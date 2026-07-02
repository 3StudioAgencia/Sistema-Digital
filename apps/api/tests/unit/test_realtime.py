"""Realtime do dashboard (etapa 3) — hub in-process + conversão de DSN (offline).

O ``EventoHub`` é pura mecânica de fan-out (sem I/O), então é testável offline:
foco no contrato que protege o servidor — ``broadcast`` nunca bloqueia nem levanta
(``put_nowait`` + drop em fila cheia), e ``desassinar`` de fato para de receber
(sem filas órfãs). A entrega real do ``NOTIFY`` (publisher → listener) é @db em
``tests/integration/test_realtime_notify.py``.
"""

from src.infrastructure.config import to_asyncpg_dsn
from src.infrastructure.realtime import TAMANHO_FILA, EventoHub


async def test_hub_broadcast_sinaliza_todos_os_assinantes() -> None:
    hub = EventoHub()
    q1, q2 = hub.assinar(), hub.assinar()
    assert hub.total_assinantes == 2
    hub.broadcast()
    assert q1.qsize() == 1
    assert q2.qsize() == 1
    assert q1.get_nowait() is None


async def test_hub_desassinar_para_de_receber() -> None:
    hub = EventoHub()
    q = hub.assinar()
    hub.desassinar(q)
    assert hub.total_assinantes == 0
    hub.broadcast()
    assert q.qsize() == 0  # já não recebe — sem fila órfã sendo alimentada


async def test_hub_broadcast_sem_assinantes_e_noop() -> None:
    hub = EventoHub()
    hub.broadcast()  # degradação: nenhum stream aberto → nada acontece, sem erro
    assert hub.total_assinantes == 0


async def test_hub_fila_cheia_descarta_sem_bloquear_nem_levantar() -> None:
    """Cliente lento não pode derrubar o fan-out: ``broadcast`` satura a fila no
    teto e descarta o excedente (o sinal já enfileirado basta para o refetch)."""
    hub = EventoHub()
    q = hub.assinar()
    for _ in range(TAMANHO_FILA + 5):
        hub.broadcast()  # nunca bloqueia nem levanta QueueFull
    assert q.qsize() == TAMANHO_FILA


def test_to_asyncpg_dsn_remove_sufixo_do_driver() -> None:
    assert to_asyncpg_dsn("postgresql+asyncpg://u:p@h:5432/db") == "postgresql://u:p@h:5432/db"


def test_to_asyncpg_dsn_sem_sufixo_fica_intacto() -> None:
    assert to_asyncpg_dsn("postgresql://u:p@h/db") == "postgresql://u:p@h/db"
