"""RLS + imutabilidade de ``assinaturas`` (W3-C12) contra Postgres real (@db).

Valida, como o banco verá em produção (``SET LOCAL ROLE authenticated`` + claims):

- SELECT espelha o escopo de ``provas`` (via ``prova_id``): você vê a assinatura de
  uma prova SE vê a prova — Vendedor as suas, Motorista as operacionais,
  3Studio/Clicheria todas; fora do escopo → 0 registros;
- INSERT só com ``ator_id`` = você E prova no escopo (WITH CHECK);
- APPEND-ONLY: UPDATE/DELETE bloqueados pelo trigger até para o OWNER, e sem
  GRANT para o ``authenticated``.
"""

import datetime as dt
import json
import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from src.domain.provas import gerar_codigo

pytestmark = pytest.mark.db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


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
        text("SELECT set_config('request.jwt.claims', :c, true)"),
        {"c": _claims(sub, setor, admin)},
    )
    await conn.execute(text("SET LOCAL ROLE authenticated"))


async def _seed_usuario(engine: AsyncEngine, *, setor: str) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao) "
                "VALUES (:id, 'U', :email, :setor, :loc)"
            ),
            {"id": uid, "email": f"{uid}@x.z", "setor": setor, "loc": loc},
        )
    return uid


async def _seed_prova(engine: AsyncEngine, *, vendedor_id: str, status: str, rota: str) -> str:
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type) VALUES (:id, :codigo, 'P', '1', 'C', "
                ":vendedor, :rota, :status, 'provas/x/arte.png', 'image/png')"
            ),
            {
                "id": uid,
                "codigo": gerar_codigo(dt.datetime.now(tz=dt.UTC)),
                "vendedor": vendedor_id,
                "rota": rota,
                "status": status,
            },
        )
    return uid


async def _seed_assinatura(engine: AsyncEngine, *, prova_id: str, ator_id: str) -> str:
    """Insere uma assinatura como OWNER (bypass RLS) — sem o motor (C12)."""
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO assinaturas (id, prova_id, ator_id, imagem, content_type) "
                "VALUES (:id, :prova, :ator, :img, 'image/png')"
            ),
            {"id": uid, "prova": prova_id, "ator": ator_id, "img": PNG},
        )
    return uid


@pytest.fixture
async def cenario(usuarios_engine: AsyncEngine) -> dict[str, Any]:
    engine = usuarios_engine
    v1 = await _seed_usuario(engine, setor="vendedor")
    v2 = await _seed_usuario(engine, setor="vendedor")
    motorista = await _seed_usuario(engine, setor="motorista")
    clicheria = await _seed_usuario(engine, setor="clicheria")
    studio = await _seed_usuario(engine, setor="studio")

    p_v1 = await _seed_prova(engine, vendedor_id=v1, status="criada", rota="matriz")
    p_v2 = await _seed_prova(engine, vendedor_id=v2, status="criada", rota="matriz")
    p_transito = await _seed_prova(
        engine, vendedor_id=v1, status="com_motorista_ida_laminacao", rota="lam_matriz"
    )

    a_v1 = await _seed_assinatura(engine, prova_id=p_v1, ator_id=v1)
    a_v2 = await _seed_assinatura(engine, prova_id=p_v2, ator_id=v2)
    a_transito = await _seed_assinatura(engine, prova_id=p_transito, ator_id=motorista)

    return {
        "engine": engine,
        "v1": v1,
        "v2": v2,
        "motorista": motorista,
        "clicheria": clicheria,
        "studio": studio,
        "p_v1": p_v1,
        "p_v2": p_v2,
        "todas": {a_v1, a_v2, a_transito},
        "de_v1": {a_v1, a_transito},
        "de_v2": {a_v2},
        "motorista_ve": {a_transito},  # Em Trânsito
    }


async def _visiveis(engine: AsyncEngine, *, sub: str, setor: str, admin: bool = False) -> set[str]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor, admin)
            rows = (await conn.execute(text("SELECT id FROM assinaturas"))).scalars().all()
        finally:
            await trans.rollback()
    return {str(r) for r in rows}


# ---------------------------------------------------------------------------
# SELECT por perfil (espelha o escopo de provas)
# ---------------------------------------------------------------------------
async def test_studio_e_clicheria_veem_todas(cenario: dict[str, Any]) -> None:
    eng = cenario["engine"]
    assert await _visiveis(eng, sub=cenario["studio"], setor="studio") == cenario["todas"]
    assert await _visiveis(eng, sub=cenario["clicheria"], setor="clicheria") == cenario["todas"]


