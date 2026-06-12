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

import json
import logging
from collections.abc import AsyncIterator, Mapping
from datetime import datetime
from typing import Any, cast

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.application.ports.unit_of_work import UnitOfWork
from src.infrastructure.config import Settings

logger = logging.getLogger("rastreio.database")


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


def create_direct_engine(settings: Settings) -> AsyncEngine:
    """Engine async sobre a conexão DIRETA/sessão (porta 5432, ``MIGRATIONS_DATABASE_URL``).

    Para tarefas *one-shot* fora do ciclo de request — caso do keep-alive (W0-C02,
    ADR-015): abre UMA conexão curta, faz um ``SELECT`` trivial e devolve.
    ``NullPool`` porque o processo é efêmero (não há pool a manter); a conexão
    direta evita qualquer peculiaridade do pooler de transação para um único
    comando. Em dev local as duas URLs apontam para o mesmo Postgres.
    """
    return create_async_engine(
        settings.migrations_database_url,
        poolclass=NullPool,
        pool_pre_ping=False,  # processo de vida curta: pre-ping seria custo morto
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Fábrica de sessões compartilhada pelo app (estado de processo, não de usuário).

    ``expire_on_commit=False``: objetos permanecem utilizáveis após o commit,
    evitando reloads implícitos (princípio do mínimo de requisições, RNF-020).
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def fetch_db_time(engine: AsyncEngine) -> datetime:
    """Núcleo do *ping* read-only: abre uma conexão curta e lê o ``now()`` do
    servidor Postgres.

    É a ÚNICA função com a lógica de ida ao banco do *ping* — reutilizada pelo
    readiness (via ``ping``) e pelo keep-alive (W0-C02), atendendo ao DRY
    (CLAUDE.md §3). Devolve o instante do servidor (útil ao keep-alive como
    prova de atividade) e **levanta** a exceção de conexão para quem precisa
    distinguir falha (o keep-alive a converte em status/exit code); ``ping``
    envelopa e degrada para ``False``.
    """
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT now()"))
        return cast(datetime, result.scalar_one())


async def ping(engine: AsyncEngine) -> bool:
    """Ping read-only ao banco — usado pelo readiness check. Nunca levanta exceção."""
    try:
        await fetch_db_time(engine)
    except Exception as exc:
        # O readiness reportará "down"; deixe um rastro diagnóstico (RNF-024) em
        # vez de descartar a causa em silêncio. Só o TIPO da exceção — nunca
        # str(exc), que pode conter a connection string (mesmo padrão do
        # keep-alive). O request_id corrente já correlaciona a linha.
        logger.warning(
            "ping ao banco falhou",
            extra={"event": "db_ping_failed", "error_type": type(exc).__name__},
        )
        return False
    return True


def propagar_claims_rls(session: AsyncSession, claims: Mapping[str, Any]) -> None:
    """Propaga os claims do JWT verificado para CADA transação da sessão (ADR-008).

    Anexa um listener ``after_begin``: no início de toda transação — leitura OU
    escrita, **inclusive as auto-begin** dos repositórios — executa
    ``set_config('request.jwt.claims', <json>, true)`` + ``SET LOCAL ROLE
    authenticated``. Assim, as policies de RLS (que leem ``app_current_claims()``,
    o mesmo conteúdo que ``auth.jwt()`` expõe no Supabase) valem também para as
    consultas servidas pelo FastAPI — sem esta propagação, a conexão *owner*
    faria *bypass* da RLS.

    Por transação (``SET LOCAL`` / ``is_local=true``): seguro com o pooler em modo
    transação (ADR-007), em que cada transação pode cair numa conexão diferente.
    O listener é ligado à sessão concreta (uma por requisição), nunca à fábrica —
    sessões de seed/CLI que rodam como *owner* permanecem fora da RLS de propósito.

    Ordem deliberada: claims ANTES da troca de role (o ``set_config`` corre como
    owner; o GUC local sobrevive à troca de role e é lido pelas policies).
    """
    claims_json = json.dumps(dict(claims))

    @event.listens_for(session.sync_session, "after_begin")
    def _aplicar(_sess: Any, _trans: Any, connection: Any) -> None:
        connection.execute(
            text("SELECT set_config('request.jwt.claims', :c, true)"),
            {"c": claims_json},
        )
        connection.execute(text("SET LOCAL ROLE authenticated"))


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Unit of Work por requisição sobre uma ``AsyncSession``.

    A propagação de claims para a RLS (ADR-008) é feita por
    ``propagar_claims_rls`` (listener ``after_begin`` da sessão), e NÃO aqui:
    repositórios fazem leituras que auto-iniciam transações sem passar pelo
    ``begin()``, então o hook de propagação precisa ser por-transação, não
    por-``begin()``. A UoW segue responsável apenas pela fronteira atômica
    (RNF-017).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Exposta para os repositórios concretos (adapters), não para casos de uso."""
        return self._session

    async def begin(self) -> None:
        """Abre a transação explícita do caso de uso (escrita)."""
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
