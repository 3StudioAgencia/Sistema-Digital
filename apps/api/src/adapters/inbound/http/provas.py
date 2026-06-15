"""Endpoints de provas digitais (W2-C06/C07/C08) — RF-001/002/003, RN-007, US-001.

Gate por endpoint (Matriz §7):
- **CRIAÇÃO** (``POST /provas``) é EXCLUSIVA do Administrador ("Criar Prova"):
  gate ``CRIAR_PROVA`` dentro de ``get_provas_service`` (uma sessão RLS por
  requisição — RNF-020).
- **LEITURA** — listagem (``GET /provas``), dropdown (``/provas/vendedores``),
  detalhe (``/provas/{id}``), arte (``/provas/{id}/arte``) e etiqueta
  (``/provas/{id}/etiqueta.pdf``) — é UNIVERSAL-em-escopo via
  ``get_provas_consulta_service`` (gate ``Recurso.PROVAS``); o ESCOPO de dado é
  da RLS de ``provas`` (W2-C08/DP-8: a etiqueta deixou de ser admin-only).

NÃO há endpoint de update nesta wave (DP-5 do C06): a rota é imutável (RN-007) e
as transições de status são do C11 — qualquer PATCH/PUT responde 405 por ausência.
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, Form, Query, Response, UploadFile, status
from pydantic import BaseModel

from src.adapters.inbound.http.dependencies import (
    get_provas_consulta_service,
    get_provas_service,
)
from src.application.ports.provas_repository import (
    PAGE_SIZE_MAXIMO,
    PAGE_SIZE_PADRAO,
    FiltrosProvas,
)
from src.application.provas import (
    CriarProva,
    ProvaListagem,
    ProvasConsultaService,
    ProvasService,
)
from src.domain.provas import ARTE_TAMANHO_MAXIMO, EstadoProva, Prova, Rota

router = APIRouter(prefix="/provas", tags=["provas"])


# ---------------------------------------------------------------------------
# Schemas (validação de FORMA na borda; REGRAS vivem no domínio/serviço)
# ---------------------------------------------------------------------------
class ProvaOut(BaseModel):
    id: str
    codigo: str
    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    rota: Rota
    status: EstadoProva
    created_at: datetime | None

    @classmethod
    def de_dominio(cls, p: Prova) -> Self:
        return cls(
            id=p.id,
            codigo=p.codigo,
            nome=p.nome,
            requerimento=p.requerimento,
            cliente=p.cliente,
            vendedor_id=p.vendedor_id,
            rota=p.rota,
            status=p.status,
            created_at=p.created_at,
        )


class ProvaListagemOut(BaseModel):
    """Linha da listagem (W2-C07): acrescenta o NOME do vendedor (resolvido pela
    projeção SECURITY DEFINER — DP-7) e ``finalizada_em`` ao ``ProvaOut``."""

    id: str
    codigo: str
    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    vendedor_nome: str | None
    rota: Rota
    status: EstadoProva
    created_at: datetime | None
    finalizada_em: datetime | None

    @classmethod
    def de_dominio(cls, item: ProvaListagem) -> Self:
        p = item.prova
        return cls(
            id=p.id,
            codigo=p.codigo,
            nome=p.nome,
            requerimento=p.requerimento,
            cliente=p.cliente,
            vendedor_id=p.vendedor_id,
            vendedor_nome=item.vendedor_nome,
            rota=p.rota,
            status=p.status,
            created_at=p.created_at,
            finalizada_em=p.finalizada_em,
        )


class PaginaProvasOut(BaseModel):
    items: list[ProvaListagemOut]
    total: int
    page: int
    page_size: int


class VendedorRefOut(BaseModel):
    id: str
    nome: str


class ProvaDetalheOut(BaseModel):
    """Detalhe da prova (W2-C08): ``ProvaListagemOut`` + ``ciclo_atual`` (DP-1).

    A arte NÃO vem aqui — é servida pelo proxy ``GET /provas/{id}/arte`` (DP-5),
    para não trafegar imagem dentro do JSON nem expor a key do R2."""

    id: str
    codigo: str
    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    vendedor_nome: str | None
    rota: Rota
    status: EstadoProva
    ciclo_atual: int
    created_at: datetime | None
    finalizada_em: datetime | None

    @classmethod
    def de_dominio(cls, item: ProvaListagem) -> Self:
        p = item.prova
        return cls(
            id=p.id,
            codigo=p.codigo,
            nome=p.nome,
            requerimento=p.requerimento,
            cliente=p.cliente,
            vendedor_id=p.vendedor_id,
            vendedor_nome=item.vendedor_nome,
            rota=p.rota,
            status=p.status,
            ciclo_atual=p.ciclo_atual,
            created_at=p.created_at,
            finalizada_em=p.finalizada_em,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=PaginaProvasOut)
async def listar(
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
    # Busca (RF-013): nome E/OU requerimento. Filtros combináveis (RF-014).
    busca: Annotated[str | None, Query(max_length=200)] = None,
    cliente: Annotated[str | None, Query(max_length=200)] = None,
    status_filtro: Annotated[EstadoProva | None, Query(alias="status")] = None,
    rota: Rota | None = None,
    vendedor_id: uuid.UUID | None = None,
    criada_de: date | None = None,
    criada_ate: date | None = None,
    finalizada_de: date | None = None,
    finalizada_ate: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAXIMO)] = PAGE_SIZE_PADRAO,
) -> PaginaProvasOut:
    """Listagem paginada server-side (RNF-019), ordenada por ``created_at`` desc.

    Acessível a todos os perfis; o ESCOPO de dado (Vendedor as próprias, Motorista
    as "Em Trânsito") é da RLS de ``provas`` (claims propagados — ADR-008). Query
    fora do escopo retorna simplesmente 0 registros (anti-enumeração)."""
    pagina = await service.listar(
        FiltrosProvas(
            busca=busca,
            cliente=cliente,
            status=status_filtro,
            rota=rota,
            vendedor_id=str(vendedor_id) if vendedor_id is not None else None,
            criada_de=criada_de,
            criada_ate=criada_ate,
            finalizada_de=finalizada_de,
            finalizada_ate=finalizada_ate,
            page=page,
            page_size=page_size,
        )
    )
    return PaginaProvasOut(
        items=[ProvaListagemOut.de_dominio(i) for i in pagina.items],
        total=pagina.total,
        page=pagina.page,
        page_size=pagina.page_size,
    )


@router.get("/vendedores", response_model=list[VendedorRefOut])
async def vendedores(
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
) -> list[VendedorRefOut]:
    """Vendedores em escopo (distintos das provas visíveis) para o dropdown de
    filtro — alimenta o "Vendedor: Todos" sem vazar nomes fora do escopo."""
    return [VendedorRefOut(id=v.id, nome=v.nome) for v in await service.vendedores()]


@router.post("", response_model=ProvaOut, status_code=status.HTTP_201_CREATED)
async def criar(
    service: Annotated[ProvasService, Depends(get_provas_service)],
    # multipart/form-data: campos obrigatórios do RF-001. ``pattern=r"\S"``
    # exige ao menos um caractere não-branco (Pydantic v2 usa re.search);
    # requerimento é numérico ancorado (decisão da sessão: texto de dígitos,
    # preserva zeros à esquerda). Rota ausente → 422 (validation_error).
    nome: Annotated[str, Form(min_length=1, max_length=200, pattern=r"\S")],
    requerimento: Annotated[str, Form(min_length=1, max_length=50, pattern=r"^\d{1,50}$")],
    cliente: Annotated[str, Form(min_length=1, max_length=200, pattern=r"\S")],
    vendedor_id: Annotated[uuid.UUID, Form()],
    rota: Annotated[Rota, Form()],
    arte: UploadFile,
    # Chave de idempotência gerada pelo cliente (RNF-015): reenvio após
    # resposta perdida converge para a prova já criada em vez de duplicar.
    prova_id: Annotated[uuid.UUID | None, Form()] = None,
) -> ProvaOut:
    """Criação ATÔMICA da prova (RNF-017): arte no R2 + INSERT com código único.

    Lê no MÁXIMO 10 MB + 1 byte do upload para a MEMÓRIA do processo; o teto
    do corpo inteiro da requisição (anti-DoS, inclusive pré-auth) é do
    ``BodyLimitMiddleware``.
    """
    conteudo = await arte.read(ARTE_TAMANHO_MAXIMO + 1)
    prova = await service.criar(
        CriarProva(
            nome=nome,
            requerimento=requerimento,
            cliente=cliente,
            vendedor_id=str(vendedor_id),
            rota=rota,
            prova_id=str(prova_id) if prova_id is not None else None,
        ),
        arte=conteudo,
        arte_content_type_declarado=arte.content_type,
    )
    return ProvaOut.de_dominio(prova)


@router.get("/{prova_id}", response_model=ProvaDetalheOut)
async def detalhe(
    prova_id: uuid.UUID,
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
) -> ProvaDetalheOut:
    """Detalhe de UMA prova (W2-C08) — página UNIVERSAL escopada pela RLS.

    Acessível a qualquer perfil ativo; o ESCOPO é da RLS de ``provas`` (claims
    propagados — ADR-008). Prova inexistente e prova fora do escopo retornam o
    MESMO 404 genérico (anti-enumeração — CLAUDE.md §11): a UI redireciona para a
    listagem e mostra um toast, sem revelar se a prova existe.
    """
    return ProvaDetalheOut.de_dominio(await service.obter(str(prova_id)))


@router.get("/{prova_id}/arte")
async def arte(
    prova_id: uuid.UUID,
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
) -> Response:
    """PROXY da arte do R2 privado (W2-C08/DP-5) — escopado pela RLS.

    O backend lê o objeto do R2 e streama os bytes: a key do R2 NUNCA é exposta
    ao cliente e não há URL pública. Fora do escopo / inexistente → MESMO 404
    genérico (a prova é resolvida antes de tocar o storage). ``Cache-Control:
    private`` permite cache só no navegador do próprio usuário."""
    dados, content_type = await service.obter_arte(str(prova_id))
    return Response(
        content=dados,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/{prova_id}/etiqueta.pdf")
async def etiqueta(
    prova_id: uuid.UUID,
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
) -> Response:
    """Etiqueta PDF sob demanda (RF-003) — 95 x 55 mm, com o código em destaque.

    UNIVERSAL-em-escopo (DP-8): qualquer perfil que ENXERGA a prova (RLS) pode
    imprimir a etiqueta dela. Prova inexistente e prova fora do escopo retornam o
    MESMO 404 genérico (anti-enumeração — a RLS não distingue e a borda também não).
    """
    pdf, codigo = await service.gerar_etiqueta(str(prova_id))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="etiqueta-{codigo}.pdf"'},
    )


__all__ = ["router"]
