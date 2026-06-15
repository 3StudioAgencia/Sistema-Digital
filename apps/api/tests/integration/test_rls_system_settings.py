"""RLS de ``system_settings`` (W2-C09) contra Postgres real (@db) — defesa em
profundidade do acesso 3Studio.

Exercita as policies como o banco as verá em produção (``SET LOCAL ROLE
authenticated`` + ``request.jwt.claims`` — ADR-008) e valida a postura DP-2/DP-3:

- LEITURA aberta a qualquer autenticado (o valor não é sigiloso; alimenta C16/C06);
- ESCRITA (INSERT/UPDATE) exclusiva do flag admin — query direta de não-admin
  é bloqueada pelo WITH CHECK (critério §6.1, camada inferior);
- sem GRANT de DELETE (privilégio mínimo).
"""

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

pytestmark = pytest.mark.db


def _claims(sub: str, setor: str, administrador: bool) -> str:
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


async def _autenticar(conn: AsyncConnection, sub: str, setor: str, admin: bool) -> None:
    await conn.execute(
        text("SELECT set_config('request.jwt.claims', :c, true)"),
        {"c": _claims(sub, setor, admin)},
    )
    await conn.execute(text("SET LOCAL ROLE authenticated"))


async def _inserir_como(
    engine: AsyncEngine, *, sub: str, setor: str, admin: bool, chave: str
) -> None:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor, admin)
            await conn.execute(
                text("INSERT INTO system_settings (key, value, updated_by) VALUES (:k, :v, :by)"),
                {"k": chave, "v": json.dumps(48), "by": sub},
            )
            await trans.commit()
        except BaseException:
            await trans.rollback()
            raise


async def test_admin_insere_configuracao(usuarios_engine: AsyncEngine) -> None:
    admin = str(uuid.uuid4())
    await _inserir_como(
        usuarios_engine, sub=admin, setor="studio", admin=True, chave="delay_horas_uteis"
    )
    async with usuarios_engine.connect() as conn:
        total = (await conn.execute(text("SELECT count(*) FROM system_settings"))).scalar_one()
    assert total == 1


@pytest.mark.parametrize(
    ("setor", "admin"),
    [("vendedor", False), ("motorista", False), ("clicheria", False), ("studio", False)],
)
async def test_nao_admin_nao_insere(usuarios_engine: AsyncEngine, setor: str, admin: bool) -> None:
    """Mesmo o setor STUDIO sem o flag admin é bloqueado (gate é o flag — ADR-023)."""
    with pytest.raises(DBAPIError):  # WITH CHECK de system_settings_insert_admin viola
        await _inserir_como(
            usuarios_engine, sub=str(uuid.uuid4()), setor=setor, admin=admin, chave="x"
        )


async def test_nao_admin_nao_atualiza(usuarios_engine: AsyncEngine) -> None:
    """O UPDATE de um não-admin é filtrado pela RLS (USING) — 0 linhas afetadas,
    SEM erro (semântica do Postgres, diferente do INSERT/WITH CHECK). O valor
    permanece intacto: a configuração não muda."""
    admin = str(uuid.uuid4())
    await _inserir_como(
        usuarios_engine, sub=admin, setor="studio", admin=True, chave="delay_horas_uteis"
    )  # value = 48
    async with usuarios_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, str(uuid.uuid4()), "vendedor", False)
            resultado = await conn.execute(
                text("UPDATE system_settings SET value = :v WHERE key = 'delay_horas_uteis'"),
                {"v": json.dumps(999)},
            )
            afetadas = resultado.rowcount
            await trans.commit()
        except BaseException:
            await trans.rollback()
            raise
    assert afetadas == 0  # RLS impediu o não-admin de tocar a linha
    # valor permanece o original (48) — a escrita do não-admin não teve efeito
    async with usuarios_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, admin, "studio", True)
            valor = (
                await conn.execute(
                    text("SELECT value FROM system_settings WHERE key = 'delay_horas_uteis'")
                )
            ).scalar_one()
        finally:
            await trans.rollback()
    assert valor == 48


async def test_leitura_e_aberta_a_qualquer_autenticado(usuarios_engine: AsyncEngine) -> None:
    """DP-2: o valor alimenta features de todos os perfis (C16/C06) — leitura livre."""
    admin = str(uuid.uuid4())
    await _inserir_como(
        usuarios_engine, sub=admin, setor="studio", admin=True, chave="delay_horas_uteis"
    )
    async with usuarios_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, str(uuid.uuid4()), "vendedor", False)
            visiveis = (await conn.execute(text("SELECT key FROM system_settings"))).scalars().all()
        finally:
            await trans.rollback()
    assert "delay_horas_uteis" in set(visiveis)


async def test_authenticated_nao_tem_grant_de_delete(usuarios_engine: AsyncEngine) -> None:
    """Privilégio mínimo (DP-2): DELETE não é concedido — a app nunca apaga config."""
    admin = str(uuid.uuid4())
    await _inserir_como(
        usuarios_engine, sub=admin, setor="studio", admin=True, chave="delay_horas_uteis"
    )
    with pytest.raises(DBAPIError, match=r"permission denied|InsufficientPrivilege"):
        async with usuarios_engine.connect() as conn:
            trans = await conn.begin()
            try:
                await _autenticar(conn, admin, "studio", True)
                await conn.execute(text("DELETE FROM system_settings"))
            finally:
                await trans.rollback()
