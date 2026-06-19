"""Timeline de UMA prova (W3-C13) contra Postgres REAL (@db).

Exercita ``GET /provas/{id}/movimentacoes`` no caminho HTTP inteiro como em
produção (``SET LOCAL ROLE authenticated`` + claims — ADR-008/ADR-034):

- MESMO escopo/gate do detalhe (Matriz §7): dados escopados pela RLS de
  ``movimentacoes`` (espelha ``provas``);
- ``etapas_canonicas`` deriva das regras do C11 (DP-1) — comprimento por rota;
- ``movimentacoes`` em ordem cronológica, com o RESPONSÁVEL resolvido inclusive
  CROSS-SETOR (Vendedor resolve o nome do 3Studio que moveu a prova dele — DP-2b);
- ``tem_assinatura`` é só o SELO (DP-2c — a imagem nunca trafega);
- reprovação carrega o ``motivo``;
- ANTI-ENUMERAÇÃO (§11): fora do escopo e inexistente → MESMO 404 genérico.
"""

import datetime as dt
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from src.adapters.inbound.http.auth import JwtVerifier
from src.domain.provas import Rota, gerar_codigo
from src.domain.state_machine.machine import sequencia_canonica
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _auth(sub: str, setor: str, admin: bool = False) -> dict[str, str]:
    now = dt.datetime.now(tz=dt.UTC)
    claims: dict[str, Any] = {
        "sub": sub,
        "user_id": sub,
        "setor": setor,
        "administrador": admin,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }
    return {"Authorization": f"Bearer {jwt.encode(claims, HS256_SECRET, algorithm='HS256')}"}


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


async def _seed_assinatura(engine: AsyncEngine, *, prova_id: str, ator_id: str) -> str:
    aid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO assinaturas (id, prova_id, ator_id, imagem, content_type) "
                "VALUES (:id, :prova, :ator, :img, 'image/png')"
            ),
            {"id": aid, "prova": prova_id, "ator": ator_id, "img": PNG_BYTES},
        )
    return aid


