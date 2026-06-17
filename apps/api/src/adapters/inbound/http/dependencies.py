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
from src.adapters.outbound.db.assinaturas_repository import SqlAlchemyAssinaturasRepository
from src.adapters.outbound.db.movimentacoes_repository import SqlAlchemyMovimentacoesRepository
from src.adapters.outbound.db.provas_repository import SqlAlchemyProvasRepository
from src.adapters.outbound.db.rate_limiter import SqlAlchemyRateLimiter
from src.adapters.outbound.db.settings_repository import SqlAlchemySettingsRepository
from src.adapters.outbound.db.unit_of_work import SqlAlchemyUnitOfWork
from src.adapters.outbound.db.usuarios_repository import SqlAlchemyUsuariosRepository
from src.application.ports.etiqueta import EtiquetaPort
from src.application.ports.identity_provider import IdentityProviderPort
from src.application.ports.storage import StoragePort
from src.application.provas import (
    ProvasConsultaService,
    ProvasIdentificacaoService,
    ProvasService,
)
from src.application.settings import SettingsService
from src.application.transicoes import ProvasTransicaoService
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
    """Serviço de CRIAÇÃO de provas por requisição, JÁ gateado por ``CRIAR_PROVA``.

    Autorização e serviço compartilham UMA sessão RLS (em vez de empilhar
    ``requer_acesso`` + serviço, que abririam duas conexões com NullPool —
    RNF-020): a linha do próprio ator é legível pela policy
    ``usuarios_select_self``, então o gate funciona dentro da mesma sessão.
    Mensagem única de negação (anti-enumeração — mesma do ``requer_acesso``).
    Só a CRIAÇÃO (``POST /provas``) é exclusiva do admin (Matriz §7, "Criar
    Prova"); detalhe/arte/etiqueta (W2-C08) são UNIVERSAIS-em-escopo e usam
    ``get_provas_consulta_service`` (DP-8).
    """
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    storage: StoragePort = request.app.state.storage
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
            uow=SqlAlchemyUnitOfWork(session),
        )


async def get_provas_consulta_service(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AsyncIterator[ProvasConsultaService]:
    """Serviço de LEITURA de provas (W2-C07 listagem + W2-C08 detalhe/arte/etiqueta).

    Diferente de ``get_provas_service`` (gate ``CRIAR_PROVA``, admin): a Matriz §7
    torna ``provas`` ACESSÍVEL A QUALQUER perfil ativo; o que muda por perfil é o
    ESCOPO de dado, garantido pela RLS de ``provas`` (C06) — não pela borda. Mesma
    sessão RLS fail-closed por requisição (ADR-008/ADR-034). ``storage``/``etiqueta``
    injetados aqui (C08): servem o proxy da arte (DP-5) e a etiqueta universal-em-
    escopo (DP-8); a listagem/detalhe não os tocam. Negação ÚNICA para sem-linha/
    inativo/não-autorizado (anti-enumeração — CLAUDE.md §11)."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    storage: StoragePort = request.app.state.storage
    etiqueta: EtiquetaPort = request.app.state.etiqueta_generator
    async with abrir_sessao_rls(factory, user.claims) as session:
        ator = await SqlAlchemyUsuariosRepository(session).get(user.sub)
        if ator is None or not autorizar(ator, Recurso.PROVAS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado.",
            )
        yield ProvasConsultaService(
            repo=SqlAlchemyProvasRepository(session),
            storage=storage,
            etiqueta=etiqueta,
            # W2-C09: a etiqueta respeita a config do template (RN-011), lida na
            # MESMA sessão RLS (leitura authenticated — DP-2).
            settings_repo=SqlAlchemySettingsRepository(session),
            # W3-C13: o histórico (Timeline) é lido na MESMA sessão RLS — a RLS de
            # ``movimentacoes`` espelha o escopo de ``provas`` (DP-2).
            movs=SqlAlchemyMovimentacoesRepository(session),
        )


async def get_identificacao_service(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AsyncIterator[ProvasIdentificacaoService]:
    """Serviço de IDENTIFICAÇÃO de provas (W3-C10), JÁ gateado por ``ESCANEAR``.

    "Escanear QR" é UNIVERSAL na Matriz §7 (qualquer perfil ativo); o ESCOPO de
    dado é da RLS de ``provas`` — código fora do escopo resolve para o MESMO 404
    genérico (anti-enumeração — RN-014). Gate + serviço numa ÚNICA sessão RLS
    fail-closed (a linha do ator é legível por ``usuarios_select_self``). O rate
    limiter e o repositório compartilham a sessão: o contador vive na mesma
    transação que o caso de uso confirma ANTES de resolver (RNF-020). Negação
    ÚNICA para sem-linha/inativo/não-autorizado (anti-enumeração — CLAUDE.md §11).
    """
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    async with abrir_sessao_rls(factory, user.claims) as session:
        ator = await SqlAlchemyUsuariosRepository(session).get(user.sub)
        if ator is None or not autorizar(ator, Recurso.ESCANEAR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado.",
            )
        yield ProvasIdentificacaoService(
            repo=SqlAlchemyProvasRepository(session),
            rate_limiter=SqlAlchemyRateLimiter(session),
            uow=SqlAlchemyUnitOfWork(session),
        )


async def get_transicao_service(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AsyncIterator[ProvasTransicaoService]:
    """Serviço de TRANSIÇÃO da máquina de estados (W3-C11), gateado por ``ESCANEAR``.

    A página/ação é universal na Matriz §7 ("Escanear" — o fluxo identificar →
    assinar → confirmar é de qualquer perfil ativo); a autorização FINA por ação
    (qual setor avança o quê; Cancelar/Reiniciar só admin) é do MOTOR
    (``avaliar_transicao``), não da borda — daí o gate amplo. Gate + serviço numa
    ÚNICA sessão RLS fail-closed; o ``ator`` carregado para o gate é passado ao
    motor (setor + flag administrador). ``repo``/``movs``/``uow`` compartilham a
    sessão: ``status`` e ``movimentacoes`` caem na MESMA transação (RNF-017).
    Negação ÚNICA para sem-linha/inativo/não-autorizado (anti-enumeração — §11).
    """
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    async with abrir_sessao_rls(factory, user.claims) as session:
        ator = await SqlAlchemyUsuariosRepository(session).get(user.sub)
        if ator is None or not autorizar(ator, Recurso.ESCANEAR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado.",
            )
        yield ProvasTransicaoService(
            repo=SqlAlchemyProvasRepository(session),
            movs=SqlAlchemyMovimentacoesRepository(session),
            # W3-C12: a assinatura e a movimentação caem na MESMA sessão/transação
            # (RNF-017) — nascem/falham juntas.
            assinaturas=SqlAlchemyAssinaturasRepository(session),
            uow=SqlAlchemyUnitOfWork(session),
            ator=ator,
        )


async def get_cancelamento_service(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AsyncIterator[ProvasTransicaoService]:
    """Serviço de CANCELAMENTO (W3-C14) — o MESMO motor de transição (uma fonte
    única de mudança de status; ADR-062), mas gateado por ``CANCELAR_PROVA``.

    Cancelar é "Exclusivo 3Studio" na Matriz §7 — exige a flag ``administrador``
    (ADR-023/ADR-064). Diferente de ``get_transicao_service`` (gate amplo
    ``ESCANEAR``, porque o fluxo de escaneamento é universal e a autorização fina é
    do motor), aqui a BORDA já barra o não-admin: defesa em DUAS camadas (gate de
    recurso + ``Autorizacao.ADMIN`` do motor). O motor ainda revalida — negar em
    qualquer camada basta (CLAUDE.md §5.4). Mesma sessão RLS fail-closed; o ``ator``
    carregado para o gate vai ao motor. Negação ÚNICA para sem-linha/inativo/não-
    admin (403 ``Acesso negado.``)."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    async with abrir_sessao_rls(factory, user.claims) as session:
        ator = await SqlAlchemyUsuariosRepository(session).get(user.sub)
        if ator is None or not autorizar(ator, Recurso.CANCELAR_PROVA):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado.",
            )
        yield ProvasTransicaoService(
            repo=SqlAlchemyProvasRepository(session),
            movs=SqlAlchemyMovimentacoesRepository(session),
            assinaturas=SqlAlchemyAssinaturasRepository(session),
            uow=SqlAlchemyUnitOfWork(session),
            ator=ator,
        )


