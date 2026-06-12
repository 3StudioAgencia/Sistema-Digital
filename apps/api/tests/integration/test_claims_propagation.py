"""Propagação de claims à RLS (ADR-008) — W1-C05, @db.

Prova de ponta a ponta no caminho do backend:
- COM propagação, as consultas do repositório respeitam a RLS de ``usuarios``
  (não-admin não enxerga linha alheia — critério §6.4);
- SEM propagação (conexão *owner*), a RLS é contornada — por isso a propagação é
  a ÚNICA garantia nesse caminho (teste de CONTROLE, negativo).
"""

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from src.adapters.outbound.db.models import UsuarioRow
from src.adapters.outbound.db.usuarios_repository import SqlAlchemyUsuariosRepository
from src.domain.usuarios import Localizacao, Setor
from src.infrastructure.database import propagar_claims_rls

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
async def factory(usuarios_engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(usuarios_engine, expire_on_commit=False)


async def _seed(
    factory: async_sessionmaker,
    *,
    setor: Setor,
    administrador: bool,
    localizacao: Localizacao | None = None,
) -> str:
    uid = str(uuid.uuid4())
    async with factory() as session:  # owner: bypassa RLS — só prepara o estado
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


async def test_backend_com_propagacao_respeita_rls(factory: async_sessionmaker) -> None:
    admin = await _seed(factory, setor=Setor.STUDIO, administrador=True)
    vendedor = await _seed(
        factory, setor=Setor.VENDEDOR, administrador=False, localizacao=Localizacao.MATRIZ
    )

    # Admin (claims propagados) enxerga qualquer linha.
    async with factory() as session:
        propagar_claims_rls(session, _claims(admin, setor="studio", administrador=True))
        repo = SqlAlchemyUsuariosRepository(session)
        assert (await repo.get(vendedor)) is not None

    # Não-admin enxerga apenas a PRÓPRIA linha.
    async with factory() as session:
        propagar_claims_rls(
            session, _claims(vendedor, setor="vendedor", administrador=False)
        )
        repo = SqlAlchemyUsuariosRepository(session)
        assert (await repo.get(vendedor)) is not None  # self
        assert (await repo.get(admin)) is None  # alheia → RLS bloqueia (não vaza)


async def test_sem_propagacao_owner_contorna_rls_controle(
    factory: async_sessionmaker,
) -> None:
    """CONTROLE: a mesma leitura SEM propagação (owner) enxerga tudo — evidência de
    que a propagação é o que liga a RLS no caminho do backend (não um efeito do
    banco 'por acaso')."""
    admin = await _seed(factory, setor=Setor.STUDIO, administrador=True)
    outro = await _seed(factory, setor=Setor.CLICHERIA, administrador=False)

    async with factory() as session:  # sem propagar_claims_rls → owner
        repo = SqlAlchemyUsuariosRepository(session)
        assert (await repo.get(admin)) is not None
        assert (await repo.get(outro)) is not None
