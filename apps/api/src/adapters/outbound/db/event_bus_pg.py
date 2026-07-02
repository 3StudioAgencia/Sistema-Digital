"""Adapter de ``EventBusPort`` via ``pg_notify`` do PostgreSQL (etapa 3 da migração).

Executa ``SELECT pg_notify(canal, payload)`` na MESMA ``AsyncSession`` do caso de
uso — entra na transação autobegun corrente e o Postgres só ENTREGA a notificação
no COMMIT (descarta em rollback). Assim o sinal é atômico com a mutação de domínio
(RNF-017) e nunca "vaza" um evento de uma transição que deu rollback.

``NOTIFY`` não exige privilégio (não há GRANT de canal) nem sofre RLS — funciona
sob o ``SET LOCAL ROLE authenticated`` da sessão de request. O payload é uma
constante GENÉRICA (``domain/eventos.py``): nada de dado por perfil trafega pelo
canal. Mesmo padrão de escrita do ``SqlAlchemyAuditLogRepository``.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.event_bus import EventBusPort
from src.domain.eventos import CANAL_EVENTOS_PROVAS, EVENTO_PROVA_MUDOU

# Bind puro (sem ``::cast``): o ``::`` logo após um bind confunde o parser do
# ``text()`` — mesma nota de ``audit_log_repository.py``.
_SQL_NOTIFY = text("SELECT pg_notify(:canal, :payload)")


class PgNotifyEventBus(EventBusPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publicar_mudanca_de_prova(self) -> None:
        await self._session.execute(
            _SQL_NOTIFY,
            {"canal": CANAL_EVENTOS_PROVAS, "payload": EVENTO_PROVA_MUDOU},
        )


__all__ = ["PgNotifyEventBus"]
