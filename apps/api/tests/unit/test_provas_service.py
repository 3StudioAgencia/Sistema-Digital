"""``ProvasService`` (W2-C06) — criação atômica, retry de colisão e compensação.

Offline, com dublês: a ordem upload→INSERT→commit e a compensação do R2 são o
coração da RNF-017 (nunca prova órfã; objeto órfão só se a própria compensação
falhar — e aí com CRITICAL no log).
"""

import datetime as dt
import logging

import pytest
from src.application.ports.provas_repository import (
    CodigoJaExisteError,
    FiltrosProvas,
    PaginaProvas,
    ProvaJaExisteError,
    ProvasRepositoryPort,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.application.ports.usuarios_repository import (
    FiltrosUsuarios,
    PaginaUsuarios,
    UsuariosRepositoryPort,
)
from src.application.provas import (
    MAX_TENTATIVAS_CODIGO,
    CriarProva,
    GeracaoDeCodigoEsgotadaError,
    ProvasService,
)
from src.domain.provas import (
    ArteInvalidaError,
    CriacaoDivergenteError,
    EstadoProva,
    Prova,
    Rota,
    VendedorInvalidoError,
    validar_codigo,
)
from src.domain.usuarios import Localizacao, Setor, Usuario

from tests.conftest import FakeStorage

JPEG_MINIMO = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PNG_MINIMO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
QUANDO = dt.datetime(2026, 6, 12, tzinfo=dt.UTC)
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------
class FakeProvasRepository(ProvasRepositoryPort):
    def __init__(self) -> None:
        self.provas: dict[str, Prova] = {}
        self.codigos_tentados: list[str] = []
        self.falhas_pendentes: list[Exception] = []

    async def add(self, prova: Prova) -> None:
        self.codigos_tentados.append(prova.codigo)
        if self.falhas_pendentes:
            raise self.falhas_pendentes.pop(0)
        prova.created_at = prova.updated_at = QUANDO
        self.provas[prova.id] = prova

    async def get(self, prova_id: str) -> Prova | None:
        return self.provas.get(prova_id)

    # Métodos de leitura do C07/C10: o serviço de CRIAÇÃO não os usa.
    async def obter_para_transicao(self, prova_id: str) -> Prova | None:  # pragma: no cover
        raise NotImplementedError

    async def atualizar_status(
        self,
        prova_id: str,
        novo_status: EstadoProva,
        finalizada_em: dt.datetime | None,
        quando: dt.datetime,
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    async def incrementar_ciclo(self, prova_id: str) -> int:  # pragma: no cover
        raise NotImplementedError

    async def buscar_por_codigo(self, codigo: str) -> Prova | None:  # pragma: no cover
        raise NotImplementedError

    async def listar(self, filtros: FiltrosProvas) -> PaginaProvas:  # pragma: no cover
        raise NotImplementedError

    async def vendedor_ids_distintos(self) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    async def nomes_de_vendedores(self, ids: list[str]) -> dict[str, str]:  # pragma: no cover
        raise NotImplementedError


class FakeUsuariosRepository(UsuariosRepositoryPort):
    def __init__(self) -> None:
        self.usuarios: dict[str, Usuario] = {}

    async def get(self, usuario_id: str) -> Usuario | None:
        return self.usuarios.get(usuario_id)

    async def get_by_email(self, email: str) -> Usuario | None:  # pragma: no cover
        raise NotImplementedError

    async def add(self, usuario: Usuario) -> None:  # pragma: no cover
        raise NotImplementedError

    async def update(self, usuario: Usuario) -> None:  # pragma: no cover
        raise NotImplementedError

    async def listar(self, filtros: FiltrosUsuarios) -> PaginaUsuarios:  # pragma: no cover
        raise NotImplementedError

    async def count_admins_ativos(self, excluir_id: str | None = None) -> int:  # pragma: no cover
        raise NotImplementedError

    async def travar_gestao_de_admins(self) -> None:  # pragma: no cover
        raise NotImplementedError


class FakeUow(UnitOfWork):
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class StorageComDeleteQuebrado(FakeStorage):
    def delete(self, key: str) -> None:
        raise RuntimeError("delete indisponível")


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------
def _vendedor(ativo: bool = True, setor: Setor = Setor.VENDEDOR) -> Usuario:
    return Usuario(
        id=VENDEDOR_ID,
        nome="Renan Petrim",
        email="renan@x.z",
        setor=setor,
        localizacao=Localizacao.MATRIZ if setor is Setor.VENDEDOR else None,
        ativo=ativo,
    )


def _montar(
    vendedor: Usuario | None = None,
    storage: FakeStorage | None = None,
) -> tuple[ProvasService, FakeProvasRepository, FakeUsuariosRepository, FakeStorage, FakeUow]:
    repo = FakeProvasRepository()
    usuarios = FakeUsuariosRepository()
    if vendedor is not None:
        usuarios.usuarios[vendedor.id] = vendedor
    storage = storage or FakeStorage()
    uow = FakeUow()
    service = ProvasService(
        repo=repo,
        usuarios_repo=usuarios,
        storage=storage,
        uow=uow,
        relogio=lambda: QUANDO,
    )
    return service, repo, usuarios, storage, uow


def _cmd(**overrides: object) -> CriarProva:
    base: dict[str, object] = {
        "nome": "Etiq Cafe Caproni Classico",
        "requerimento": "155295",
        "cliente": "Cafe Caproni",
        "vendedor_id": VENDEDOR_ID,
        "rota": Rota.MATRIZ,
    }
    base.update(overrides)
    return CriarProva(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Caminho feliz
# ---------------------------------------------------------------------------
async def test_criar_persiste_prova_criada_na_rota_com_arte_no_storage() -> None:
    service, repo, _, storage, uow = _montar(_vendedor())

    prova = await service.criar(_cmd(), JPEG_MINIMO, "image/jpeg")

    assert prova.status is EstadoProva.CRIADA  # US-001: nasce "Criada"
    assert prova.rota is Rota.MATRIZ  # na rota selecionada
    assert validar_codigo(prova.codigo)
    assert prova.codigo.startswith("PRV-2026-06-")  # relógio injetado
    assert repo.provas[prova.id] is prova
    assert prova.arte_key == f"provas/{prova.id}/arte.jpg"
    assert storage.download(prova.arte_key) == JPEG_MINIMO
    assert prova.arte_content_type == "image/jpeg"
    assert uow.commits == 1


async def test_criar_detecta_png_e_normaliza_strings() -> None:
    service, _, _, storage, _ = _montar(_vendedor())

    prova = await service.criar(
        _cmd(nome="  Prova X  ", cliente=" C ", requerimento=" 01 ".strip()),
        PNG_MINIMO,
        None,  # sem content-type declarado: vale o magic byte
    )

    assert prova.arte_key.endswith("/arte.png")
    assert prova.arte_content_type == "image/png"
    assert prova.nome == "Prova X"
    assert prova.cliente == "C"
    assert storage.download(prova.arte_key) == PNG_MINIMO


# ---------------------------------------------------------------------------
# Validações de negócio (nada sobe ao storage)
# ---------------------------------------------------------------------------
async def test_arte_invalida_nao_toca_storage_nem_banco() -> None:
    service, repo, _, storage, _ = _montar(_vendedor())
    with pytest.raises(ArteInvalidaError):
        await service.criar(_cmd(), b"GIF89a" + b"\x00" * 16, "image/gif")
    assert repo.provas == {} and storage._objects == {}


@pytest.mark.parametrize(
    "vendedor",
    [None, _vendedor(ativo=False), _vendedor(setor=Setor.MOTORISTA)],
)
async def test_vendedor_invalido_e_rejeitado_antes_do_upload(vendedor: Usuario | None) -> None:
    service, repo, _, storage, _ = _montar(vendedor)
    with pytest.raises(VendedorInvalidoError):
        await service.criar(_cmd(), JPEG_MINIMO, "image/jpeg")
    assert repo.provas == {} and storage._objects == {}


# ---------------------------------------------------------------------------
# Colisão de código (DP-3) e atomicidade (RNF-017)
# ---------------------------------------------------------------------------
async def test_colisao_de_codigo_regenera_e_converge() -> None:
    service, repo, _, storage, uow = _montar(_vendedor())
    repo.falhas_pendentes = [CodigoJaExisteError("PRV-X")]

    prova = await service.criar(_cmd(), JPEG_MINIMO, "image/jpeg")

    assert len(repo.codigos_tentados) == 2
    assert repo.codigos_tentados[0] != repo.codigos_tentados[1]  # regenerou
    assert prova.codigo == repo.codigos_tentados[1]
    # a arte NÃO é re-enviada nem apagada (key derivada do id, estável)
    assert storage.download(prova.arte_key) == JPEG_MINIMO
    assert uow.commits == 1


async def test_colisoes_esgotadas_viram_erro_interno_e_compensam_a_arte() -> None:
    service, repo, _, storage, _ = _montar(_vendedor())
    repo.falhas_pendentes = [CodigoJaExisteError("PRV-X")] * MAX_TENTATIVAS_CODIGO

    with pytest.raises(GeracaoDeCodigoEsgotadaError):
        await service.criar(_cmd(), JPEG_MINIMO, "image/jpeg")

    assert len(repo.codigos_tentados) == MAX_TENTATIVAS_CODIGO
    assert storage._objects == {}  # compensação removeu a arte
    assert repo.provas == {}  # nenhuma prova órfã


async def test_falha_no_insert_compensa_a_arte_e_propaga_o_erro_original() -> None:
    service, repo, _, storage, uow = _montar(_vendedor())
    repo.falhas_pendentes = [RuntimeError("banco caiu")]

    with pytest.raises(RuntimeError, match="banco caiu"):
        await service.criar(_cmd(), JPEG_MINIMO, "image/jpeg")

    assert storage._objects == {}  # sem objeto órfão
    assert repo.provas == {}  # sem prova órfã
    assert uow.rollbacks >= 1  # transação desfeita


async def test_compensacao_que_falha_loga_critical_e_preserva_o_erro_original(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, repo, _, _storage, _ = _montar(_vendedor(), storage=StorageComDeleteQuebrado())
    repo.falhas_pendentes = [RuntimeError("banco caiu")]

    with (
        caplog.at_level(logging.CRITICAL, logger="rastreio.provas"),
        pytest.raises(RuntimeError, match="banco caiu"),  # erro ORIGINAL, não o do delete
    ):
        await service.criar(_cmd(), JPEG_MINIMO, "image/jpeg")

    assert any(
        getattr(r, "event", "") == "compensacao_arte_falhou" for r in caplog.records
    )  # objeto órfão fica MARCADO para limpeza (RNF-024)


# ---------------------------------------------------------------------------
# Idempotência por prova_id (RNF-015 — revisão adversarial W2-C06)
# ---------------------------------------------------------------------------
async def test_reenvio_com_a_mesma_chave_converge_sem_novo_upload() -> None:
    """Resposta perdida (timeout pós-commit) + retry: devolve a prova existente."""
    service, repo, _, storage, uow = _montar(_vendedor())
    primeira = await service.criar(
        _cmd(prova_id="33333333-3333-3333-3333-333333333333"), JPEG_MINIMO, "image/jpeg"
    )
    uploads_antes = dict(storage._objects)

    segunda = await service.criar(
        _cmd(prova_id="33333333-3333-3333-3333-333333333333"), JPEG_MINIMO, "image/jpeg"
    )

    assert segunda is primeira or segunda.id == primeira.id
    assert segunda.codigo == primeira.codigo  # NENHUMA prova nova
    assert len(repo.provas) == 1
    assert storage._objects == uploads_antes  # pré-check converge ANTES do upload
    assert uow.commits == 1  # só a primeira criação commitou


async def test_mesma_chave_com_dados_diferentes_e_409() -> None:
    service, repo, _, _, _ = _montar(_vendedor())
    await service.criar(
        _cmd(prova_id="33333333-3333-3333-3333-333333333333"), JPEG_MINIMO, "image/jpeg"
    )
    with pytest.raises(CriacaoDivergenteError):
        await service.criar(
            _cmd(prova_id="33333333-3333-3333-3333-333333333333", nome="OUTRO NOME"),
            JPEG_MINIMO,
            "image/jpeg",
        )
    assert len(repo.provas) == 1  # nada duplicado nem sobrescrito


async def test_corrida_de_idempotencia_no_insert_converge_sem_compensar_a_arte() -> None:
    """Requisição idêntica venceu entre o pré-check e o INSERT (PK violada):
    converge para a existente e NÃO deleta a arte — a key pertence a ela."""
    service, repo, _, storage, _ = _montar(_vendedor())
    chave = "44444444-4444-4444-4444-444444444444"
    existente = Prova(
        id=chave,
        codigo="PRV-2026-06-K3T9XB",
        nome="Etiq Cafe Caproni Classico",
        requerimento="155295",
        cliente="Cafe Caproni",
        vendedor_id=VENDEDOR_ID,
        rota=Rota.MATRIZ,
        arte_key=f"provas/{chave}/arte.jpg",
        arte_content_type="image/jpeg",
        created_at=QUANDO,
        updated_at=QUANDO,
    )
    repo.falhas_pendentes = [ProvaJaExisteError(chave)]

    async def get_pos_colisao(prova_id: str) -> Prova | None:
        # pré-check vê vazio; após a "colisão", a linha da concorrente aparece
        return existente if repo.codigos_tentados else None

    repo.get = get_pos_colisao  # type: ignore[method-assign]

    prova = await service.criar(_cmd(prova_id=chave), JPEG_MINIMO, "image/jpeg")

    assert prova is existente
    assert existente.arte_key in storage._objects  # compensação NÃO rodou
