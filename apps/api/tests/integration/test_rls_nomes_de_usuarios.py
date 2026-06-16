"""Projeção ``private.nomes_de_usuarios`` (W3-C13/DP-2b) contra Postgres real (@db).

A Timeline resolve o NOME do responsável de cada movimentação (qualquer setor).
A função é SECURITY DEFINER (vê todas as linhas), mas RE-APLICA o escopo do
chamador (defesa em profundidade): só resolve nomes de atores em provas VISÍVEIS
a quem chama — espelhando as policies ``provas_select_*``. Aqui validamos esse
escopo como o banco verá em produção (``SET LOCAL ROLE authenticated`` + claims):

- 3Studio/Clicheria veem todas → resolvem qualquer ator;
- Vendedor resolve só atores das PRÓPRIAS provas (incl. o 3Studio/Motorista que as
  moveu — cross-setor), nunca o ator de prova de outro vendedor;
- Motorista resolve atores das provas no seu escopo operacional;
- fora do escopo → nada (mesmo passando o id correto).
"""

import datetime as dt
import json
import uuid
from typing import Any

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUuid
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from src.domain.provas import gerar_codigo

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


async def _seed_usuario(engine: AsyncEngine, *, setor: str, nome: str) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao) "
                "VALUES (:id, :nome, :email, :setor, :loc)"
            ),
            {"id": uid, "nome": nome, "email": f"{uid}@x.z", "setor": setor, "loc": loc},
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


async def _seed_mov(engine: AsyncEngine, *, prova_id: str, ator_id: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO movimentacoes (id, prova_id, estado_origem, estado_destino, acao, "
                "ator_id, idempotency_key) VALUES (:id, :prova, 'criada', 'retirada_vendedor', "
                "'identificar_e_assinar', :ator, :idem)"
            ),
            {
                "id": str(uuid.uuid4()),
                "prova": prova_id,
                "ator": ator_id,
                "idem": str(uuid.uuid4()),
            },
        )


@pytest.fixture
async def cenario(usuarios_engine: AsyncEngine) -> dict[str, Any]:
    engine = usuarios_engine
    v1 = await _seed_usuario(engine, setor="vendedor", nome="Vania")
    v2 = await _seed_usuario(engine, setor="vendedor", nome="Valdir")
    studio = await _seed_usuario(engine, setor="studio", nome="Sandro")
    motorista = await _seed_usuario(engine, setor="motorista", nome="Marcos")

    p_v1 = await _seed_prova(engine, vendedor_id=v1, status="criada", rota="matriz")
    p_v2 = await _seed_prova(engine, vendedor_id=v2, status="criada", rota="matriz")
    p_transito = await _seed_prova(
        engine, vendedor_id=v1, status="com_motorista_ida_laminacao", rota="lam_matriz"
    )

    # p_v1 movida por v1 e pelo studio; p_v2 por v2; p_transito pelo motorista.
    await _seed_mov(engine, prova_id=p_v1, ator_id=v1)
    await _seed_mov(engine, prova_id=p_v1, ator_id=studio)
    await _seed_mov(engine, prova_id=p_v2, ator_id=v2)
    await _seed_mov(engine, prova_id=p_transito, ator_id=motorista)

    return {
        "engine": engine,
        "v1": v1,
        "v2": v2,
        "studio": studio,
        "motorista": motorista,
        "todos_ids": [v1, v2, studio, motorista],
    }


async def _resolver(
    engine: AsyncEngine, ids: list[str], *, sub: str, setor: str, admin: bool = False
) -> dict[str, str]:
    stmt = text("SELECT id, nome FROM private.nomes_de_usuarios(:ids)").bindparams(
        bindparam("ids", value=ids, type_=ARRAY(PgUuid(as_uuid=False)))
    )
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor, admin)
            rows = (await conn.execute(stmt)).all()
        finally:
            await trans.rollback()
    return {str(r.id): r.nome for r in rows}


async def test_studio_resolve_qualquer_ator(cenario: dict[str, Any]) -> None:
    resolvidos = await _resolver(
        cenario["engine"], cenario["todos_ids"], sub=cenario["studio"], setor="studio"
    )
    assert resolvidos == {
        cenario["v1"]: "Vania",
        cenario["v2"]: "Valdir",
        cenario["studio"]: "Sandro",
        cenario["motorista"]: "Marcos",
    }


async def test_vendedor_resolve_atores_das_proprias_provas_inclusive_cross_setor(
    cenario: dict[str, Any],
) -> None:
    # v1 vê p_v1 (movida por v1 e studio) e p_transito (movida pelo motorista),
    # mas NÃO p_v2 — então não resolve v2.
    resolvidos = await _resolver(
        cenario["engine"], cenario["todos_ids"], sub=cenario["v1"], setor="vendedor"
    )
    assert set(resolvidos) == {cenario["v1"], cenario["studio"], cenario["motorista"]}
    assert cenario["v2"] not in resolvidos


async def test_vendedor_nao_resolve_ator_de_prova_alheia(cenario: dict[str, Any]) -> None:
    # v2 vê só p_v2 (própria) → resolve só a si mesmo, mesmo passando todos os ids.
    resolvidos = await _resolver(
        cenario["engine"], cenario["todos_ids"], sub=cenario["v2"], setor="vendedor"
    )
    assert set(resolvidos) == {cenario["v2"]}


async def test_motorista_resolve_atores_do_escopo_operacional(cenario: dict[str, Any]) -> None:
    # Motorista vê p_transito (Em Trânsito) → resolve o ator dela; não vê as "criada".
    resolvidos = await _resolver(
        cenario["engine"], cenario["todos_ids"], sub=cenario["motorista"], setor="motorista"
    )
    assert set(resolvidos) == {cenario["motorista"]}


async def test_fora_do_escopo_nao_resolve_nada(cenario: dict[str, Any]) -> None:
    fantasma = str(uuid.uuid4())
    resolvidos = await _resolver(
        cenario["engine"], cenario["todos_ids"], sub=fantasma, setor="vendedor"
    )
    assert resolvidos == {}
