"""``ProvasIdentificacaoService`` (W3-C10) — resolução QR/manual, anti-enumeração
e rate limiting, offline com dublês.

O coração do C10 (RF-004/RF-005, RN-014): QR e digitação manual resolvem o MESMO
registro pelo mesmo caminho; código malformado/inexistente/fora-de-escopo são o
MESMO 404 genérico; e a tentativa é contada+persistida ANTES de resolver, para o
limite de 30/min valer mesmo nas tentativas que dão 404.
"""

import pytest
from src.application.ports.provas_repository import (
    FiltrosProvas,
    PaginaProvas,
    ProvasRepositoryPort,
)
from src.application.ports.rate_limiter import RateLimiterPort
from src.application.ports.unit_of_work import UnitOfWork
from src.application.provas import (
    CHAVE_IDENTIFICACAO,
    LIMITE_IDENTIFICACAO,
    ProvasIdentificacaoService,
)
from src.domain.provas import (
    EstadoProva,
    LimiteDeTentativasError,
    Prova,
    ProvaNaoEncontradaError,
    Rota,
)

CODIGO = "PRV-2026-06-A2KMQ9"
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------
class FakeProvasRepository(ProvasRepositoryPort):
    def __init__(self, provas: list[Prova] | None = None) -> None:
        self.por_codigo: dict[str, Prova] = {p.codigo: p for p in (provas or [])}
        self.buscas: list[str] = []
        self.nomes: dict[str, str] = {VENDEDOR_ID: "Regiane"}

    async def buscar_por_codigo(self, codigo: str) -> Prova | None:
        self.buscas.append(codigo)
        return self.por_codigo.get(codigo)

    async def nomes_de_vendedores(self, ids: list[str]) -> dict[str, str]:
        return {i: self.nomes[i] for i in ids if i in self.nomes}

    async def add(self, prova: Prova) -> None:  # pragma: no cover
        raise NotImplementedError

    async def get(self, prova_id: str) -> Prova | None:  # pragma: no cover
        raise NotImplementedError

    async def listar(self, filtros: FiltrosProvas) -> PaginaProvas:  # pragma: no cover
        raise NotImplementedError

    async def vendedor_ids_distintos(self) -> list[str]:  # pragma: no cover
        raise NotImplementedError


class FakeRateLimiter(RateLimiterPort):
    """Devolve contagens roteirizáveis (ou um contador incremental por default)."""

    def __init__(self, contagens: list[int] | None = None) -> None:
        self.chaves: list[str] = []
        self._fila = list(contagens) if contagens is not None else []
        self._n = 0

    async def registrar_e_contar(self, chave: str) -> int:
        self.chaves.append(chave)
        self._n += 1
        return self._fila.pop(0) if self._fila else self._n


class FakeUow(UnitOfWork):
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:  # pragma: no cover
        self.rollbacks += 1


def _prova(codigo: str = CODIGO) -> Prova:
    return Prova(
        id="11111111-1111-1111-1111-111111111111",
        codigo=codigo,
        nome="Mussarela fatiada",
        requerimento="155295",
        cliente="Edulat",
        vendedor_id=VENDEDOR_ID,
        rota=Rota.MATRIZ,
        status=EstadoProva.CRIADA,
        arte_key="provas/x/arte.png",
        arte_content_type="image/png",
    )


def _montar(
    provas: list[Prova] | None = None,
    contagens: list[int] | None = None,
) -> tuple[ProvasIdentificacaoService, FakeProvasRepository, FakeRateLimiter, FakeUow]:
    repo = FakeProvasRepository(provas)
    limiter = FakeRateLimiter(contagens)
    uow = FakeUow()
    service = ProvasIdentificacaoService(repo=repo, rate_limiter=limiter, uow=uow)
    return service, repo, limiter, uow


