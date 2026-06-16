"""``ProvasTransicaoService`` (W3-C11) — orquestração offline com dublês.

Cobre o que é difícil/caro de provocar pela borda: ATOMICIDADE (falha ao gravar
a movimentação → status NÃO é commitado, rollback acontece — RNF-017) e os ramos
de IDEMPOTÊNCIA (convergência e conflito — RNF-015/DP-2), além de 404/422/403/
motivo e o carimbo terminal. A regra pura da §6 está em ``test_state_machine``;
aqui o foco é o caso de uso.
"""

import datetime as dt

import pytest
from src.application.ports.movimentacoes_repository import MovimentacoesRepositoryPort
from src.application.ports.provas_repository import (
    FiltrosProvas,
    PaginaProvas,
    ProvasRepositoryPort,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.application.transicoes import ProvasTransicaoService
from src.domain.movimentacoes import Movimentacao, TransicaoIdempotenciaConflitoError
from src.domain.provas import EstadoProva, Prova, ProvaNaoEncontradaError, Rota
from src.domain.state_machine.enums import Acao
from src.domain.state_machine.machine import (
    MotivoObrigatorioError,
    TransicaoInvalidaError,
    TransicaoNaoAutorizadaError,
)
from src.domain.usuarios import Setor, Usuario

QUANDO = dt.datetime(2026, 6, 16, 12, 0, tzinfo=dt.UTC)
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"
ADMIN_ID = "99999999-9999-9999-9999-999999999999"


def _prova(status: EstadoProva = EstadoProva.CRIADA, rota: Rota = Rota.MATRIZ) -> Prova:
    return Prova(
        id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        codigo="PRV-2026-06-A2KMQ9",
        nome="P",
        requerimento="1",
        cliente="C",
        vendedor_id=VENDEDOR_ID,
        rota=rota,
        arte_key="provas/x/arte.png",
        arte_content_type="image/png",
        status=status,
        ciclo_atual=1,
    )


def _vendedor() -> Usuario:
    return Usuario(id=VENDEDOR_ID, nome="V", email="v@x.z", setor=Setor.VENDEDOR)


def _admin() -> Usuario:
    return Usuario(
        id=ADMIN_ID, nome="A", email="a@x.z", setor=Setor.STUDIO, administrador=True
    )


class FakeProvasRepo(ProvasRepositoryPort):
    def __init__(self, prova: Prova | None) -> None:
        self._prova = prova
        self.status_atualizado: tuple[EstadoProva, dt.datetime | None] | None = None

    async def obter_para_transicao(self, prova_id: str) -> Prova | None:
        return self._prova

    async def atualizar_status(
        self,
        prova_id: str,
        novo_status: EstadoProva,
        finalizada_em: dt.datetime | None,
        quando: dt.datetime,
    ) -> None:
        self.status_atualizado = (novo_status, finalizada_em)

    async def nomes_de_vendedores(self, ids: list[str]) -> dict[str, str]:
        return {VENDEDOR_ID: "Regiane"}

    async def add(self, prova: Prova) -> None:  # pragma: no cover
        raise NotImplementedError

    async def get(self, prova_id: str) -> Prova | None:  # pragma: no cover
        raise NotImplementedError

    async def buscar_por_codigo(self, codigo: str) -> Prova | None:  # pragma: no cover
        raise NotImplementedError

    async def listar(self, filtros: FiltrosProvas) -> PaginaProvas:  # pragma: no cover
        raise NotImplementedError

    async def vendedor_ids_distintos(self) -> list[str]:  # pragma: no cover
        raise NotImplementedError


class FakeMovsRepo(MovimentacoesRepositoryPort):
    def __init__(
        self, existente: Movimentacao | None = None, falha: Exception | None = None
    ) -> None:
        self._existente = existente
        self._falha = falha
        self.registradas: list[Movimentacao] = []

    async def registrar(self, mov: Movimentacao) -> Movimentacao:
        if self._falha is not None:
            raise self._falha
        self.registradas.append(mov)
        return mov

    async def buscar_por_idempotencia(self, idempotency_key: str) -> Movimentacao | None:
        return self._existente


class FakeUoW(UnitOfWork):
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _servico(
    repo: FakeProvasRepo, movs: FakeMovsRepo, uow: FakeUoW, ator: Usuario
) -> ProvasTransicaoService:
    return ProvasTransicaoService(repo=repo, movs=movs, uow=uow, ator=ator, relogio=lambda: QUANDO)


# ---------------------------------------------------------------------------
async def test_caminho_feliz_transiciona_grava_e_commita() -> None:
    repo, movs, uow = FakeProvasRepo(_prova()), FakeMovsRepo(), FakeUoW()
    svc = _servico(repo, movs, uow, _vendedor())
    out = await svc.executar(
        prova_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        acao=Acao.IDENTIFICAR_E_ASSINAR,
        assinatura_ref="11111111-1111-1111-1111-111111111111",
        idempotency_key="33333333-3333-3333-3333-333333333333",
    )
    assert out.prova.status == EstadoProva.RETIRADA_VENDEDOR
    assert out.vendedor_nome == "Regiane"
    assert repo.status_atualizado == (EstadoProva.RETIRADA_VENDEDOR, None)
    assert len(movs.registradas) == 1
    assert uow.commits == 1


async def test_terminal_carimba_finalizada_em() -> None:
    repo = FakeProvasRepo(_prova(status=EstadoProva.COM_MOTORISTA_ENTREGA_FINAL))
    movs, uow = FakeMovsRepo(), FakeUoW()
    svc = _servico(repo, movs, uow, Usuario(id="c", nome="C", email="c@x.z", setor=Setor.CLICHERIA))
    out = await svc.executar(
        prova_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        acao=Acao.IDENTIFICAR_E_ASSINAR,
        assinatura_ref="11111111-1111-1111-1111-111111111111",
        idempotency_key="33333333-3333-3333-3333-333333333333",
    )
    assert out.prova.status == EstadoProva.RECEBIDA_CLICHERIA
    assert repo.status_atualizado == (EstadoProva.RECEBIDA_CLICHERIA, QUANDO)
    assert out.prova.finalizada_em == QUANDO


async def test_prova_fora_do_escopo_e_404_sem_commit() -> None:
    repo, movs, uow = FakeProvasRepo(None), FakeMovsRepo(), FakeUoW()
    svc = _servico(repo, movs, uow, _vendedor())
    with pytest.raises(ProvaNaoEncontradaError):
        await svc.executar(
            prova_id="x",
            acao=Acao.IDENTIFICAR_E_ASSINAR,
            assinatura_ref="11111111-1111-1111-1111-111111111111",
            idempotency_key="33333333-3333-3333-3333-333333333333",
        )
    assert uow.commits == 0


async def test_acao_invalida_e_422_sem_commit() -> None:
    repo, movs, uow = FakeProvasRepo(_prova()), FakeMovsRepo(), FakeUoW()
    svc = _servico(repo, movs, uow, _vendedor())
    with pytest.raises(TransicaoInvalidaError):
        await svc.executar(
            prova_id="a", acao=Acao.APROVAR,
            assinatura_ref="11111111-1111-1111-1111-111111111111",
            idempotency_key="33333333-3333-3333-3333-333333333333",
        )
    assert uow.commits == 0 and repo.status_atualizado is None


async def test_perfil_errado_e_403_sem_commit() -> None:
    repo, movs, uow = FakeProvasRepo(_prova()), FakeMovsRepo(), FakeUoW()
    # Clicheria tentando o avanço que é do Vendedor (Matriz/criada).
    ator = Usuario(id="c", nome="C", email="c@x.z", setor=Setor.CLICHERIA)
    svc = _servico(repo, movs, uow, ator)
    with pytest.raises(TransicaoNaoAutorizadaError):
        await svc.executar(
            prova_id="a", acao=Acao.IDENTIFICAR_E_ASSINAR,
            assinatura_ref="11111111-1111-1111-1111-111111111111",
            idempotency_key="33333333-3333-3333-3333-333333333333",
        )
    assert uow.commits == 0


async def test_reprovar_sem_motivo_e_422_sem_commit() -> None:
    repo = FakeProvasRepo(_prova(status=EstadoProva.RETIRADA_VENDEDOR))
    movs, uow = FakeMovsRepo(), FakeUoW()
    svc = _servico(repo, movs, uow, _vendedor())
    with pytest.raises(MotivoObrigatorioError):
        await svc.executar(
            prova_id="a", acao=Acao.REPROVAR,
            assinatura_ref="11111111-1111-1111-1111-111111111111",
            idempotency_key="33333333-3333-3333-3333-333333333333",
            motivo="   ",
        )
    assert uow.commits == 0


async def test_atomicidade_falha_ao_gravar_movimentacao_nao_commita() -> None:
    """RNF-017: erro ao inserir a movimentação → NÃO commita (rollback do __aexit__)
    → status não fica inconsistente."""
    repo = FakeProvasRepo(_prova())
    movs = FakeMovsRepo(falha=RuntimeError("falha de banco no INSERT da movimentação"))
    uow = FakeUoW()
    svc = _servico(repo, movs, uow, _vendedor())
    with pytest.raises(RuntimeError):
        await svc.executar(
            prova_id="a", acao=Acao.IDENTIFICAR_E_ASSINAR,
            assinatura_ref="11111111-1111-1111-1111-111111111111",
            idempotency_key="33333333-3333-3333-3333-333333333333",
        )
    assert uow.commits == 0
    assert uow.rollbacks >= 1  # o __aexit__ desfez a transação


async def test_idempotencia_reenvio_converge_sem_reaplicar() -> None:
    prova = _prova(status=EstadoProva.RETIRADA_VENDEDOR)  # já transicionada
    existente = Movimentacao(
        id="m1",
        prova_id=prova.id,
        estado_origem=EstadoProva.CRIADA,
        estado_destino=EstadoProva.RETIRADA_VENDEDOR,
        acao=Acao.IDENTIFICAR_E_ASSINAR,
        ator_id=VENDEDOR_ID,
        idempotency_key="33333333-3333-3333-3333-333333333333",
    )
    repo, movs, uow = FakeProvasRepo(prova), FakeMovsRepo(existente=existente), FakeUoW()
    svc = _servico(repo, movs, uow, _vendedor())
    out = await svc.executar(
        prova_id=prova.id, acao=Acao.IDENTIFICAR_E_ASSINAR,
        assinatura_ref="11111111-1111-1111-1111-111111111111",
        idempotency_key="33333333-3333-3333-3333-333333333333",
    )
    assert out.prova.status == EstadoProva.RETIRADA_VENDEDOR
    assert repo.status_atualizado is None  # NÃO reaplicou
    assert movs.registradas == []  # NÃO duplicou
    assert uow.commits == 0


async def test_idempotencia_mesma_chave_operacao_diferente_e_409() -> None:
    prova = _prova()
    existente = Movimentacao(
        id="m1",
        prova_id="OUTRA-PROVA",
        estado_origem=EstadoProva.CRIADA,
        estado_destino=EstadoProva.RETIRADA_VENDEDOR,
        acao=Acao.IDENTIFICAR_E_ASSINAR,
        ator_id=VENDEDOR_ID,
        idempotency_key="33333333-3333-3333-3333-333333333333",
    )
    repo, movs, uow = FakeProvasRepo(prova), FakeMovsRepo(existente=existente), FakeUoW()
    svc = _servico(repo, movs, uow, _vendedor())
    with pytest.raises(TransicaoIdempotenciaConflitoError):
        await svc.executar(
            prova_id=prova.id, acao=Acao.IDENTIFICAR_E_ASSINAR,
            assinatura_ref="11111111-1111-1111-1111-111111111111",
            idempotency_key="33333333-3333-3333-3333-333333333333",
        )
    assert uow.commits == 0


async def test_admin_cancela_com_motivo_e_grava_movimentacao() -> None:
    repo, movs, uow = FakeProvasRepo(_prova()), FakeMovsRepo(), FakeUoW()
    svc = _servico(repo, movs, uow, _admin())
    out = await svc.executar(
        prova_id="a", acao=Acao.CANCELAR,
        assinatura_ref="11111111-1111-1111-1111-111111111111",
        idempotency_key="33333333-3333-3333-3333-333333333333",
        motivo="cliente desistiu",
    )
    assert out.prova.status == EstadoProva.CANCELADA
    assert movs.registradas[0].motivo == "cliente desistiu"
    assert movs.registradas[0].ator_id == ADMIN_ID
    assert uow.commits == 1
