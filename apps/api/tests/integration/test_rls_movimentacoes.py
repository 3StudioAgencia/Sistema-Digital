"""RLS + imutabilidade de ``movimentacoes`` (W3-C11) contra Postgres real (@db).

Valida, como o banco verá em produção (``SET LOCAL ROLE authenticated`` + claims):

- SELECT espelha o escopo de ``provas`` (DP-3): você vê as movimentações de uma
  prova SE vê a prova — Vendedor as suas, Motorista as operacionais,
  3Studio/Clicheria todas; fora do escopo → 0 registros;
- INSERT só com ``ator_id`` = você E prova no escopo (WITH CHECK);
- APPEND-ONLY: UPDATE/DELETE bloqueados pelo trigger até para o OWNER, e sem
  GRANT para o ``authenticated``;
- ``acao_enum`` espelha o domínio (sincronização Python↔PG).
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
from src.domain.state_machine.enums import Acao

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


async def _seed_mov(engine: AsyncEngine, *, prova_id: str, ator_id: str) -> str:
    """Insere uma movimentação como OWNER (bypass RLS) — sem o motor (C11)."""
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO movimentacoes (id, prova_id, estado_origem, estado_destino, acao, "
                "ator_id, idempotency_key) VALUES (:id, :prova, 'criada', 'retirada_vendedor', "
                "'identificar_e_assinar', :ator, :idem)"
            ),
            {"id": uid, "prova": prova_id, "ator": ator_id, "idem": str(uuid.uuid4())},
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
    p_origem = await _seed_prova(
        engine, vendedor_id=v1, status="encaminhada_para_laminacao", rota="lam_matriz"
    )

    m_v1 = await _seed_mov(engine, prova_id=p_v1, ator_id=v1)
    m_v2 = await _seed_mov(engine, prova_id=p_v2, ator_id=v2)
    m_transito = await _seed_mov(engine, prova_id=p_transito, ator_id=motorista)
    m_origem = await _seed_mov(engine, prova_id=p_origem, ator_id=motorista)

    return {
        "engine": engine,
        "v1": v1,
        "v2": v2,
        "motorista": motorista,
        "clicheria": clicheria,
        "studio": studio,
        "p_v1": p_v1,
        "p_v2": p_v2,
        "todas_movs": {m_v1, m_v2, m_transito, m_origem},
        "de_v1": {m_v1, m_transito, m_origem},
        "de_v2": {m_v2},
        "motorista_ve": {m_transito, m_origem},  # operacional: Em Trânsito + origem
    }


async def _movs_visiveis(
    engine: AsyncEngine, *, sub: str, setor: str, admin: bool = False
) -> set[str]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor, admin)
            rows = (await conn.execute(text("SELECT id FROM movimentacoes"))).scalars().all()
        finally:
            await trans.rollback()
    return {str(r) for r in rows}


# ---------------------------------------------------------------------------
# SELECT por perfil (espelha o escopo de provas)
# ---------------------------------------------------------------------------
async def test_studio_e_clicheria_veem_todas(cenario: dict[str, Any]) -> None:
    eng = cenario["engine"]
    assert await _movs_visiveis(eng, sub=cenario["studio"], setor="studio") == cenario["todas_movs"]
    assert (
        await _movs_visiveis(eng, sub=cenario["clicheria"], setor="clicheria")
        == cenario["todas_movs"]
    )


async def test_vendedor_ve_so_as_movs_das_proprias_provas(cenario: dict[str, Any]) -> None:
    eng = cenario["engine"]
    assert await _movs_visiveis(eng, sub=cenario["v1"], setor="vendedor") == cenario["de_v1"]
    assert await _movs_visiveis(eng, sub=cenario["v2"], setor="vendedor") == cenario["de_v2"]


async def test_motorista_ve_movs_do_escopo_operacional(cenario: dict[str, Any]) -> None:
    eng = cenario["engine"]
    visiveis = await _movs_visiveis(eng, sub=cenario["motorista"], setor="motorista")
    assert visiveis == cenario["motorista_ve"]  # Em Trânsito + origem, não as "criada"


async def test_query_fora_do_escopo_retorna_zero(cenario: dict[str, Any]) -> None:
    fantasma = str(uuid.uuid4())
    assert await _movs_visiveis(cenario["engine"], sub=fantasma, setor="vendedor") == set()


# ---------------------------------------------------------------------------
# INSERT WITH CHECK (ator = você + prova no escopo)
# ---------------------------------------------------------------------------
async def _inserir_mov_como(
    cenario: dict[str, Any], *, sub: str, setor: str, prova_id: str, ator_id: str
) -> None:
    engine: AsyncEngine = cenario["engine"]
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor)
            await conn.execute(
                text(
                    "INSERT INTO movimentacoes (id, prova_id, estado_origem, estado_destino, "
                    "acao, ator_id, idempotency_key) VALUES (:id, :prova, 'criada', "
                    "'retirada_vendedor', 'identificar_e_assinar', :ator, :idem)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "prova": prova_id,
                    "ator": ator_id,
                    "idem": str(uuid.uuid4()),
                },
            )
            await trans.commit()
        except BaseException:
            await trans.rollback()
            raise


async def test_insert_proprio_ator_em_prova_em_escopo_passa(cenario: dict[str, Any]) -> None:
    await _inserir_mov_como(
        cenario,
        sub=cenario["v1"],
        setor="vendedor",
        prova_id=cenario["p_v1"],
        ator_id=cenario["v1"],
    )


async def test_insert_forjando_outro_ator_e_bloqueado(cenario: dict[str, Any]) -> None:
    with pytest.raises(DBAPIError):  # WITH CHECK: ator_id != app_current_user_id()
        await _inserir_mov_como(
            cenario,
            sub=cenario["v1"],
            setor="vendedor",
            prova_id=cenario["p_v1"],
            ator_id=cenario["v2"],
        )


async def test_insert_para_prova_fora_do_escopo_e_bloqueado(cenario: dict[str, Any]) -> None:
    with pytest.raises(DBAPIError):  # WITH CHECK: EXISTS(prova visível) falha
        await _inserir_mov_como(
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
    alvo = next(iter(cenario["todas_movs"]))
    with pytest.raises(DBAPIError, match="append-only"):
        async with engine.begin() as conn:  # owner
            await conn.execute(
                text("UPDATE movimentacoes SET motivo = 'x' WHERE id = :id"), {"id": alvo}
            )


async def test_delete_bloqueado_pelo_trigger_ate_para_owner(cenario: dict[str, Any]) -> None:
    engine: AsyncEngine = cenario["engine"]
    alvo = next(iter(cenario["todas_movs"]))
    with pytest.raises(DBAPIError, match="append-only"):
        async with engine.begin() as conn:  # owner
            await conn.execute(text("DELETE FROM movimentacoes WHERE id = :id"), {"id": alvo})


async def test_authenticated_nao_tem_grant_de_update_nem_delete(cenario: dict[str, Any]) -> None:
    engine: AsyncEngine = cenario["engine"]
    alvo = next(iter(cenario["de_v1"]))
    for sql in (
        "UPDATE movimentacoes SET motivo = 'x' WHERE id = :id",
        "DELETE FROM movimentacoes WHERE id = :id",
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


# ---------------------------------------------------------------------------
# Sincronização do enum acao_enum ↔ domínio
# ---------------------------------------------------------------------------
async def test_acao_enum_espelha_o_dominio(cenario: dict[str, Any]) -> None:
    engine: AsyncEngine = cenario["engine"]
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                    "WHERE t.typname = 'acao_enum' ORDER BY e.enumsortorder"
                )
            )
        ).scalars().all()
    assert list(rows) == [a.value for a in Acao]
