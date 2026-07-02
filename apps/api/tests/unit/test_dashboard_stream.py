"""Gerador SSE do dashboard (etapa 3) — comportamento do fluxo, offline.

Cobre o contrato do stream sem rede/DB: sinaliza "mudou" a cada evento do hub,
heartbeat por timeout, encerra com "expira" perto do ``exp`` do token e no
disconnect do cliente, e SEMPRE limpa a inscrição no hub (``finally``) — sem filas
órfãs. O handshake (auth/autorização) e o content-type são @db em
``tests/integration/test_dashboard_stream_endpoints.py``.
"""

import time

import pytest
from src.adapters.inbound.http import dashboard as mod
from src.domain.eventos import EVENTO_PROVA_MUDOU
from src.infrastructure.realtime import EventoHub


class _FakeRequest:
    """Stub de ``Request`` — o gerador só chama ``is_disconnected``."""

    def __init__(self, disconnected: bool = False) -> None:
        self._d = disconnected

    async def is_disconnected(self) -> bool:
        return self._d


async def test_conectado_e_depois_mudou_no_broadcast() -> None:
    hub = EventoHub()
    exp = int(time.time()) + 3600
    agen = mod._gerar_eventos(_FakeRequest(), hub, exp)
    assert await agen.__anext__() == "event: conectado\ndata: ok\n\n"
    hub.broadcast()
    assert await agen.__anext__() == f"data: {EVENTO_PROVA_MUDOU}\n\n"
    await agen.aclose()
    assert hub.total_assinantes == 0  # finally desassinou


async def test_heartbeat_no_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_HEARTBEAT_S", 0.05)
    hub = EventoHub()
    exp = int(time.time()) + 3600
    agen = mod._gerar_eventos(_FakeRequest(), hub, exp)
    assert await agen.__anext__() == "event: conectado\ndata: ok\n\n"
    assert await agen.__anext__() == ": ping\n\n"
    await agen.aclose()
    assert hub.total_assinantes == 0


async def test_encerra_com_expira_perto_do_exp() -> None:
    hub = EventoHub()
    exp = int(time.time()) + 10  # < margem (60) → encerra já, mandando reconectar
    agen = mod._gerar_eventos(_FakeRequest(), hub, exp)
    assert await agen.__anext__() == "event: conectado\ndata: ok\n\n"
    assert await agen.__anext__() == "event: expira\ndata: reconnect\n\n"
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
    assert hub.total_assinantes == 0


async def test_encerra_no_disconnect() -> None:
    hub = EventoHub()
    exp = int(time.time()) + 3600
    agen = mod._gerar_eventos(_FakeRequest(disconnected=True), hub, exp)
    assert await agen.__anext__() == "event: conectado\ndata: ok\n\n"
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
    assert hub.total_assinantes == 0
