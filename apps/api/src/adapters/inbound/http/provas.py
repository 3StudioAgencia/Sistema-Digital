"""Endpoints de provas digitais (W2-C06) — RF-001/002/003, RN-007, US-001.

Ambos os endpoints são EXCLUSIVOS do Administrador (Matriz §7, "Criar Prova"):
a etiqueta pertence ao fluxo de criação. O gate é aplicado dentro de
``get_provas_service`` (uma única sessão RLS por requisição — RNF-020).

NÃO há endpoint de update nesta wave (DP-5): a rota é imutável (RN-007) e as
transições de status são do C11 — qualquer PATCH/PUT responde 405 por ausência.
"""

import uuid
from datetime import datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, Form, Response, UploadFile, status
from pydantic import BaseModel

from src.adapters.inbound.http.dependencies import get_provas_service
from src.application.provas import CriarProva, ProvasService
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
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


@router.get("/{prova_id}/etiqueta.pdf")
async def etiqueta(
    prova_id: uuid.UUID,
    service: Annotated[ProvasService, Depends(get_provas_service)],
) -> Response:
    """Etiqueta PDF sob demanda (DP-7) — 95 x 55 mm, com o código em destaque.

    Prova inexistente e prova fora do escopo retornam o MESMO 404 genérico
    (anti-enumeração — a RLS não distingue e a borda também não).
    """
    pdf, codigo = await service.gerar_etiqueta(str(prova_id))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="etiqueta-{codigo}.pdf"'},
    )


__all__ = ["router"]