async def get_reinicio_service(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AsyncIterator[ProvasTransicaoService]:
    """Serviço de REINÍCIO DE CICLO (W3-C15) — o MESMO motor de transição (fonte
    ÚNICA de mudança de status; ADR-062), gateado por ``REINICIAR_CICLO``.

    Reiniciar é "Exclusivo 3Studio" na Matriz §7 — exige a flag ``administrador``
    (ADR-023/ADR-064), idêntico ao cancelamento (C14). A BORDA já barra o não-admin:
    defesa em DUAS camadas (gate de recurso ``REINICIAR_CICLO`` + ``Autorizacao.ADMIN``
    do motor). Negar em qualquer camada basta (CLAUDE.md §5.4); o motor revalida.
    Mesma sessão RLS fail-closed; o ``ator`` carregado para o gate vai ao motor.
    Negação ÚNICA para sem-linha/inativo/não-admin (403 ``Acesso negado.``)."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    async with abrir_sessao_rls(factory, user.claims) as session:
        ator = await SqlAlchemyUsuariosRepository(session).get(user.sub)
        if ator is None or not autorizar(ator, Recurso.REINICIAR_CICLO):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado.",
            )
        yield ProvasTransicaoService(
            repo=SqlAlchemyProvasRepository(session),
            movs=SqlAlchemyMovimentacoesRepository(session),
            assinaturas=SqlAlchemyAssinaturasRepository(session),
            uow=SqlAlchemyUnitOfWork(session),
            ator=ator,
        )


async def get_settings_service(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AsyncIterator[SettingsService]:
    """Serviço de configurações por requisição, JÁ gateado por ``CONFIGURACOES``.

    Configurações são "Exclusivo 3Studio" (Matriz §7 — flag administrador, ADR-023):
    gate + serviço numa ÚNICA sessão RLS (a linha do ator é legível por
    ``usuarios_select_self``), evitando duas conexões NullPool (RNF-020). A escrita
    é admin-only TAMBÉM na RLS de ``system_settings`` (defesa em profundidade — DP-3).
    Negação ÚNICA (anti-enumeração — CLAUDE.md §11)."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:  # boot sem banco (testes offline sem override explícito)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistência não configurada.",
        )
    async with abrir_sessao_rls(factory, user.claims) as session:
        ator = await SqlAlchemyUsuariosRepository(session).get(user.sub)
        if ator is None or not autorizar(ator, Recurso.CONFIGURACOES):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado.",
            )
        yield SettingsService(
            repo=SqlAlchemySettingsRepository(session),
            uow=SqlAlchemyUnitOfWork(session),
        )


__all__ = [
    "get_admin_corrente",
    "get_identificacao_service",
    "get_provas_consulta_service",
    "get_provas_service",
    "get_settings_service",
    "get_transicao_service",
    "get_usuarios_service",
    "requer_acesso",
]
