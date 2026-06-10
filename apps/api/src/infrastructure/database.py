"""Acesso assíncrono ao PostgreSQL — engine, sessão por request e Unit of Work.

Estratégia de conexão (ADR-007, confirmada nesta wave):

- RUNTIME → pooler de transação do Supabase (porta 6543, PgBouncer).
  O pooling fica no PgBouncer; do lado da app usa-se ``NullPool`` (uma conexão
  por uso, devolvida imediatamente) e caches de prepared statement DESLIGADOS,
  pois em modo transação o PgBouncer pode entregar a mesma conexão a sessões
  diferentes — prepared statements nomeados colidiriam.
- MIGRATIONS → conexão direta (porta 5432), configurada em ``migrations/env.py``
  com ``MIGRATIONS_DATABASE_URL`` (DDL exige recursos de sessão).

Em dev local (docker compose) as duas URLs apontam para a mesma instância — a
configuração de runtime é segura também contra Postgres direto, apenas abre mão
do cache de statements.
"""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.application.ports.unit_of_work import UnitOfWork
from src.infrastructure.config import Settings


def create_runtime_engine(settings: Settings) -> AsyncEngine:
    """Engine async do runtime, segura para PgBouncer em modo transação."""
    connect_args: dict[str, Any] = {
        # Cache de statements do asyncpg — OFF (PgBouncer transaction mode).
        "statement_cache_size": 0,
        # Cache de prepared statements do dialeto asyncpg do SQLAlchemy — OFF.
        "prepared_statement_cache_size": 0,
    }
    return create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args=connect_args,
        pool_pre_ping=False,  # NullPool não reusa conexões; pre-ping seria custo morto
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Fábrica de sessões compartilhada pelo app (estado de processo, não de usuário).

    ``expire_on_commit=False``: objetos permanecem utilizáveis após o commit,
    evitando reloads implícitos (princípio do mínimo de requisições, RNF-020).
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def ping(engine: AsyncEngine) -> bool:
    """``SELECT 1`` — usado pelo readiness check. Nunca levanta exceção."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Unit of Work por requisição sobre uma ``AsyncSession``.

    PONTO DE EXTENSÃO (ADR-008 — Wave 1/C05, NÃO implementar agora):
    a propagação de claims para a RLS acontecerá em ``begin()``, executando
    ``SET LOCAL request.jwt.claims = :claims`` (e ``SET LOCAL ROLE``) dentro da
    transação recém-aberta, antes de qualquer query do caso de uso. A assinatura
    ``begin(claims=...)`` absorve isso sem mudança estrutural nos casos de uso.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Exposta para os repositórios concretos (adapters), não para casos de uso."""
        return self._session

    async def begin(self) -> None:
        """Abre a transação. (Futuro: recebe claims e executa SET LOCAL — ADR-008.)"""
        if not self._session.in_transaction():
            await self._session.begin()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Gerador de sessão por request (uma sessão = uma requisição).

    O wiring concreto como dependência FastAPI acontece no composition root —
    esta função fica aqui para ser reutilizada também fora do HTTP (jobs, CLI).
    """
    async with session_factory() as session:
        yield session
