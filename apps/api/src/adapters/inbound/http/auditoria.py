"""Endpoints do Log de Auditoria (W6-C20) — RNF-006 (ampliado, DP-1=C) / §7.

EXCLUSIVO do 3Studio (flag ``administrador`` — Matriz §7 "Log de Auditoria" ●○○○):
TODOS os endpoints passam por ``get_auditoria_service``, que gateia por
``Recurso.LOG_AUDITORIA`` → 403 ao não-admin (camada inferior; a superior é o
``proxy.ts`` + a sidebar). Prefixo real ``/auditoria`` (SEM ``/api``). READ-ONLY: não
há rota de mutação do log — a imutabilidade é estrutural (append-only + chain).

- ``GET /auditoria`` — listagem paginada/filtrada (master-detail do design);
- ``GET /auditoria/atores`` — atores distintos para o dropdown "Ator";
- ``POST /auditoria/verificar-integridade`` — recomputa o chain (tamper-evidence).
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.adapters.inbound.http.dependencies import get_auditoria_service
from src.application.auditoria import AuditoriaService
from src.domain.auditoria import (
    PAGE_SIZE_MAXIMO,
    PAGE_SIZE_PADRAO,
    AtorRef,
    EventoAuditoria,
    FiltrosAuditoria,
    Ordem,
    RegistroAuditoria,
    ResultadoIntegridade,
)
from src.domain.provas import EstadoProva
from src.domain.state_machine.enums import Acao
from src.domain.usuarios import Setor

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


def filtros_auditoria(
    evento: Annotated[list[EventoAuditoria] | None, Query()] = None,
    ator_id: uuid.UUID | None = None,
    busca: Annotated[str | None, Query(max_length=200)] = None,
    de: date | None = None,
    ate: date | None = None,
    ordem: Ordem = "recentes",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAXIMO)] = PAGE_SIZE_PADRAO,
) -> FiltrosAuditoria:
    """Barra de filtros do design (DP-2) → ``FiltrosAuditoria``.

    ``evento`` aceita MÚLTIPLOS valores (``?evento=a&evento=b``); o dropdown manda
    um. Período por dia (De/Até). ``ordem`` = Recentes (desc) / Antigos (asc)."""
    return FiltrosAuditoria(
        eventos=tuple(evento) if evento else (),
        ator_id=str(ator_id) if ator_id is not None else None,
        busca=busca,
        de=de,
        ate=ate,
        ordem=ordem,
        page=page,
        page_size=page_size,
    )


Filtros = Annotated[FiltrosAuditoria, Depends(filtros_auditoria)]
Service = Annotated[AuditoriaService, Depends(get_auditoria_service)]


# ---------------------------------------------------------------------------
# Schemas (espelham os dataclasses do domínio)
# ---------------------------------------------------------------------------
class RegistroAuditoriaOut(BaseModel):
    id: str
    seq: int
    evento: EventoAuditoria
    ator_id: str
    ator_nome: str | None
    ator_setor: Setor | None
    prova_id: str | None
    prova_codigo: str | None
    prova_cliente: str | None
    prova_requerimento: str | None
    acao: Acao | None
    estado_origem: EstadoProva | None
    estado_destino: EstadoProva | None
    ciclo: int | None
    motivo: str | None
    ip: str | None
    origem: str | None
    created_at: datetime
    hash: str

    @classmethod
    def de_dominio(cls, r: RegistroAuditoria) -> Self:
        return cls(
            id=r.id,
            seq=r.seq,
            evento=r.evento,
            ator_id=r.ator_id,
            ator_nome=r.ator_nome,
            ator_setor=r.ator_setor,
            prova_id=r.prova_id,
            prova_codigo=r.prova_codigo,
            prova_cliente=r.prova_cliente,
            prova_requerimento=r.prova_requerimento,
            acao=r.acao,
            estado_origem=r.estado_origem,
            estado_destino=r.estado_destino,
            ciclo=r.ciclo,
            motivo=r.motivo,
            ip=r.ip,
            origem=r.origem,
            created_at=r.created_at,
            hash=r.hash,
        )


class PaginaAuditoriaOut(BaseModel):
    items: list[RegistroAuditoriaOut]
    total: int
    page: int
    page_size: int


class AtorOut(BaseModel):
    id: str
    nome: str | None

    @classmethod
    def de_dominio(cls, a: AtorRef) -> Self:
        return cls(id=a.id, nome=a.nome)


class IntegridadeOut(BaseModel):
    """Veredito da verificação do chain (DP-4)."""

    intacto: bool
    total: int
    quebrou_em: int | None

    @classmethod
    def de_dominio(cls, r: ResultadoIntegridade) -> Self:
        return cls(intacto=r.intacto, total=r.total, quebrou_em=r.quebrou_em)


# ---------------------------------------------------------------------------
# Endpoints — todos 3Studio-only (gate no service); read-only
# ---------------------------------------------------------------------------
@router.get("", response_model=PaginaAuditoriaOut)
async def listar(service: Service, filtros: Filtros) -> PaginaAuditoriaOut:
    """Listagem do log (master-detail do design): server-side, sem N+1. O escopo
    3Studio é do gate + RLS; a UI só consulta."""
    pagina = await service.listar(filtros)
    return PaginaAuditoriaOut(
        items=[RegistroAuditoriaOut.de_dominio(r) for r in pagina.items],
        total=pagina.total,
        page=pagina.page,
        page_size=pagina.page_size,
    )


@router.get("/atores", response_model=list[AtorOut])
async def atores(service: Service) -> list[AtorOut]:
    """Atores distintos do log (id + nome) para o dropdown "Ator"."""
    return [AtorOut.de_dominio(a) for a in await service.atores()]


@router.post("/verificar-integridade", response_model=IntegridadeOut)
async def verificar_integridade(service: Service) -> IntegridadeOut:
    """Recomputa o chain do log e devolve a 1ª linha divergente (tamper-evidence).

    READ-ONLY: a verificação NÃO altera o log — apenas o recomputa e compara. POST
    porque dispara um trabalho (recálculo), não um recurso cacheável."""
    return IntegridadeOut.de_dominio(await service.verificar())


__all__ = ["router"]
