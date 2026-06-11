"""Endpoints de gestão de usuários (W1-C04) — RF-018, RF-020, US-015.

Todos exigem JWT válido; os de gestão exigem o guard de admin (DP-5).
``GET /usuarios/me`` é a exceção deliberada: QUALQUER usuário autenticado lê a
própria linha de domínio — é o que alimenta a saudação/escopo do app shell.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from src.adapters.inbound.http.auth import AuthenticatedUser, get_current_user
from src.adapters.inbound.http.dependencies import get_admin_corrente, get_usuarios_service
from src.application.ports.usuarios_repository import (
    PAGE_SIZE_MAXIMO,
    PAGE_SIZE_PADRAO,
    FiltrosUsuarios,
)
from src.application.usuarios import CriarUsuario, EditarUsuario, UsuariosService
from src.domain.usuarios import Localizacao, SenhaFracaError, Setor, Usuario, validar_senha

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


# ---------------------------------------------------------------------------
# Schemas (validação de FORMA na borda; REGRAS vivem no domínio/serviço)
# ---------------------------------------------------------------------------
class UsuarioOut(BaseModel):
    id: str
    nome: str
    email: str
    setor: Setor
    localizacao: Localizacao | None
    administrador: bool
    ativo: bool
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def de_dominio(cls, u: Usuario) -> Self:
        return cls(
            id=u.id,
            nome=u.nome,
            email=u.email,
            setor=u.setor,
            localizacao=u.localizacao,
            administrador=u.administrador,
            ativo=u.ativo,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )


class CriarUsuarioIn(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    email: EmailStr = Field(max_length=320)
    senha: str
    setor: Setor
    localizacao: Localizacao | None = None
    administrador: bool = False

    @field_validator("nome")
    @classmethod
    def _nome_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nome não pode ser vazio")
        return v.strip()

    @field_validator("senha")
    @classmethod
    def _politica_de_senha(cls, v: str) -> str:
        try:
            validar_senha(v)
        except SenhaFracaError as exc:
            raise ValueError(str(exc)) from None
        return v


class EditarUsuarioIn(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    setor: Setor | None = None
    localizacao: Localizacao | None = None
    administrador: bool | None = None

    @field_validator("nome")
    @classmethod
    def _nome_nao_vazio(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("nome não pode ser vazio")
        return v.strip() if v is not None else None


class PaginaUsuariosOut(BaseModel):
    items: list[UsuarioOut]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/me", response_model=UsuarioOut)
async def me(
    user: AuthenticatedUser = Depends(get_current_user),
    service: UsuariosService = Depends(get_usuarios_service),
) -> UsuarioOut:
    """Linha de domínio do PRÓPRIO usuário autenticado (saudação/escopo do shell)."""
    usuario = await service.obter(user.sub)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não provisionado.",
        )
    return UsuarioOut.de_dominio(usuario)


@router.get("", response_model=PaginaUsuariosOut)
async def listar(
    _admin: Annotated[Usuario, Depends(get_admin_corrente)],
    service: Annotated[UsuariosService, Depends(get_usuarios_service)],
    busca: Annotated[str | None, Query(max_length=200)] = None,
    setor: Setor | None = None,
    status_filtro: Annotated[
        Literal["ativo", "inativo"] | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAXIMO)] = PAGE_SIZE_PADRAO,
) -> PaginaUsuariosOut:
    """Listagem paginada server-side com busca e filtros indexados (RNF-019)."""
    pagina = await service.listar(
        FiltrosUsuarios(
            busca=busca,
            setor=setor,
            ativo=None if status_filtro is None else status_filtro == "ativo",
            page=page,
            page_size=page_size,
        )
    )
    return PaginaUsuariosOut(
        items=[UsuarioOut.de_dominio(u) for u in pagina.items],
        total=pagina.total,
        page=pagina.page,
        page_size=pagina.page_size,
    )


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
async def criar(
    payload: CriarUsuarioIn,
    _admin: Annotated[Usuario, Depends(get_admin_corrente)],
    service: Annotated[UsuariosService, Depends(get_usuarios_service)],
) -> UsuarioOut:
    """Provisionamento coordenado: auth user (Admin API) + linha ``usuarios``."""
    usuario = await service.criar(
        CriarUsuario(
            nome=payload.nome,
            email=payload.email,
            senha=payload.senha,
            setor=payload.setor,
            localizacao=payload.localizacao,
            administrador=payload.administrador,
        )
    )
    return UsuarioOut.de_dominio(usuario)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
async def editar(
    usuario_id: uuid.UUID,
    payload: EditarUsuarioIn,
    admin: Annotated[Usuario, Depends(get_admin_corrente)],
    service: Annotated[UsuariosService, Depends(get_usuarios_service)],
) -> UsuarioOut:
    """Edição parcial (nome/setor/localização/perfil). E-mail não é editável."""
    usuario = await service.editar(
        ator=admin,
        usuario_id=str(usuario_id),
        edicao=EditarUsuario(
            nome=payload.nome,
            setor=payload.setor,
            localizacao=payload.localizacao,
            localizacao_informada="localizacao" in payload.model_fields_set,
            administrador=payload.administrador,
        ),
    )
    return UsuarioOut.de_dominio(usuario)


@router.post("/{usuario_id}/desativar", response_model=UsuarioOut)
async def desativar(
    usuario_id: uuid.UUID,
    admin: Annotated[Usuario, Depends(get_admin_corrente)],
    service: Annotated[UsuariosService, Depends(get_usuarios_service)],
) -> UsuarioOut:
    """Bloqueia o login (ban no auth) preservando todo o histórico (US-015)."""
    usuario = await service.alterar_status(ator=admin, usuario_id=str(usuario_id), ativo=False)
    return UsuarioOut.de_dominio(usuario)


@router.post("/{usuario_id}/reativar", response_model=UsuarioOut)
async def reativar(
    usuario_id: uuid.UUID,
    admin: Annotated[Usuario, Depends(get_admin_corrente)],
    service: Annotated[UsuariosService, Depends(get_usuarios_service)],
) -> UsuarioOut:
    usuario = await service.alterar_status(ator=admin, usuario_id=str(usuario_id), ativo=True)
    return UsuarioOut.de_dominio(usuario)


__all__ = ["router"]
