"""Dependências FastAPI por requisição (W1-C04).

Constrói o ``UsuariosService`` a partir do que o composition root pendurou em
``app.state`` (session factory + provedor de identidade). É o equivalente
por-request do wiring do ``main.py`` — testes substituem via
``app.dependency_overrides`` ou injetando fakes no ``create_app``.
"""

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.adapters.inbound.http.auth import AuthenticatedUser, get_current_user
from src.adapters.outbound.db.usuarios_repository import SqlAlchemyUsuariosRepository
from src.application.ports.identity_provider import IdentityProviderPort
from src.application.usuarios import UsuariosService
from src.domain.usuarios import Usuario
from src.infrastructure.database import SqlAlchemyUnitOfWork


async def get_usuarios_service(request: Request) -> AsyncIterator[UsuariosService]:
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    identity: IdentityProviderPort = request.app.state.identity_provider
    async with factory() as session:
        yield UsuariosService(
            repo=SqlAlchemyUsuariosRepository(session),
            identity=identity,
            uow=SqlAlchemyUnitOfWork(session),
        )


async def get_admin_corrente(
    user: AuthenticatedUser = Depends(get_current_user),
    service: UsuariosService = Depends(get_usuarios_service),
) -> Usuario:
    """Guard mínimo de admin (DP-5): JWT válido E linha ``usuarios`` ativa com
    ``administrador=true``. O enforcement completo por página/RLS é C05.

    Mensagem única para "sem linha", "inativo" e "não-admin": quem chama sabe
    quem é; o que não revelamos é POR QUE foi negado (menos superfície).
    """
    ator = await service.obter(user.sub)
    if ator is None or not ator.ativo or not ator.administrador:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return ator


__all__ = ["get_admin_corrente", "get_usuarios_service"]
