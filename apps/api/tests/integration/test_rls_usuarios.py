"""RLS definitiva de ``usuarios`` (W1-C05) contra Postgres real (@db).

Exercita as policies como o banco as vera em producao: sob ``SET LOCAL ROLE
authenticated`` + ``request.jwt.claims`` propagados (o que a UoW faz por
requisicao — ADR-008). Valida a Matriz §7 a nivel de DADO:
- admin (flag) le/gerencia todos;
- nao-admin le apenas a propria linha (``/me``) e 0 alheias (criterio §6.3);
- mutacoes (insert/update/delete) so passam para admin.
"""

import json
import uuid
from typing import Any

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


async def _seed(
    engine: AsyncEngine, *, setor: str, administrador: bool, localizacao: str | None = None
) -> str:
    """Insere uma linha como OWNER (RLS bypass) — prepara o estado do teste."""
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id, :nome, :email, :setor, :loc, :adm)"
            ),
            {
                "id": uid,
                "nome": "U",
                "email": f"{uid}@x.z",
                "setor": setor,
                "loc": localizacao,
                "adm": administrador,
            },
        )
    return uid


async def _autenticar(conn: AsyncConnection, sub: str, setor: str, admin: bool) -> None:
    """Propaga os claims e troca para a role authenticated NA transacao corrente
    (espelha exatamente a propagacao da UoW — ADR-008)."""
    await conn.execute(
        text("SELECT set_config('request.jwt.claims', :c, true)"),
        {"c": _claims(sub, setor, admin)},
    )
    await conn.execute(text("SET LOCAL ROLE authenticated"))


async def _ids_visiveis(engine: AsyncEngine, *, sub: str, setor: str, admin: bool) -> set[str]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor, admin)
            rows = (await conn.execute(text("SELECT id FROM usuarios"))).scalars().all()
        finally:
            await trans.rollback()
    return {str(r) for r in rows}


@pytest.fixture
async def cenario(usuarios_engine: AsyncEngine) -> dict[str, Any]:
    """Quatro usuarios: um admin (studio) e tres nao-admin de setores distintos."""
    admin = await _seed(usuarios_engine, setor="studio", administrador=True)
    vendedor = await _seed(
        usuarios_engine, setor="vendedor", administrador=False, localizacao="matriz"
    )
    motorista = await _seed(usuarios_engine, setor="motorista", administrador=False)
    clicheria = await _seed(usuarios_engine, setor="clicheria", administrador=False)
    return {
        "engine": usuarios_engine,
        "admin": admin,
        "vendedor": vendedor,
        "motorista": motorista,
        "clicheria": clicheria,
        "todos": {admin, vendedor, motorista, clicheria},
    }


async def test_admin_le_todos(cenario: dict[str, Any]) -> None:
    visiveis = await _ids_visiveis(
        cenario["engine"], sub=cenario["admin"], setor="studio", admin=True
    )
    assert visiveis == cenario["todos"]


@pytest.mark.parametrize("setor", ["vendedor", "motorista", "clicheria"])
async def test_nao_admin_le_apenas_a_propria_linha(cenario: dict[str, Any], setor: str) -> None:
    eu = cenario[setor]
    visiveis = await _ids_visiveis(cenario["engine"], sub=eu, setor=setor, admin=False)
    assert visiveis == {eu}  # self policy: vê a si; 0 das alheias (§6.3)


async def test_query_direta_fora_do_escopo_retorna_zero(cenario: dict[str, Any]) -> None:
    """Um autenticado SEM linha (sub fantasma) e nao-admin: 0 registros."""
    fantasma = str(uuid.uuid4())
    visiveis = await _ids_visiveis(
        cenario["engine"], sub=fantasma, setor="vendedor", admin=False
    )
    assert visiveis == set()


async def test_admin_insere_com_sucesso(cenario: dict[str, Any]) -> None:
    engine = cenario["engine"]
    novo = str(uuid.uuid4())
    async with engine.connect() as conn:
        trans = await conn.begin()
        await _autenticar(conn, cenario["admin"], "studio", True)
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, administrador) "
                "VALUES (:id, 'N', :email, 'clicheria', false)"
            ),
            {"id": novo, "email": f"{novo}@x.z"},
        )
        await trans.commit()
    # Confirma persistencia (via admin, que le todos).
    visiveis = await _ids_visiveis(engine, sub=cenario["admin"], setor="studio", admin=True)
    assert novo in visiveis


async def test_nao_admin_insert_e_bloqueado(cenario: dict[str, Any]) -> None:
    engine = cenario["engine"]
    novo = str(uuid.uuid4())
    with pytest.raises(DBAPIError):  # WITH CHECK da policy de insert viola
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                await _autenticar(conn, cenario["vendedor"], "vendedor", False)
                await conn.execute(
                    text(
                        "INSERT INTO usuarios (id, nome, email, setor, administrador) "
                        "VALUES (:id, 'N', :email, 'clicheria', false)"
                    ),
                    {"id": novo, "email": f"{novo}@x.z"},
                )
            finally:
                await trans.rollback()


async def test_nao_admin_update_alheio_nao_afeta_linhas(cenario: dict[str, Any]) -> None:
    """UPDATE de um nao-admin sobre linha alheia: USING filtra → 0 linhas (sem vazar)."""
    engine = cenario["engine"]
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, cenario["vendedor"], "vendedor", False)
            result = await conn.execute(
                text("UPDATE usuarios SET nome = 'HACK' WHERE id = :alvo"),
                {"alvo": cenario["admin"]},
            )
            assert result.rowcount == 0
        finally:
            await trans.rollback()
