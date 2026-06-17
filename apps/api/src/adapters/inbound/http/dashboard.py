"""Endpoint do Dashboard (W4-C16) — RF-015/RF-025/US-013.

``GET /dashboard`` (prefixo real SEM ``/api``) devolve TODOS os contadores do
painel + o breakdown de "Atrasadas" por vendedor + total, de UMA consulta unica
(RNF-022), escopados pela RLS de ``provas`` (cada perfil ve so os seus numeros —
Matriz §7). Pagina UNIVERSAL (``Recurso.DASHBOARD``): o gate da borda so exige
usuario ativo provisionado; o ESCOPO de dado e da RLS. O front mantem UMA
subscription Realtime e re-busca este endpoint (debounced) a cada evento — sem
polling (RNF-021).
"""

from typing import Annotated, Self

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.adapters.inbound.http.dependencies import get_dashboard_service
from src.application.dashboard import DashboardService
from src.domain.dashboard import AtrasadaVendedor, ContadoresDashboard

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


__all__ = ["router"]
