"""Portas do Log de Auditoria (W6-C20) — escrita (captura) e leitura (consulta).

Duas portas com responsabilidades opostas, propositadamente separadas:

- ``AuditLogPort`` (ESCRITA) — a captura. Chamada pelos casos de uso que produzem
  eventos (criação C06, escaneamento C10, transições C11/C14/C15). Participa da
  transação CORRENTE do chamador (atômica com a mutação de domínio — RNF-017); o
  commit é do caso de uso. O ator é forçado pelas claims no banco (anti-forja), o
  hash encadeado é calculado pela função SQL — o adapter só enriquece IP/origem/
  request_id do contexto da requisição. ``registrar`` é o ÚNICO caminho de escrita.

- ``AuditoriaRepositoryPort`` (LEITURA) — a janela read-only do C20: listagem
  paginada/filtrada, atores distintos para o dropdown e a verificação de
  integridade do chain. Leitura PURA (não participa de escrita). Sob a RLS
  ``audit_log_select_admin`` (3Studio-only) — o gate da borda já garante o admin.
"""

from abc import ABC, abstractmethod

from src.domain.auditoria import (
    AtorRef,
    FiltrosAuditoria,
    NovoEventoAuditoria,
    PaginaAuditoria,
    ResultadoIntegridade,
)


class AuditLogPort(ABC):
    """Captura append-only de eventos (a única porta de escrita do log)."""

    @abstractmethod
    async def registrar(self, evento: NovoEventoAuditoria) -> None:
        """Acrescenta UM evento ao log na transação corrente (sem commit próprio).

        Enriquece com IP/User-Agent/origem/request_id do contexto da requisição e
        delega à função SQL ``private.audit_log_append`` (SECURITY DEFINER), que
        força o ator das claims e calcula ``seq``/``prev_hash``/``hash`` sob o lock
        do chain. Idempotência é responsabilidade do chamador: o registro só é
        chamado no ramo que de fato cria o evento (transição nova, criação,
        identificação bem-sucedida) — nunca num reenvio que converge."""


class AuditoriaRepositoryPort(ABC):
    """Leitura do log para a interface de Auditoria (3Studio-only)."""

    @abstractmethod
    async def listar(self, filtros: FiltrosAuditoria) -> PaginaAuditoria:
        """Página filtrada/ordenada do log (server-side, sem N+1 — RNF-022).

        Filtros: tipos de evento, ator, busca (motivo/cliente/nº requerimento),
        período (``created_at``) e ordem (``seq`` desc/asc). O nome do ator é
        resolvido por JOIN a ``usuarios`` (o chamador é admin — vê todos)."""

    @abstractmethod
    async def atores(self) -> list[AtorRef]:
        """Atores DISTINTOS presentes no log (id + nome) — popula o dropdown "Ator"."""

    @abstractmethod
    async def verificar(self) -> ResultadoIntegridade:
        """Recomputa o chain (``private.audit_log_verificar``) e devolve a 1ª linha
        divergente (tamper-evidence — DP-4)."""


__all__ = ["AuditLogPort", "AuditoriaRepositoryPort"]
