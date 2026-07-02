"""Endpoint do Dashboard (W4-C16) — RF-015/RF-025/US-013.

``GET /dashboard`` (prefixo real SEM ``/api``) devolve TODOS os contadores do
painel + o breakdown de "Atrasadas" por vendedor + total, de UMA consulta unica
(RNF-022), escopados pela RLS de ``provas`` (cada perfil ve so os seus numeros —
Matriz §7). Pagina UNIVERSAL (``Recurso.DASHBOARD``): o gate da borda so exige
usuario ativo provisionado; o ESCOPO de dado e da RLS. O front mantem UMA
subscription Realtime e re-busca este endpoint (debounced) a cada evento — sem
polling (RNF-021).
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated, Self

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.adapters.inbound.http.auth import AuthenticatedUser, get_current_user
from src.adapters.inbound.http.dependencies import (
    autorizar_stream_dashboard,
    get_dashboard_service,
)
from src.application.dashboard import DashboardService
from src.domain.dashboard import AtrasadaVendedor, ContadoresDashboard
from src.domain.eventos import EVENTO_PROVA_MUDOU
from src.infrastructure.realtime import EventoHub

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class AtrasadaVendedorOut(BaseModel):
    vendedor_id: str
    vendedor_nome: str | None
    total: int

    @classmethod
    def de_dominio(cls, a: AtrasadaVendedor) -> Self:
        return cls(vendedor_id=a.vendedor_id, vendedor_nome=a.vendedor_nome, total=a.total)


class DashboardOut(BaseModel):
    """Contadores do painel (W4-C16). ``atrasadas_por_vendedor`` ja vem ordenado
    por contagem desc; o front anima o count-up (RF-025) e abre a listagem
    pre-filtrada (C07) ao clicar (DP-6)."""

    criadas_hoje: int
    com_vendedor: int
    aprovadas: int
    na_clicheria: int
    atrasadas_total: int
    atrasadas_por_vendedor: list[AtrasadaVendedorOut]

    @classmethod
    def de_dominio(cls, c: ContadoresDashboard) -> Self:
        return cls(
            criadas_hoje=c.criadas_hoje,
            com_vendedor=c.com_vendedor,
            aprovadas=c.aprovadas,
            na_clicheria=c.na_clicheria,
            atrasadas_total=c.atrasadas_total,
            atrasadas_por_vendedor=[
                AtrasadaVendedorOut.de_dominio(a) for a in c.atrasadas_por_vendedor
            ],
        )


@router.get("", response_model=DashboardOut)
async def contadores(
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> DashboardOut:
    """Contadores do Dashboard em tempo real (W4-C16) — consulta unica escopada.

    Acessivel a qualquer perfil ativo (Matriz §7: Dashboard universal); os numeros
    sao escopados pela RLS de ``provas`` (claims propagados — ADR-008). A regra de
    "Atrasada" e em horas uteis (seg-sex 07-18, fuso America/Sao_Paulo) com o limiar
    do C09 (DP-4); o breakdown de atrasadas por vendedor respeita o mesmo escopo
    (Vendedor ve so a si).
    """
    return DashboardOut.de_dominio(await service.contadores())


# ---------------------------------------------------------------------------
# Realtime (etapa 3 da migração): stream SSE do dashboard (substitui o Realtime do
# Supabase — ADR-113/ADR-114). Mão única servidor->navegador; o evento é GENÉRICO
# ("mudou") e o navegador rebusca ``GET /dashboard`` (escopado pela RLS). Sem
# polling (RNF-021): o push vem do Postgres LISTEN/NOTIFY via o ``EventoHub``.
# ---------------------------------------------------------------------------
# Keep-alive do stream: um comentário SSE periódico impede que um proxy derrube a
# conexão por idle timeout. Calibrado ao mínimo (RNF-023). O reverse proxy on-prem
# deve ter ``proxy_read_timeout`` > este intervalo (docs/realtime.md).
_HEARTBEAT_S = 20.0
# Fecha o stream ANTES de o access token (30 min) expirar, para o cliente renovar o
# cookie (POST /auth/refresh) e reabrir — o EventSource não faz refresh sozinho.
_MARGEM_EXPIRACAO_S = 60.0


async def _gerar_eventos(request: Request, hub: EventoHub, exp: int) -> AsyncIterator[str]:
    """Fluxo SSE: sinaliza "mudou" a cada evento do hub, com heartbeat por timeout,
    e ENCERRA pouco antes de o token expirar (o cliente renova+reabre). Limpa a
    inscrição no ``finally`` — sem filas órfãs no hub, mesmo em disconnect abrupto."""
    fila = hub.assinar()
    try:
        # Reconciliação imediata ao (re)conectar: o cliente rebusca de cara.
        yield "event: conectado\ndata: ok\n\n"
        while True:
            restante = exp - time.time() - _MARGEM_EXPIRACAO_S
            if restante <= 0:
                # Token quase expirando: manda reconectar (o cliente renova o cookie).
                yield "event: expira\ndata: reconnect\n\n"
                return
            if await request.is_disconnected():
                return
            try:
                await asyncio.wait_for(fila.get(), timeout=min(_HEARTBEAT_S, restante))
                yield f"data: {EVENTO_PROVA_MUDOU}\n\n"
            except TimeoutError:
                yield ": ping\n\n"  # comentário SSE (ignorado pelo EventSource)
    finally:
        hub.desassinar(fila)


@router.get("/stream")
async def stream(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> StreamingResponse:
    """Stream SSE de sinais "prova mudou" (W4-C16 / etapa 3 da migração).

    Autentica pelo cookie ``access_token`` (via ``get_current_user``) e autoriza
    ``Recurso.DASHBOARD`` numa sessão RLS CURTA (não a mantém pela vida do stream —
    ``NullPool``). O canal NÃO carrega números: o navegador rebusca ``GET /dashboard``
    (escopado pela RLS) a cada sinal, preservando o escopo por perfil.
    ``X-Accel-Buffering: no`` desliga o buffering do reverse proxy (SSE exige
    resposta chunked, sem buffer)."""
    await autorizar_stream_dashboard(request, user)
    hub: EventoHub = request.app.state.dashboard_hub
    exp = int(user.claims["exp"])
    return StreamingResponse(
        _gerar_eventos(request, hub, exp),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