# ---------------------------------------------------------------------------
# Caminho feliz + idempotência de mecanismo (QR == manual)
# ---------------------------------------------------------------------------
async def test_resolve_a_prova_pelo_codigo() -> None:
    service, _, limiter, uow = _montar([_prova()])
    item = await service.identificar(CODIGO)
    assert item.prova.codigo == CODIGO
    assert item.vendedor_nome == "Regiane"  # nome resolvido (DP-7)
    assert limiter.chaves == [CHAVE_IDENTIFICACAO]  # contou a tentativa
    assert uow.commits == 1  # persistiu a contagem


@pytest.mark.parametrize(
    "entrada",
    [
        CODIGO,  # exato (digitação correta)
        "  PRV-2026-06-A2KMQ9\n",  # QR com espaço/quebra de linha do leitor
        "prv-2026-06-a2kmq9",  # digitação em minúsculas
    ],
)
async def test_qr_e_manual_resolvem_o_mesmo_registro(entrada: str) -> None:
    """O QR carrega o próprio código (C06): leitura e digitação batem no MESMO
    caminho. Normalização (trim + maiúsculas) faz minúsculas/quebras convergirem."""
    service, repo, _, _ = _montar([_prova()])
    item = await service.identificar(entrada)
    assert item.prova.id == "11111111-1111-1111-1111-111111111111"
    assert repo.buscas == [CODIGO]  # consultou pela forma canônica


# ---------------------------------------------------------------------------
# Anti-enumeração (RN-014): inválido == inexistente == fora-de-escopo → 404
# ---------------------------------------------------------------------------
async def test_codigo_malformado_e_404_sem_consultar() -> None:
    """Formato inválido não vira 422 (revelaria que nem consultou): mesmo 404
    genérico do inexistente — e nem toca o repositório."""
    service, repo, _, _ = _montar([_prova()])
    with pytest.raises(ProvaNaoEncontradaError):
        await service.identificar("3S-1234-5678")  # máscara do design (legado)
    assert repo.buscas == []  # curto-circuito: nem consultou


async def test_codigo_inexistente_e_404() -> None:
    service, repo, _, _ = _montar([])  # repositório vazio
    with pytest.raises(ProvaNaoEncontradaError):
        await service.identificar("PRV-2026-06-B3T7XC")
    assert repo.buscas == ["PRV-2026-06-B3T7XC"]


async def test_fora_de_escopo_e_inexistente_sao_indistinguiveis() -> None:
    """No serviço, "fora do escopo" = a RLS devolve None (igual ao inexistente):
    o mesmo erro, sem diferença observável."""
    service, _, _, _ = _montar([])  # buscar_por_codigo devolve None nos dois casos
    inexistente = ProvaNaoEncontradaError()
    with pytest.raises(ProvaNaoEncontradaError) as fora:
        await service.identificar(CODIGO)  # válido, mas "invisível" (None)
    assert str(fora.value) == str(inexistente)
    assert fora.value.codigo == inexistente.codigo


# ---------------------------------------------------------------------------
# Rate limiting (RN-014: 30/ator/minuto) — conta+persiste ANTES de resolver
# ---------------------------------------------------------------------------
async def test_no_limite_ainda_resolve() -> None:
    service, repo, _, _ = _montar([_prova()], contagens=[LIMITE_IDENTIFICACAO])
    item = await service.identificar(CODIGO)  # 30ª tentativa passa
    assert item.prova.codigo == CODIGO
    assert repo.buscas == [CODIGO]


async def test_acima_do_limite_bloqueia_antes_de_resolver() -> None:
    service, repo, _, uow = _montar([_prova()], contagens=[LIMITE_IDENTIFICACAO + 1])
    with pytest.raises(LimiteDeTentativasError):
        await service.identificar(CODIGO)  # 31ª tentativa → 429
    assert repo.buscas == []  # nem chegou a resolver
    assert uow.commits == 1  # mas a tentativa FOI persistida (não some no rollback)


async def test_tentativa_que_da_404_ainda_persiste_a_contagem() -> None:
    """Idempotência do limite: o 404 não desfaz o incremento (commit veio antes)."""
    service, _, _, uow = _montar([])  # resolução dará 404
    with pytest.raises(ProvaNaoEncontradaError):
        await service.identificar(CODIGO)
    assert uow.commits == 1
