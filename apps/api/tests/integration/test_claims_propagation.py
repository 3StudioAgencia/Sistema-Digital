"""Propagação de claims à RLS (ADR-008) — W1-C05/W1-A-001, @db.

Prova de ponta a ponta no caminho do backend:
- COM propagação, as consultas do repositório respeitam a RLS de ``usuarios``
  (não-admin não enxerga linha alheia — critério §6.4);
- uma sessão de REQUEST **sem** propagação **falha fechada** (não roda como owner):
  o guarda ``after_begin`` de ``_RlsSyncSession`` levanta antes de qualquer query
  (W1-A-001 — converte o fail-open silencioso em erro alto e cedo);
- sessões de SISTEMA (seed/CLI/migrations, fábrica owner) seguem fora da RLS de
  propósito — é por isso que o caminho de request precisa ser fail-closed.
"""

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from src.adapters.outbound.db.models import UsuarioRow
from src.adapters.outbound.db.usuarios_repository import SqlAlchemyUsuariosRepository
from src.domain.usuarios import Localizacao, Setor
from src.infrastructure.database import (
    create_request_session_factory,
    propagar_claims_rls,
)

pytestmark = pytest.mark.db


def _claims(sub: str, *, setor: str, administrador: bool) -> dict[str, Any]:
    return {
        "sub": sub,
        "user_id": sub,
        "setor": setor,
        "administrador": administrador,
        "role": "authenticated",
        "aud": "authenticated",
    }


@pytest.fixture
def request_factory(usuarios_engine: AsyncEngine) -> async_sessionmaker:
    """Fábrica de sessões de REQUEST (fail-closed na RLS — W1-A-001)."""
    return create_request_session_factory(usuarios_engine)


@pytest.fixture
def owner_factory(usuarios_engine: AsyncEngine) -> async_sessionmaker:
    """Fábrica de sessões de SISTEMA (owner): seed/CLI — fora da RLS de propósito."""
    return async_sessionmaker(usuarios_engine, expire_on_commit=False)


async def _seed(
    owner_factory: async_sessionmaker,
    *,
    setor: Setor,
    administrador: bool,
    localizacao: Localizacao | None = None,
) -> str:
    uid = str(uuid.uuid4())
    async with owner_factory() as session:  # owner: bypassa RLS — só prepara o estado
        session.add(
            UsuarioRow(
                id=uid,
                nome="U",
                email=f"{uid}@x.z",
                setor=setor,
                localizacao=localizacao,
                administrador=administrador,
            )
        )
        await session.commit()
    return uid


async def test_backend_com_propagacao_respeita_rls(
    request_factory: async_sessionmaker, owner_factory: async_sessionmaker
) -> None:
    admin = await _seed(owner_factory, setor=Setor.STUDIO, administrador=True)
    vendedor = await _seed(
        owner_factory, setor=Setor.VENDEDOR, administrador=False, localizacao=Localizacao.MATRIZ
    )

    # Admin (claims propagados) enxerga qualquer linha.
    async with request_factory() as session:
        propagar_claims_rls(session, _claims(admin, setor="studio", administrador=True))
        repo = SqlAlchemyUsuariosRepository(session)
        assert (await repo.get(vendedor)) is not None

    # Não-admin enxerga apenas a PRÓPRIA linha.
    async with request_factory() as session:
        propagar_claims_rls(session, _claims(vendedor, setor="vendedor", administrador=False))
        repo = SqlAlchemyUsuariosRepository(session)
        assert (await repo.get(vendedor)) is not None  # self
        assert (await repo.get(admin)) is None  # alheia → RLS bloqueia (não vaza)


async def test_request_sem_propagacao_falha_fechado(
    request_factory: async_sessionmaker, owner_factory: async_sessionmaker
) -> None:
    """W1-A-001: uma sessão de request que esquece a propagação NÃO roda como owner.

    O guarda ``after_begin`` de ``_RlsSyncSession`` levanta na primeira transação,
    antes de qualquer leitura — fail-closed, e não o fail-open silencioso de antes.
    """
    alvo = await _seed(owner_factory, setor=Setor.STUDIO, administrador=True)

    async with request_factory() as session:  # SEM propagar_claims_rls
        repo = SqlAlchemyUsuariosRepository(session)
        with pytest.raises(RuntimeError, match="fail-open"):
            await repo.get(alvo)


async def test_sessao_de_sistema_roda_como_owner(
    owner_factory: async_sessionmaker,
) -> None:
    """CONTROLE: sessões de SISTEMA (seed/CLI/migrations) enxergam tudo — bypass de
    RLS intencional. Documenta por que o caminho de REQUEST precisa ser fail-closed
    (uma sessão owner sem propagação vazaria entre escopos em silêncio)."""
    admin = await _seed(owner_factory, setor=Setor.STUDIO, administrador=True)
    outro = await _seed(owner_factory, setor=Setor.CLICHERIA, administrador=False)

    async with owner_factory() as session:  # owner, sem guarda → vê tudo
        repo = SqlAlchemyUsuariosRepository(session)
        assert (await repo.get(admin)) is not None
        assert (await repo.get(outro)) is not None
