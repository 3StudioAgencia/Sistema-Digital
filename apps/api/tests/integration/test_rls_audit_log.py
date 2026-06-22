"""RLS + escrita controlada de ``audit_log`` (W6-C20) contra Postgres real (@db).

Valida, como o banco verá em produção (``SET LOCAL ROLE authenticated`` + claims):

- SELECT é EXCLUSIVO do admin (``audit_log_select_admin`` = ``app_is_admin()``):
  3Studio/admin vê tudo; qualquer outro perfil → 0 registros (mesmo chamando direto);
- ESCRITA só pela função ``private.audit_log_append`` (SECURITY DEFINER, força o ator
  das claims): INSERT direto por ``authenticated`` é NEGADO (sem GRANT — anti-forja);
- APPEND-ONLY: UPDATE/DELETE bloqueados até para o owner (trigger).
"""

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

pytestmark = pytest.mark.db


def _claims(sub: str, setor: str, administrador: bool = False) -> str:
    return json.dumps(
        {
            "sub": sub,
            "user_id": sub,
            "setor": setor,
            "administrador": administrador,
            "role": "authenticated",
            "aud": "authenticated",
        }
    )


async def _autenticar(conn: AsyncConnection, sub: str, setor: str, admin: bool = False) -> None:
    await conn.execute(
        text("SELECT set_config('request.jwt.claims', :c, true)"), {"c": _claims(sub, setor, admin)}
    )
    await conn.execute(text("SET LOCAL ROLE authenticated"))


async def _seed_usuario(engine: AsyncEngine, *, setor: str, admin: bool = False) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id, 'U', :email, :setor, :loc, :adm)"
            ),
            {"id": uid, "email": f"{uid}@x.z", "setor": setor, "loc": loc, "adm": admin},
        )
    return uid


_APPEND = text(
    "SELECT private.audit_log_append("
    ":evento, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)"
)


async def _semear_evento(
    engine: AsyncEngine, *, ator: str, setor: str, admin: bool = False
) -> None:
    """Acrescenta UM evento via a função DEFINER, autenticado como ``ator``."""
    async with engine.begin() as conn:
        await _autenticar(conn, ator, setor, admin)
        await conn.execute(_APPEND, {"evento": "escaneou_qr"})


async def test_select_e_exclusivo_do_admin(usuarios_engine: AsyncEngine) -> None:
    engine = usuarios_engine
    admin = await _seed_usuario(engine, setor="studio", admin=True)
    vendedor = await _seed_usuario(engine, setor="vendedor")
    await _semear_evento(engine, ator=vendedor, setor="vendedor")  # 1 evento no log

    # Admin enxerga o log inteiro.
    async with engine.connect() as conn:
        await _autenticar(conn, admin, "studio", True)
        total_admin = (await conn.execute(text("SELECT count(*) FROM audit_log"))).scalar_one()
    assert total_admin == 1

    # Não-admin (vendedor) NÃO enxerga nada (RLS app_is_admin()).
    async with engine.connect() as conn:
        await _autenticar(conn, vendedor, "vendedor")
        total_vendedor = (await conn.execute(text("SELECT count(*) FROM audit_log"))).scalar_one()
    assert total_vendedor == 0

    # Clicheria/Motorista também não (mesmo vendo todas as provas, o LOG é admin-only).
    async with engine.connect() as conn:
        await _autenticar(conn, await _seed_usuario(engine, setor="clicheria"), "clicheria")
        total_clicheria = (await conn.execute(text("SELECT count(*) FROM audit_log"))).scalar_one()
    assert total_clicheria == 0


async def test_insert_direto_e_negado_para_authenticated(usuarios_engine: AsyncEngine) -> None:
    """A escrita é só pela função DEFINER — INSERT direto não tem GRANT (anti-forja)."""
    engine = usuarios_engine
    vendedor = await _seed_usuario(engine, setor="vendedor")
    with pytest.raises(DBAPIError):
        async with engine.begin() as conn:
            await _autenticar(conn, vendedor, "vendedor")
            await conn.execute(
                text(
                    "INSERT INTO audit_log (seq, evento, ator_id, prev_hash, hash) "
                    "VALUES (999, 'escaneou_qr', :a, '', 'deadbeef')"
                ),
                {"a": vendedor},
            )


async def test_append_forca_o_ator_das_claims(usuarios_engine: AsyncEngine) -> None:
    """A função grava o ator = ``app_current_user_id()`` — o cliente não escolhe."""
    engine = usuarios_engine
    admin = await _seed_usuario(engine, setor="studio", admin=True)
    vendedor = await _seed_usuario(engine, setor="vendedor")
    await _semear_evento(engine, ator=vendedor, setor="vendedor")
    async with engine.connect() as conn:
        await _autenticar(conn, admin, "studio", True)
        ator = (
            await conn.execute(text("SELECT ator_id::text FROM audit_log LIMIT 1"))
        ).scalar_one()
    assert ator == vendedor


async def test_update_e_delete_bloqueados_ate_para_o_owner(usuarios_engine: AsyncEngine) -> None:
    engine = usuarios_engine
    vendedor = await _seed_usuario(engine, setor="vendedor")
    await _semear_evento(engine, ator=vendedor, setor="vendedor")
    with pytest.raises(DBAPIError):
        async with engine.begin() as conn:  # owner, sem SET ROLE
            await conn.execute(text("UPDATE audit_log SET motivo = 'x'"))
    with pytest.raises(DBAPIError):
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM audit_log"))
