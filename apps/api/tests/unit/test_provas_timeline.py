"""Timeline de UMA prova (W3-C13) — ``ProvasConsultaService.obter_movimentacoes``, offline.

Cobre a montagem do insumo da Timeline com dublês em memória:
- a sequência canônica vem de ``sequencia_canonica`` (DP-1 — derivada das regras do
  C11, não duplicada);
- o histórico vem do repo de movimentações (ordem preservada) com o NOME do
  responsável resolvido (DP-2b), numa ÚNICA ida ao projetor (sem N+1);
- prova inexistente/fora-de-escopo é o MESMO 404 (``ProvaNaoEncontradaError``).
"""

import datetime as dt

import pytest
from src.application.ports.movimentacoes_repository import MovimentacoesRepositoryPort
from src.application.ports.provas_repository import (
    FiltrosProvas,
    PaginaProvas,
    ProvasRepositoryPort,
)
from src.application.provas import ProvasConsultaService
from src.domain.movimentacoes import Movimentacao
from src.domain.provas import EstadoProva, Prova, ProvaNaoEncontradaError, Rota
from src.domain.state_machine.enums import Acao
from src.domain.state_machine.machine import sequencia_canonica

VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"
STUDIO_ID = "44444444-4444-4444-4444-444444444444"
PROVA_ID = "33333333-3333-3333-3333-333333333333"


def _prova(status: EstadoProva = EstadoProva.APROVADA_VENDEDOR, ciclo: int = 1) -> Prova:
    return Prova(
        id=PROVA_ID,
        codigo="PRV-2026-06-ABCDEF",
        nome="Mussarela fatiada",
        requerimento="123456",
        cliente="Edulat",
        vendedor_id=VENDEDOR_ID,
        rota=Rota.MATRIZ,
        arte_key=f"provas/{PROVA_ID}/arte.png",
        arte_content_type="image/png",
        status=status,
        ciclo_atual=ciclo,
        created_at=dt.datetime(2026, 4, 27, tzinfo=dt.UTC),
    )


def _mov(
    estado_origem: EstadoProva,
    estado_destino: EstadoProva,
    acao: Acao,
    ator_id: str,
    *,
    ciclo: int = 1,
    motivo: str | None = None,
    assinatura_ref: str | None = "ass-1",
    minuto: int = 0,
) -> Movimentacao:
    return Movimentacao(
        id=f"mov-{estado_destino.value}",
        prova_id=PROVA_ID,
        estado_origem=estado_origem,
        estado_destino=estado_destino,
        acao=acao,
        ator_id=ator_id,
        idempotency_key=f"key-{estado_destino.value}",
        ciclo=ciclo,
        motivo=motivo,
        assinatura_ref=assinatura_ref,
        created_at=dt.datetime(2026, 4, 27, 10, minuto, tzinfo=dt.UTC),
    )


class FakeRepo(ProvasRepositoryPort):
    def __init__(self, prova: Prova | None) -> None:
        self._prova = prova

    async def get(self, prova_id: str) -> Prova | None:
        return self._prova if self._prova and self._prova.id == prova_id else None

    async def nomes_de_vendedores(self, ids: list[str]) -> dict[str, str]:  # pragma: no cover
        return {}

    async def add(self, prova: Prova) -> None:  # pragma: no cover
        raise NotImplementedError

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


class FakeMovs(MovimentacoesRepositoryPort):
    def __init__(self, movs: list[Movimentacao], nomes: dict[str, str]) -> None:
        self._movs = movs
        self._nomes = nomes
        self.ids_recebidos: list[str] | None = None

    async def listar_por_prova(self, prova_id: str) -> list[Movimentacao]:
        return [m for m in self._movs if m.prova_id == prova_id]

    async def nomes_de_atores(self, ids: list[str]) -> dict[str, str]:
        self.ids_recebidos = ids
        return {i: self._nomes[i] for i in ids if i in self._nomes}

    async def registrar(self, mov: Movimentacao) -> Movimentacao:  # pragma: no cover
        raise NotImplementedError

    async def buscar_por_idempotencia(self, idempotency_key: str) -> Movimentacao | None:
        raise NotImplementedError  # pragma: no cover


