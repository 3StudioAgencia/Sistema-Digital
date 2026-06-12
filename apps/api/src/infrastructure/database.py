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
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, cast

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

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


# Chave em ``session.info`` onde os claims do JWT ficam registrados para a RLS.
# A presença dela distingue uma sessão de REQUEST (que DEVE rodar sob
# ``authenticated`` com claims) de uma sessão de sistema (seed/CLI/migrations,
# que roda como owner de propósito).
_RLS_CLAIMS_KEY = "rls_claims"


class _RlsSyncSession(Session):
    """Sessão síncrona dedicada às requisições, com o guarda *fail-closed* da RLS.

    Existe apenas para escopar o listener ``after_begin`` abaixo a ESTAS sessões
    (as criadas por ``create_request_session_factory``), sem afetar as sessões de
    sistema/seed que usam a ``Session`` padrão.
    """


@event.listens_for(_RlsSyncSession, "after_begin")
def _exigir_claims_rls(session: Session, _trans: Any, _connection: Any) -> None:
    """Guarda *fail-closed*: nenhuma transação de uma sessão de request pode
    começar sem claims propagados.

    Sem este guarda, esquecer a propagação faria a consulta rodar com o role de
    conexão (owner + ``BYPASSRLS`` no Supabase) e VAZAR dados entre escopos em
    silêncio (fail-**open**). Aqui, esquecer **levanta** — o erro é alto e cedo,
    não um vazamento silencioso (W1-A-001). A propagação em si é feita pelo
    listener de ``propagar_claims_rls``; este apenas recusa a ausência de claims,
    de modo que o C06 (RLS de ``provas``) herde o padrão *fail-closed*.
    """
    if not session.info.get(_RLS_CLAIMS_KEY):
        raise RuntimeError(
            "Sessão de request iniciou transação sem claims de RLS propagados: a "
            "consulta rodaria como owner (fail-open). Abra a sessão via "
            "abrir_sessao_rls()/propagar_claims_rls() antes de qualquer query."
        )


def create_request_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Fábrica das sessões de REQUEST — toda sessão daqui é *fail-closed* na RLS.

    Diferente de ``create_session_factory`` (sessões de sistema/owner: seed, CLI,
    bootstrap), as sessões produzidas aqui recusam iniciar uma transação sem
    claims propagados (``_RlsSyncSession`` + guarda ``after_begin``). É a ÚNICA
    fábrica que o caminho HTTP deve usar; o C06 herda o padrão *fail-closed* sem
    reimplementar a propagação em cada wiring (W1-A-001).
    """
    return async_sessionmaker(engine, expire_on_commit=False, sync_session_class=_RlsSyncSession)


def propagar_claims_rls(session: AsyncSession, claims: Mapping[str, Any]) -> None:
    """Propaga os claims do JWT verificado para CADA transação da sessão (ADR-008).

    Registra os claims em ``session.info`` (lido pelo guarda *fail-closed* das
    sessões de request) e anexa um listener ``after_begin``: no início de toda
    transação — leitura OU escrita, **inclusive as auto-begin** dos repositórios —
    executa ``set_config('request.jwt.claims', <json>, true)`` + ``SET LOCAL ROLE
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
    claims_dict = dict(claims)
    session.sync_session.info[_RLS_CLAIMS_KEY] = claims_dict
    claims_json = json.dumps(claims_dict)

    @event.listens_for(session.sync_session, "after_begin")
    def _aplicar(sess: Any, _trans: Any, connection: Any) -> None:
        # Fail-closed também aqui: claims vazios não devem propagar como owner.
        if not sess.info.get(_RLS_CLAIMS_KEY):
            raise RuntimeError(
                "propagar_claims_rls chamado sem claims — a sessão rodaria como owner (fail-open)."
            )
        connection.execute(
            text("SELECT set_config('request.jwt.claims', :c, true)"),
            {"c": claims_json},
        )
        connection.execute(text("SET LOCAL ROLE authenticated"))


@asynccontextmanager
async def abrir_sessao_rls(
    factory: async_sessionmaker[AsyncSession], claims: Mapping[str, Any]
) -> AsyncIterator[AsyncSession]:
    """Abre uma sessão de request com a RLS ligada (ADR-008) — ponto ÚNICO.

    Centraliza ``factory() + propagar_claims_rls`` para que todo serviço por
    requisição (C04 e, daqui em diante, o C06 e seguintes) honre a RLS por
    padrão, sem reimplementar a propagação em cada wiring (W1-A-001). Use sempre
    com uma fábrica de ``create_request_session_factory`` para herdar o guarda
    *fail-closed*.
    """
    async with factory() as session:
        propagar_claims_rls(session, claims)
        yield session


# SqlAlchemyUnitOfWork morava aqui; movida para adapters/outbound/db/unit_of_work.py
# no W2-C06 (W0-A-018/ADR-017 — implementação de porta mora em adapters).


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Gerador de sessão por request (uma sessão = uma requisição).

    O wiring concreto como dependência FastAPI acontece no composition root —
    esta função fica aqui para ser reutilizada também fora do HTTP (jobs, CLI).
    """
    async with session_factory() as session:
        yield session
