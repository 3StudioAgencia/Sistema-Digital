"""Caso de uso de LEITURA do Log de Auditoria (W6-C20) — read-only, 3Studio-only.

Fachada fina sobre ``AuditoriaRepositoryPort`` (uma instância por requisição). A
captura (escrita) é efeito colateral dos casos de uso de domínio (criação/
escaneamento/transições) via ``AuditLogPort`` — NÃO passa por aqui: este serviço só
ABRE a janela read-only do C20. O escopo (3Studio) é da RLS ``audit_log_select_admin``
+ o gate ``Recurso.LOG_AUDITORIA`` na borda (defesa em profundidade).
"""

from src.application.ports.audit_log import AuditoriaRepositoryPort
from src.domain.auditoria import (
    AtorRef,
    FiltrosAuditoria,
    PaginaAuditoria,
    ResultadoIntegridade,
)


class AuditoriaService:
    """Leitura do log: listagem filtrada, atores e verificação de integridade."""

    def __init__(self, repo: AuditoriaRepositoryPort) -> None:
        self._repo = repo

    async def listar(self, filtros: FiltrosAuditoria) -> PaginaAuditoria:
        """Página filtrada/ordenada do log (server-side, sem N+1 — RNF-022)."""
        return await self._repo.listar(filtros)

    async def atores(self) -> list[AtorRef]:
        """Atores distintos do log (id + nome) — popula o dropdown "Ator"."""
        return await self._repo.atores()

    async def verificar(self) -> ResultadoIntegridade:
        """Recomputa o chain e devolve a 1ª linha divergente (tamper-evidence — DP-4)."""
        return await self._repo.verificar()


__all__ = ["AuditoriaService"]