def _service(prova: Prova | None, movs: FakeMovs | None = None) -> ProvasConsultaService:
    return ProvasConsultaService(repo=FakeRepo(prova), movs=movs or FakeMovs([], {}))


async def test_monta_timeline_com_esqueleto_historico_e_nomes() -> None:
    movs = FakeMovs(
        [
            _mov(EstadoProva.CRIADA, EstadoProva.RETIRADA_VENDEDOR, Acao.IDENTIFICAR_E_ASSINAR,
                 VENDEDOR_ID, minuto=1),
            _mov(EstadoProva.RETIRADA_VENDEDOR, EstadoProva.APROVADA_VENDEDOR, Acao.APROVAR,
                 VENDEDOR_ID, minuto=2),
        ],
        {VENDEDOR_ID: "Regiane"},
    )
    timeline = await _service(_prova(), movs).obter_movimentacoes(PROVA_ID)

    assert timeline.rota is Rota.MATRIZ
    assert timeline.estado_atual is EstadoProva.APROVADA_VENDEDOR
    assert timeline.ciclo_atual == 1
    assert timeline.criada_em == dt.datetime(2026, 4, 27, tzinfo=dt.UTC)
    # DP-1: o esqueleto é exatamente a sequência canônica derivada das regras do C11.
    assert timeline.etapas_canonicas == sequencia_canonica(Rota.MATRIZ)
    # Histórico preservado em ordem, com o responsável resolvido (DP-2b).
    assert [m.movimentacao.estado_destino for m in timeline.movimentacoes] == [
        EstadoProva.RETIRADA_VENDEDOR,
        EstadoProva.APROVADA_VENDEDOR,
    ]
    assert all(m.ator_nome == "Regiane" for m in timeline.movimentacoes)


async def test_prova_inexistente_ou_fora_de_escopo_e_404() -> None:
    with pytest.raises(ProvaNaoEncontradaError, match=r"Prova não encontrada\."):
        await _service(None).obter_movimentacoes("00000000-0000-0000-0000-000000000099")


async def test_sem_historico_devolve_esqueleto_e_nao_chama_projetor() -> None:
    movs = FakeMovs([], {})
    timeline = await _service(_prova(EstadoProva.CRIADA), movs).obter_movimentacoes(PROVA_ID)

    assert timeline.movimentacoes == []
    assert timeline.etapas_canonicas == sequencia_canonica(Rota.MATRIZ)
    # Sem atores → o projetor de nomes nem é chamado (evita ida inútil ao banco).
    assert movs.ids_recebidos is None


async def test_ator_nome_none_quando_projetor_nao_resolve() -> None:
    movs = FakeMovs(
        [_mov(EstadoProva.CRIADA, EstadoProva.RETIRADA_VENDEDOR, Acao.IDENTIFICAR_E_ASSINAR,
              VENDEDOR_ID)],
        {},  # projetor vazio
    )
    timeline = await _service(_prova(), movs).obter_movimentacoes(PROVA_ID)
    assert timeline.movimentacoes[0].ator_nome is None


async def test_ids_de_atores_sao_distintos_uma_ida_ao_projetor() -> None:
    movs = FakeMovs(
        [
            _mov(EstadoProva.CRIADA, EstadoProva.RETIRADA_VENDEDOR, Acao.IDENTIFICAR_E_ASSINAR,
                 VENDEDOR_ID, minuto=1),
            _mov(EstadoProva.RETIRADA_VENDEDOR, EstadoProva.APROVADA_VENDEDOR, Acao.APROVAR,
                 VENDEDOR_ID, minuto=2),
            _mov(EstadoProva.APROVADA_VENDEDOR, EstadoProva.DE_VOLTA_STUDIO,
                 Acao.IDENTIFICAR_E_ASSINAR, STUDIO_ID, minuto=3),
        ],
        {VENDEDOR_ID: "Regiane", STUDIO_ID: "Mario"},
    )
    await _service(_prova(EstadoProva.DE_VOLTA_STUDIO), movs).obter_movimentacoes(PROVA_ID)

    assert movs.ids_recebidos is not None
    # Dois atores distintos numa só ida ao projetor (sem N+1 — RNF-022).
    assert sorted(movs.ids_recebidos) == sorted({VENDEDOR_ID, STUDIO_ID})
