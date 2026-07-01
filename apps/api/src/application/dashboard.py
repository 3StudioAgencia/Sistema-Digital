"""Caso de uso do Dashboard (W4-C16) — RF-015/US-013.

Fachada fina sobre a CONSULTA UNICA de agregacao (``DashboardRepositoryPort``).
Uma instancia por requisicao; a sessao por tras do repo DEVE vir de
``abrir_sessao_rls`` — o escopo por perfil (Matriz §7) e da RLS de ``provas``, nao
reimplementado aqui. Sem logica de negocio extra: o mapeamento contador->status
(DP-2) vive no dominio e a regra de atraso (DP-4) na funcao SQL — o servico so
orquestra a leitura (e fica como ponto natural de logging/observabilidade futura).
"""

from src.application.ports.dashboard_repository import DashboardRepositoryPort
from src.domain.dashboard import ContadoresDashboard


class DashboardService:
    def __init__(self, repo: DashboardRepositoryPort) -> None:
        self._repo = repo

    async def contadores(self) -> ContadoresDashboard:
        return await self._repo.contadores()


__all__ = ["DashboardService"]