async def test_vendedor_ve_so_as_das_proprias_provas(cenario: dict[str, Any]) -> None:
    eng = cenario["engine"]
    assert await _visiveis(eng, sub=cenario["v1"], setor="vendedor") == cenario["de_v1"]
    assert await _visiveis(eng, sub=cenario["v2"], setor="vendedor") == cenario["de_v2"]


async def test_motorista_ve_do_escopo_operacional(cenario: dict[str, Any]) -> None:
    eng = cenario["engine"]
    visiveis = await _visiveis(eng, sub=cenario["motorista"], setor="motorista")
    assert visiveis == cenario["motorista_ve"]


async def test_query_fora_do_escopo_retorna_zero(cenario: dict[str, Any]) -> None:
    fantasma = str(uuid.uuid4())
    assert await _visiveis(cenario["engine"], sub=fantasma, setor="vendedor") == set()


# ---------------------------------------------------------------------------
# INSERT WITH CHECK (ator = você + prova no escopo)
# ---------------------------------------------------------------------------
async def _inserir_como(
    cenario: dict[str, Any], *, sub: str, setor: str, prova_id: str, ator_id: str
) -> None:
    engine: AsyncEngine = cenario["engine"]
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor)
            await conn.execute(
                text(
                    "INSERT INTO assinaturas (id, prova_id, ator_id, imagem, content_type) "
                    "VALUES (:id, :prova, :ator, :img, 'image/png')"
                ),
                {"id": str(uuid.uuid4()), "prova": prova_id, "ator": ator_id, "img": PNG},
            )
            await trans.commit()
        except BaseException:
            await trans.rollback()
            raise


async def test_insert_proprio_ator_em_prova_em_escopo_passa(cenario: dict[str, Any]) -> None:
    await _inserir_como(
        cenario,
        sub=cenario["v1"],
        setor="vendedor",
        prova_id=cenario["p_v1"],
        ator_id=cenario["v1"],
    )


async def test_insert_forjando_outro_ator_e_bloqueado(cenario: dict[str, Any]) -> None:
    with pytest.raises(DBAPIError):  # WITH CHECK: ator_id != app_current_user_id()
        await _inserir_como(
            cenario,
            sub=cenario["v1"],
            setor="vendedor",
            prova_id=cenario["p_v1"],
            ator_id=cenario["v2"],
        )


async def test_insert_para_prova_fora_do_escopo_e_bloqueado(cenario: dict[str, Any]) -> None:
    with pytest.raises(DBAPIError):  # WITH CHECK: EXISTS(prova visível) falha
        await _inserir_como(
            cenario,
            sub=cenario["v1"],
            setor="vendedor",
            prova_id=cenario["p_v2"],
            ator_id=cenario["v1"],
        )


# ---------------------------------------------------------------------------
# Imutabilidade (append-only) — trigger vale até para o owner; sem GRANT p/ auth
# ---------------------------------------------------------------------------
async def test_update_bloqueado_pelo_trigger_ate_para_owner(cenario: dict[str, Any]) -> None:
    engine: AsyncEngine = cenario["engine"]
    alvo = next(iter(cenario["todas"]))
    with pytest.raises(DBAPIError, match="append-only"):
        async with engine.begin() as conn:  # owner
            await conn.execute(
                text("UPDATE assinaturas SET content_type = 'image/jpeg' WHERE id = :id"),
                {"id": alvo},
            )


async def test_delete_bloqueado_pelo_trigger_ate_para_owner(cenario: dict[str, Any]) -> None:
    engine: AsyncEngine = cenario["engine"]
    alvo = next(iter(cenario["todas"]))
    with pytest.raises(DBAPIError, match="append-only"):
        async with engine.begin() as conn:  # owner
            await conn.execute(text("DELETE FROM assinaturas WHERE id = :id"), {"id": alvo})


async def test_authenticated_nao_tem_grant_de_update_nem_delete(cenario: dict[str, Any]) -> None:
    engine: AsyncEngine = cenario["engine"]
    alvo = next(iter(cenario["de_v1"]))
    for sql in (
        "UPDATE assinaturas SET content_type = 'image/jpeg' WHERE id = :id",
        "DELETE FROM assinaturas WHERE id = :id",
    ):
        match = r"permission denied|InsufficientPrivilege|append-only"
        with pytest.raises(DBAPIError, match=match):
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    await _autenticar(conn, cenario["v1"], "vendedor")
                    await conn.execute(text(sql), {"id": alvo})
                finally:
                    await trans.rollback()
