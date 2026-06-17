"""Dashboard (W4-C16) — domínio + serviço, offline (sem Postgres).

Trava o MAPEAMENTO contador->status (DP-2) — a decisão de negócio que o
repositório injeta na consulta — e o passthrough do serviço. A regra de "Atrasada"
(horas úteis) e a agregação RLS-escopada são validadas em integração (@db).
"""

from src.application.dashboard import DashboardService
from src.application.ports.dashboard_repository import DashboardRepositoryPort
from src.domain.dashboard import (
    STATUS_APROVADAS,
    STATUS_COM_VENDEDOR,
    STATUS_NA_CLICHERIA,
    AtrasadaVendedor,
    ContadoresDashboard,
)
from src.domain.provas import EstadoProva
from src.domain.state_machine.rules import ESTADOS_TERMINAIS


class FakeDashboardRepo(DashboardRepositoryPort):
    def __init__(self, contadores: ContadoresDashboard) -> None:
        self._contadores = contadores
        self.chamadas = 0

    async def contadores(self) -> ContadoresDashboard:
        self.chamadas += 1
        return self._contadores


async def test_servico_repassa_os_contadores_do_repo() -> None:
    esperado = ContadoresDashboard(
        criadas_hoje=25,
        com_vendedor=6894,
        aprovadas=5487,
        na_clicheria=5,
        atrasadas_total=258,
        atrasadas_por_vendedor=(AtrasadaVendedor("v1", "Regiane", 43),),
    )
    repo = FakeDashboardRepo(esperado)
    service = DashboardService(repo)

    resultado = await service.contadores()

    assert resultado is esperado
    assert repo.chamadas == 1  # uma única ida ao repositório (consulta única)


def test_mapeamento_contador_para_status_dp2() -> None:
    """DP-2 (fonte única): 'Com Vendedor' = posse do vendedor nas 4 rotas;
    'Aprovadas' = aprovada_vendedor; 'Na clicheria' = recebida_clicheria (terminal)."""
    assert STATUS_COM_VENDEDOR == (
        EstadoProva.RETIRADA_VENDEDOR,
        EstadoProva.ENCAMINHADA_PARA_VENDEDOR,
    )
    assert STATUS_APROVADAS == (EstadoProva.APROVADA_VENDEDOR,)
    assert STATUS_NA_CLICHERIA == (EstadoProva.RECEBIDA_CLICHERIA,)


def test_na_clicheria_e_terminal_concluidas() -> None:
    """'Na clicheria' é o terminal 'Concluídas' do RF-015 — coerente com o motor:
    o estado contado é terminal (não entra no cálculo de 'Atrasada')."""
    assert set(STATUS_NA_CLICHERIA) <= ESTADOS_TERMINAIS
    # E os contadores ATIVOS não tocam terminais.
    assert not (set(STATUS_COM_VENDEDOR) & ESTADOS_TERMINAIS)
    assert not (set(STATUS_APROVADAS) & ESTADOS_TERMINAIS)
