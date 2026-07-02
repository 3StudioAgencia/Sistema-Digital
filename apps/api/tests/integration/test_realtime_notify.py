"""Realtime do dashboard (etapa 3) — entrega do ``pg_notify`` @db (Postgres real).

Prova o contrato de atomicidade que sustenta todo o desenho (ADR-114): o sinal é
emitido pela MESMA sessão da mutação e o Postgres só o ENTREGA no COMMIT (descarta
em rollback). Um listener asyncpg cru (como o ``PgEventListener`` de produção)
recebe o ``NOTIFY``; o publisher é o ``PgNotifyEventBus`` real.
"""

import asyncio
import contextlib

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from src.adapters.outbound.db.event_bus_pg import PgNotifyEventBus
from src.domain.eventos import CANAL_EVENTOS_PROVAS, EVENTO_PROVA_MUDOU
from src.infrastructure.config import Settings, to_asyncpg_dsn
from src.infrastructure.realtime import EventoHub, PgEventListener

pytestmark = pytest.mark.db


async def _abrir_listener(dsn: str) -> tuple[asyncpg.Connection, "asyncio.Queue[str]"]:
    fila: asyncio.Queue[str] = asyncio.Queue()
    conn = await asyncpg.connect(dsn=dsn)
    # Callback do asyncpg: (connection, pid, channel, payload) — guarda o payload.
    await conn.add_listener(CANAL_EVENTOS_PROVAS, lambda *args: fila.put_nowait(args[-1]))
    return conn, fila


async def test_pg_notify_entregue_no_commit(database_url: str) -> None:
    dsn = to_asyncpg_dsn(database_url)
    conn, fila = await _abrir_listener(dsn)
    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await PgNotifyEventBus(session).publicar_mudanca_de_prova()
            await session.commit()
        payload = await asyncio.wait_for(fila.get(), timeout=5)
        assert payload == EVENTO_PROVA_MUDOU
    finally:
        await conn.close()
        await engine.dispose()


async def test_pg_notify_nao_entregue_em_rollback(database_url: str) -> None:
    dsn = to_asyncpg_dsn(database_url)
    conn, fila = await _abrir_listener(dsn)
    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await PgNotifyEventBus(session).publicar_mudanca_de_prova()
            await session.rollback()
        # Nada deve chegar: o rollback descartou a notificação enfileirada.
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(fila.get(), timeout=1)
    finally:
        await conn.close()
        await engine.dispose()


async def test_listener_conecta_e_entrega_notify_ao_hub(database_url: str) -> None:
    """Ponta-a-ponta do lado servidor (sem HTTP): o ``PgEventListener`` real conecta
    (conversão de DSN + ``add_listener``) e, ao receber um ``NOTIFY``, chama
    ``hub.broadcast()`` — que chega à fila de um assinante. Cobre o elo que os testes
    ASGI não exercitam (o listener asyncpg de produção contra o Postgres real)."""
    hub = EventoHub()
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=database_url,
        migrations_database_url=database_url,
    )
    listener = PgEventListener(settings, hub)
    fila = hub.assinar()
    task = asyncio.create_task(listener.run())
    try:
        # Ao (re)conectar o listener emite um broadcast sintético de "rebusca".
        await asyncio.wait_for(fila.get(), timeout=5)
        # Emite um NOTIFY real por OUTRA conexão — o listener deve recebê-lo.
        emissor = await asyncpg.connect(dsn=to_asyncpg_dsn(database_url))
        try:
            await emissor.execute(
                "SELECT pg_notify($1, $2)", CANAL_EVENTOS_PROVAS, EVENTO_PROVA_MUDOU
            )
        finally:
            await emissor.close()
        await asyncio.wait_for(fila.get(), timeout=5)  # sinal do NOTIFY chegou ao hub
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
