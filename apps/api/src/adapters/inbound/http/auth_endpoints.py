"""Endpoints de autenticação própria — login/refresh/logout (migração Supabase->local).

PRÉ-AUTENTICAÇÃO: não passam por ``get_current_user`` nem pela sessão RLS. Usam a
sessão de SISTEMA (``app.state.system_session_factory`` — plain, no role de
runtime, sem claims) e as funções ``private.auth_*``. O token vai ao cliente em
cookies **httpOnly** (``access_token`` + ``refresh_token``): imunes a XSS, lidos
pelo backend (``get_current_user``) e pelo proxy do Next (Fase 3).
"""

from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.adapters.inbound.http.auth import ACCESS_COOKIE_NAME
from src.adapters.outbound.db.auth_repository import SqlAlchemyAuthRepository
from src.adapters.outbound.db.unit_of_work import SqlAlchemyUnitOfWork
from src.application.auth import AutenticacaoService, ResultadoAuth
from src.application.ports.password_hasher import PasswordHasherPort
from src.application.ports.tokens import TokenIssuerPort
from src.domain.usuarios import Setor
from src.infrastructure.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie do refresh token (o do access está em auth.ACCESS_COOKIE_NAME).
REFRESH_COOKIE_NAME = "refresh_token"
# SameSite=lax basta com o front na MESMA origem (rewrite /api do Next — Fase 3).
_SAMESITE: Literal["lax"] = "lax"


class LoginIn(BaseModel):
    email: EmailStr
    senha: str


class SessaoOut(BaseModel):
    """Confirma o login e já entrega o perfil (evita um /me imediato no front)."""

    id: str
    email: str
    setor: Setor
    administrador: bool

    @classmethod
    def de_resultado(cls, r: ResultadoAuth) -> "SessaoOut":
        return cls(id=r.user_id, email=r.email, setor=Setor(r.setor), administrador=r.administrador)


def _cookie_secure(settings: Settings) -> bool:
    # Secure só em staging/produção (HTTPS). Em dev/test (http://localhost) o
    # atributo Secure impediria o envio do cookie.
    return settings.app_env in ("staging", "production")


def _set_auth_cookies(response: Response, r: ResultadoAuth, settings: Settings) -> None:
    secure = _cookie_secure(settings)
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        r.access_token,
        max_age=settings.auth_access_ttl_seconds,
        httponly=True,
        secure=secure,
        samesite=_SAMESITE,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        r.refresh_token,
        max_age=settings.auth_refresh_ttl_seconds,
        httponly=True,
        secure=secure,
        samesite=_SAMESITE,
        path="/",
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    secure = _cookie_secure(settings)
    for nome in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME):
        response.delete_cookie(
            nome, path="/", httponly=True, secure=secure, samesite=_SAMESITE
        )


async def get_autenticacao_service(request: Request) -> AsyncIterator[AutenticacaoService]:
    """Serviço de auth numa sessão de SISTEMA (sem claims — caminho pré-auth)."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.system_session_factory
    issuer: TokenIssuerPort | None = request.app.state.token_issuer
    if factory is None or issuer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação não configurada.",
        )
    hasher: PasswordHasherPort = request.app.state.password_hasher
    settings: Settings = request.app.state.settings
    async with factory() as session:
        yield AutenticacaoService(
            repo=SqlAlchemyAuthRepository(session),
            hasher=hasher,
            issuer=issuer,
            uow=SqlAlchemyUnitOfWork(session),
            refresh_ttl_seconds=settings.auth_refresh_ttl_seconds,
        )


def _credenciais_invalidas() -> HTTPException:
    # Mensagem ÚNICA para e-mail inexistente / senha errada / conta inativa
    # (anti-enumeração — CLAUDE.md §11).
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="E-mail ou senha inválidos.",
    )


@router.post("/login", response_model=SessaoOut)
async def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    service: AutenticacaoService = Depends(get_autenticacao_service),
) -> SessaoOut:
    resultado = await service.login(payload.email, payload.senha)
    if resultado is None:
        raise _credenciais_invalidas()
    _set_auth_cookies(response, resultado, request.app.state.settings)
    return SessaoOut.de_resultado(resultado)


@router.post("/refresh", response_model=SessaoOut)
async def refresh(
    request: Request,
    response: Response,
    service: AutenticacaoService = Depends(get_autenticacao_service),
) -> SessaoOut:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    resultado = await service.refresh(token)
    if resultado is None:
        # Sessão expirada/ inválida: limpa os cookies e força novo login.
        _clear_auth_cookies(response, request.app.state.settings)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada. Entre novamente.",
        )
    _set_auth_cookies(response, resultado, request.app.state.settings)
    return SessaoOut.de_resultado(resultado)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    service: AutenticacaoService = Depends(get_autenticacao_service),
) -> None:
    await service.logout(request.cookies.get(REFRESH_COOKIE_NAME))
    _clear_auth_cookies(response, request.app.state.settings)


__all__ = ["REFRESH_COOKIE_NAME", "get_autenticacao_service", "router"]
