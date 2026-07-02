"""Realtime do dashboard (etapa 3 da migração): fan-out in-process alimentado por
Postgres ``LISTEN/NOTIFY``.

Dois componentes, UM de cada por processo. O backend é single-process hoje; se
escalar para N processos/réplicas, cada um mantém o SEU listener e o SEU hub — e
como cada processo abre o próprio ``LISTEN`` na MESMA instância Postgres, TODOS
recebem o ``NOTIFY``. O fan-out fica correto sem afinidade de sessão (o bus é o
Postgres), preservando o pilar "stateless / escala horizontal" (CLAUDE.md §3.2) e
o custo R$ 0 (sem Redis).

- ``EventoHub`` — registro de assinantes in-process. Cada conexão SSE assina e
  recebe uma ``asyncio.Queue`` *bounded*; ``broadcast`` empurra um sinal a todas as
  filas com ``put_nowait`` e **descarta** em fila cheia (nunca bloqueia o fan-out
  nem espera um cliente lento — head-of-line blocking derrubaria todos). Perder um
  sinal intermediário é inócuo: o payload é genérico e o próximo refetch reconcilia.
- ``PgEventListener`` — mantém UMA conexão asyncpg dedicada em ``LISTEN`` no canal
  de eventos e chama ``hub.broadcast()`` a cada ``NOTIFY``. Conexão DIRETA/sessão
  (``migrations_database_url``): ``LISTEN`` não sobrevive a um pooler em modo
  transação. Resiliente: reconecta com backoff se a conexão cair e re-``LISTEN``, e
  emite um sinal de "rebusca" ao (re)conectar — fechando a janela em que ``NOTIFY``
  possa ter sido perdido enquanto estava fora do ar (o Postgres não persiste
  notificações).
"""

import asyncio
import contextlib
import logging
from typing import Any

import asyncpg

from src.domain.eventos import CANAL_EVENTOS_PROVAS
from src.infrastructure.config import Settings, to_asyncpg_dsn

logger = logging.getLogger("rastreio.realtime")

# Fila pequena por assinante: só precisamos saber "há sinal pendente"; sinais
# excedentes são redundantes (o refetch é da agregação inteira).
TAMANHO_FILA = 8
# Ping periódico da conexão do listener: detecta queda (o SELECT levanta) para
# disparar a reconexão. Calibrado ao mínimo (RNF-023).
_INTERVALO_KEEPALIVE_S = 30.0
_BACKOFF_INICIAL_S = 0.5
_BACKOFF_MAX_S = 30.0


class EventoHub:
    """Fan-out in-process de sinais de "prova mudou" para conexões SSE abertas."""

    def __init__(self) -> None:
        self._assinantes: set[asyncio.Queue[None]] = set()

    def assinar(self) -> "asyncio.Queue[None]":
        """Registra uma conexão SSE e devolve a fila por onde ela recebe sinais."""
        fila: asyncio.Queue[None] = asyncio.Queue(maxsize=TAMANHO_FILA)
        self._assinantes.add(fila)
        return fila

    def desassinar(self, fila: "asyncio.Queue[None]") -> None:
        """Remove a fila no fim do stream (``finally`` do gerador) — sem órfãs."""
        self._assinantes.discard(fila)

    def broadcast(self) -> None:
        """Sinaliza todas as filas SEM bloquear (``put_nowait`` + drop em cheia)."""
        # Itera sobre uma cópia: um assinante pode se desassinar concorrentemente.
        for fila in tuple(self._assinantes):
            try:
                fila.put_nowait(None)
            except asyncio.QueueFull:
                # Cliente lento com sinal já pendente — descarta: o sinal enfileirado
                # basta para disparar o refetch (o payload é genérico).
                pass

    @property
    def total_assinantes(self) -> int:
        return len(self._assinantes)


class PgEventListener:
    """Escuta ``NOTIFY`` numa conexão asyncpg dedicada e alimenta o ``EventoHub``."""

    def __init__(self, settings: Settings, hub: EventoHub) -> None:
        # asyncpg cru NÃO entende o sufixo ``+asyncpg`` do SQLAlchemy — converte.
        self._dsn = to_asyncpg_dsn(settings.migrations_database_url)
        self._hub = hub
        self._conn: Any = None
        self._backoff = _BACKOFF_INICIAL_S

    def _ao_notificar(self, *_: object) -> None:
        # Callback do asyncpg (roda no event loop): SÓ sinaliza o hub, sem I/O.
        self._hub.broadcast()

    async def run(self) -> None:
        """Loop resiliente: conecta, ``LISTEN``, mantém vivo; reconecta com backoff.

        Encerra limpo no cancelamento (shutdown) fechando a conexão."""
        while True:
            try:
                await self._conectar_e_escutar()
            except asyncio.CancelledError:
                await self._fechar()
                raise
            except Exception as exc:
                logger.warning(
                    "listener de realtime caiu — reconectando",
                    extra={
                        "event": "realtime_listener_down",
                        "error_type": type(exc).__name__,
                    },
                )
                await self._fechar()
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, _BACKOFF_MAX_S)

    async def _conectar_e_escutar(self) -> None:
        self._conn = await asyncpg.connect(dsn=self._dsn)
        await self._conn.add_listener(CANAL_EVENTOS_PROVAS, self._ao_notificar)
        # Conexão saudável: zera o backoff.
        self._backoff = _BACKOFF_INICIAL_S
        # (Re)conectou: sinaliza "rebusca" para fechar a janela em que NOTIFYs
        # possam ter sido perdidos enquanto o listener estava fora do ar.
        self._hub.broadcast()
        logger.info("listener de realtime conectado", extra={"event": "realtime_listener_up"})
        # Mantém a conexão viva e detecta queda: o SELECT levanta se ela morreu,
        # caindo no loop de reconexão. asyncpg entrega os NOTIFY pelo reader de
        # fundo — o SELECT é só liveness, não é polling de eventos (RNF-021).
        while True:
            await asyncio.sleep(_INTERVALO_KEEPALIVE_S)
            await self._conn.execute("SELECT 1")

    async def _fechar(self) -> None:
        conn = self._conn
        self._conn = None
        if conn is not None:
            # Fechamento best-effort: a conexão pode já estar morta (o motivo da
            # reconexão) — não deixar a limpeza mascarar/atrapalhar o loop.
            with contextlib.suppress(Exception):
                await conn.close()


__all__ = ["TAMANHO_FILA", "EventoHub", "PgEventListener"]