async def _seed_mov(
    engine: AsyncEngine,
    *,
    prova_id: str,
    ator_id: str,
    origem: str,
    destino: str,
    acao: str,
    assinatura_ref: str | None = None,
    motivo: str | None = None,
    minuto: int = 0,
) -> None:
    """Insere uma movimentação como OWNER (bypass RLS) — sem o motor (C11)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO movimentacoes (id, prova_id, estado_origem, estado_destino, acao, "
                "ator_id, motivo, assinatura_ref, idempotency_key, created_at) VALUES (:id, "
                ":prova, :origem, :destino, :acao, :ator, :motivo, :ass, :idem, :quando)"
            ),
            {
                "id": str(uuid.uuid4()),
                "prova": prova_id,
                "origem": origem,
                "destino": destino,
                "acao": acao,
                "ator": ator_id,
                "motivo": motivo,
                "ass": assinatura_ref,
                "idem": str(uuid.uuid4()),
                "quando": dt.datetime(2026, 4, 27, 10, minuto, tzinfo=dt.UTC),
            },
        )


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, dict[str, Any]]]:
    engine = usuarios_engine
    storage = FakeStorage()
    studio = await _seed_usuario(engine, setor="studio", nome="Studio Op")
    regiane = await _seed_usuario(engine, setor="vendedor", nome="Regiane")
    packon = await _seed_usuario(engine, setor="vendedor", nome="Packon")

    # Prova da Regiane em "de_volta_studio" (Matriz): 3 etapas percorridas, sendo a
    # última movida pelo 3Studio (ator CROSS-SETOR — resolução de nome do C13).
    p_reg = await _seed_prova(engine, vendedor_id=regiane, status="de_volta_studio", rota="matriz")
    a1 = await _seed_assinatura(engine, prova_id=p_reg, ator_id=regiane)
    a2 = await _seed_assinatura(engine, prova_id=p_reg, ator_id=regiane)
    a3 = await _seed_assinatura(engine, prova_id=p_reg, ator_id=studio)
    await _seed_mov(
        engine,
        prova_id=p_reg,
        ator_id=regiane,
        origem="criada",
        destino="retirada_vendedor",
        acao="identificar_e_assinar",
        assinatura_ref=a1,
        minuto=1,
    )
    await _seed_mov(
        engine,
        prova_id=p_reg,
        ator_id=regiane,
        origem="retirada_vendedor",
        destino="aprovada_vendedor",
        acao="aprovar",
        assinatura_ref=a2,
        minuto=2,
    )
    await _seed_mov(
        engine,
        prova_id=p_reg,
        ator_id=studio,
        origem="aprovada_vendedor",
        destino="de_volta_studio",
        acao="identificar_e_assinar",
        assinatura_ref=a3,
        minuto=3,
    )

    # Prova reprovada (motivo em destaque) + uma movimentação SEM assinatura (selo off).
    p_reprov = await _seed_prova(
        engine, vendedor_id=regiane, status="reprovada_vendedor", rota="filial"
    )
    a4 = await _seed_assinatura(engine, prova_id=p_reprov, ator_id=regiane)
    await _seed_mov(
        engine,
        prova_id=p_reprov,
        ator_id=regiane,
        origem="criada",
        destino="encaminhada_para_vendedor",
        acao="identificar_e_assinar",
        assinatura_ref=a4,
        minuto=1,
    )
    await _seed_mov(
        engine,
        prova_id=p_reprov,
        ator_id=regiane,
        origem="encaminhada_para_vendedor",
        destino="reprovada_vendedor",
        acao="reprovar",
        assinatura_ref=None,
        motivo="Cor saiu fora do padrão.",
        minuto=2,
    )

    # Prova do Packon — fora do escopo da Regiane (anti-enumeração).
    p_pack = await _seed_prova(engine, vendedor_id=packon, status="criada", rota="matriz")

    ids = {
        "studio": studio,
        "regiane": regiane,
        "packon": packon,
        "p_reg": p_reg,
        "p_reprov": p_reprov,
        "p_pack": p_pack,
    }
    client = make_client(
        settings,
        storage,
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    async with client as c:
        yield c, ids


async def test_timeline_da_propria_prova_com_esqueleto_e_responsaveis(ctx: tuple[Any, ...]) -> None:
    client, ids = ctx
    resp = await client.get(
        f"/provas/{ids['p_reg']}/movimentacoes", headers=_auth(ids["regiane"], "vendedor")
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rota"] == "matriz"
    assert body["estado_atual"] == "de_volta_studio"
    assert body["ciclo_atual"] == 1
    assert body["criada_em"] is not None
    # DP-1: esqueleto = sequência canônica da rota (derivada das regras do C11).
    assert body["etapas_canonicas"] == [e.value for e in sequencia_canonica(Rota.MATRIZ)]
    movs = body["movimentacoes"]
    assert [m["estado_destino"] for m in movs] == [
        "retirada_vendedor",
        "aprovada_vendedor",
        "de_volta_studio",
    ]
    # DP-2b: o Vendedor resolve o nome do 3Studio que moveu a prova dele (cross-setor).
    assert movs[2]["acao"] == "identificar_e_assinar"
    assert movs[2]["ator_nome"] == "Studio Op"
    assert movs[0]["ator_nome"] == "Regiane"
    # DP-2c: selo de assinatura, sem a imagem.
    assert all(m["tem_assinatura"] is True for m in movs)
    assert "assinatura" not in str(body).lower() or all("imagem" not in m for m in movs)


async def test_reprovacao_traz_motivo_e_selo_off_quando_sem_assinatura(
    ctx: tuple[Any, ...],
) -> None:
    client, ids = ctx
    resp = await client.get(
        f"/provas/{ids['p_reprov']}/movimentacoes", headers=_auth(ids["regiane"], "vendedor")
    )
    assert resp.status_code == 200
    movs = resp.json()["movimentacoes"]
    reprovacao = next(m for m in movs if m["acao"] == "reprovar")
    assert reprovacao["estado_destino"] == "reprovada_vendedor"
    assert reprovacao["motivo"] == "Cor saiu fora do padrão."
    assert reprovacao["tem_assinatura"] is False  # nenhuma assinatura vinculada


async def test_fora_do_escopo_e_inexistente_sao_o_mesmo_404(ctx: tuple[Any, ...]) -> None:
    client, ids = ctx
    fora = await client.get(
        f"/provas/{ids['p_pack']}/movimentacoes", headers=_auth(ids["regiane"], "vendedor")
    )
    inexistente = await client.get(
        f"/provas/{uuid.uuid4()}/movimentacoes", headers=_auth(ids["regiane"], "vendedor")
    )
    assert fora.status_code == inexistente.status_code == 404
    assert fora.json()["error"]["message"] == inexistente.json()["error"]["message"]
    assert fora.json()["error"]["message"] == "Prova não encontrada."


async def test_timeline_sem_token_e_401(ctx: tuple[Any, ...]) -> None:
    client, ids = ctx
    resp = await client.get(f"/provas/{ids['p_reg']}/movimentacoes")
    assert resp.status_code == 401
