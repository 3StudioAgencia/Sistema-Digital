"""Dependências FastAPI por requisição (W1-C04 · RBAC no W1-C05).

Constrói o ``UsuariosService`` a partir do que o composition root pendurou em
``app.state`` (session factory + provedor de identidade) e, no C05, **propaga os
claims do JWT verificado para a sessão do Postgres** (ADR-008) — de modo que a
RLS por perfil valha também nas consultas servidas pelo backend. A autorização
por recurso (Matriz §7) é exposta como dependência reutilizável (``requer_acesso``),
generalização do guard de admin do C04.
"""

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.adapters.inbound.http.auth import AuthenticatedUser, get_current_user
from src.adapters.outbound.db.provas_repository import SqlAlchemyProvasRepository
from src.adapters.outbound.db.unit_of_work import SqlAlchemyUnitOfWork
from src.adapters.outbound.db.usuarios_repository import SqlAlchemyUsuariosRepository
from src.application.ports.etiqueta import EtiquetaPort
from src.application.ports.identity_provider import IdentityProviderPort
from src.application.ports.storage import StoragePort
from src.application.provas import ProvasConsultaService, ProvasService
from src.application.usuarios import UsuariosService
from src.domain.rbac import Recurso, autorizar
from src.domain.usuarios import Usuario
from src.infrastructure.database import abrir_sessao_rls


async def get_usuarios_service(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AsyncIterator[UsuariosService]:
    """Serviço de usuários por requisição, com a RLS honrada via propagação de
    claims (ADR-008): toda transação desta sessão roda como ``authenticated`` com
    ``request.jwt.claims`` = os claims do JWT verificado deste usuário."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    identity: IdentityProviderPort = request.app.state.identity_provider
    # Sessão de request com a RLS ligada ao usuário corrente (ponto único,
    # fail-closed — W1-A-001). O C06 reusa este mesmo opener para ``provas``.
    async with abrir_sessao_rls(factory, user.claims) as session:
        yield UsuariosService(
            repo=SqlAlchemyUsuariosRepository(session),
            identity=identity,
            uow=SqlAlchemyUnitOfWork(session),
        )


def requer_acesso(
    recurso: Recurso,
) -> Callable[..., Coroutine[Any, Any, Usuario]]:
    """Fábrica de dependência de autorização por recurso (Matriz §7).

    Camada SUPERIOR do RBAC no backend: exige JWT válido E linha ``usuarios``
    ativa cujo perfil autoriza ``recurso`` (``autorizar`` — espelho de
    ``access-matrix.ts``). A linha do próprio ator é legível pela RLS (policy
    ``usuarios_select_self``), então o guard funciona para qualquer perfil.

    Mensagem ÚNICA para "sem linha", "inativo" e "não autorizado": o ator sabe
    quem é; o que não revelamos é POR QUE foi negado (menos superfície,
    anti-enumeração — CLAUDE.md §11).
    """

    async def _dep(
        user: AuthenticatedUser = Depends(get_current_user),
        service: UsuariosService = Depends(get_usuarios_service),
    ) -> Usuario:
        ator = await service.obter(user.sub)
        if ator is None or not autorizar(ator, recurso):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado.",
            )
        return ator

    return _dep


# Guard de admin do C04, agora expresso pela Matriz: gestão de usuários é
# "Exclusivo 3Studio" (flag administrador). Mantido como nome estável usado pelos
# endpoints de ``usuarios``.
get_admin_corrente = requer_acesso(Recurso.CADASTRO_USUARIOS)


async def get_provas_service(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AsyncIterator[ProvasService]:
    """Serviço de provas por requisição, JÁ gateado por ``CRIAR_PROVA`` (W2-C06).

    Autorização e serviço compartilham UMA sessão RLS (em vez de empilhar
    ``requer_acesso`` + serviço, que abririam duas conexões com NullPool —
    RNF-020): a linha do próprio ator é legível pela policy
    ``usuarios_select_self``, então o gate funciona dentro da mesma sessão.
    Mensagem única de negação (anti-enumeração — mesma do ``requer_acesso``).
    Ambos os endpoints do C06 (criar + etiqueta) são exclusivos do admin
    (Matriz §7, "Criar Prova"); quando o C07 trouxer leituras universais,
    cria-se a dependência própria com o recurso adequado.
    """
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    storage: StoragePort = request.app.state.storage
    etiqueta: EtiquetaPort = request.app.state.etiqueta_generator
    async with abrir_sessao_rls(factory, user.claims) as session:
        usuarios_repo = SqlAlchemyUsuariosRepository(session)
        ator = await usuarios_repo.get(user.sub)
        if ator is None or not autorizar(ator, Recurso.CRIAR_PROVA):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado.",
            )
        yield ProvasService(
            repo=SqlAlchemyProvasRepository(session),
            usuarios_repo=usuarios_repo,
            storage=storage,
            etiqueta=etiqueta,
            uow=SqlAlchemyUnitOfWork(session),
        )


async def get_provas_consulta_service(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AsyncIterator[ProvasConsultaService]:
    """Serviço de LEITURA de provas (W2-C07) — listagem/filtros da página universal.

    Diferente de ``get_provas_service`` (gate ``CRIAR_PROVA``, admin): a Matriz §7
    torna ``provas`` ACESSÍVEL A QUALQUER perfil ativo; o que muda por perfil é o
    ESCOPO de dado, garantido pela RLS de ``provas`` (C06) — não pela borda. Mesma
    sessão RLS fail-closed por requisição (ADR-008/ADR-034), sem ``storage``/
    ``etiqueta`` (caminho só de leitura). Negação ÚNICA para sem-linha/inativo/
    não-autorizado (anti-enumeração — CLAUDE.md §11)."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    async with abrir_sessao_rls(factory, user.claims) as session:
        ator = await SqlAlchemyUsuariosRepository(session).get(user.sub)
        if ator is None or not autorizar(ator, Recurso.PROVAS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado.",
            )
        yield ProvasConsultaService(repo=SqlAlchemyProvasRepository(session))


__all__ = [
    "get_admin_corrente",
    "get_provas_consulta_service",
    "get_provas_service",
    "get_usuarios_service",
    "requer_acesso",
]
