"""Endpoints do Log de Auditoria (W6-C20) contra Postgres REAL (@db).

Exercita ``GET /auditoria`` + ``/atores`` + ``POST /verificar-integridade`` pelo
caminho HTTP inteiro (``SET LOCAL ROLE authenticated`` + claims). A captura é
gerada pelos casos de uso reais (criação C06, escaneamento C10, transição C11) —
este teste prova que o log é a janela read-only fiel ao design:

- master-detail: cada evento traz ator (nome+setor), prova, IP, origem e hash;
- IP/origem capturados do request (X-Forwarded-For + User-Agent) — middleware;
- filtros server-side (evento, ator, paginação) — sem N+1;
- ACESSO 3Studio em duas camadas: não-admin → 403 em TODOS os endpoints;
- READ-ONLY: não há rota de mutação (DELETE/PUT → 405);
- integridade: o chain recém-criado é íntegro.
"""

import base64
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
from src.application.ports.arte_fonte import ArteSelecionada
from src.domain.requerimentos import RequerimentoArte
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import (
    FakeArteFonte,
    FakeRequerimentoReader,
    FakeStorage,
    make_client,
    ping_ok,
)

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"
JPEG_MINIMO = b"\xff\xd8\xff\xe0" + b"\x00" * 32
COD_REQ = 155295
COD_VENDE = 10
_REQ = RequerimentoArte(
    cod_req_art=COD_REQ,
    nome="Etiqueta Cafe",
    cod_cliente=1058,
    nome_cliente="Cafe Caproni",
    cod_vendedor=COD_VENDE,
    nome_vendedor="V",
    cod_vend_fat=10,
    anexo_imagem="V1.jpg",
)
_ARTE = ArteSelecionada(JPEG_MINIMO, "image/jpeg", "V1.jpg")
# UA de Chrome + IP via X-Forwarded-For: torna IP/origem DETERMINÍSTICOS na captura.
UA_CHROME = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537 (KHTML) Chrome/120 Safari/537"
IP_CLIENTE = "203.0.113.7"
# Imagem mínima que passa por validar_assinatura (magic bytes de PNG), em base64.
ASSINATURA = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16).decode()


def _token(sub: str, setor: str, administrador: bool = False) -> str:
    now = dt.datetime.now(tz=dt.UTC)
    claims: dict[str, Any] = {
        "sub": sub,
        "user_id": sub,
        "email": "x@y.z",
        "setor": setor,
        "administrador": administrador,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }
    return jwt.encode(claims, HS256_SECRET, algorithm="HS256")


def _auth(sub: str, setor: str, admin: bool = False, *, origem: bool = False) -> dict[str, str]:
    h = {"Authorization": f"Bearer {_token(sub, setor, admin)}"}
    if origem:
        h["User-Agent"] = UA_CHROME
        h["X-Forwarded-For"] = IP_CLIENTE
    return h


async def _seed_usuario(
    engine: AsyncEngine,
    *,
    setor: str,
    nome: str,
    admin: bool = False,
    cod_firebird: int | None = None,
) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador, "
                "cod_vendedor_firebird) VALUES (:id, :nome, :email, :setor, :loc, :adm, :cod)"
            ),
            {
                "id": uid,
                "nome": nome,
                "email": f"{uid}@x.z",
                "setor": setor,
                "loc": loc,
                "adm": admin,
                "cod": cod_firebird,
            },
        )
    return uid


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, dict[str, str]]]:
    engine = usuarios_engine
    ids = {
        "admin": await _seed_usuario(engine, setor="studio", nome="Monica", admin=True),
        "vendedor": await _seed_usuario(
            engine, setor="vendedor", nome="Renan Petrim", cod_firebird=COD_VENDE
        ),
    }
    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
        requerimento_reader=FakeRequerimentoReader({COD_REQ: _REQ}),
        arte_fonte=FakeArteFonte(_ARTE),
    )
    async with client as c:
        yield c, engine, ids


async def _gerar_eventos(client: httpx.AsyncClient, ids: dict[str, str]) -> str:
    """Gera os 3 tipos de evento e devolve o código da prova criada.

    criou_prova (admin) → escaneou_qr (vendedor) → mudou_status (vendedor), todos
    com IP/UA determinísticos (origem=True)."""
    criada = await client.post(
        "/provas",
        json={"cod_req_art": COD_REQ, "rota": "matriz"},
        headers=_auth(ids["admin"], "studio", True, origem=True),
    )
    assert criada.status_code == 201, criada.text
    prova = criada.json()
    codigo = prova["codigo"]

    ident = await client.post(
        "/provas/identificar",
        json={"codigo": codigo},
        headers=_auth(ids["vendedor"], "vendedor", origem=True),
    )
    assert ident.status_code == 200, ident.text

    trans = await client.post(
        f"/provas/{prova['id']}/transicoes",
        json={
            "acao": "identificar_e_assinar",
            "assinatura": ASSINATURA,
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=_auth(ids["vendedor"], "vendedor", origem=True),
    )
    assert trans.status_code == 200, trans.text
    return codigo


async def test_master_detail_fiel_ao_design(ctx: tuple[Any, ...]) -> None:
    client, _engine, ids = ctx
    codigo = await _gerar_eventos(client, ids)

    resp = await client.get("/auditoria", headers=_auth(ids["admin"], "studio", True))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 3
    eventos = {i["evento"] for i in body["items"]}
    assert {"criou_prova", "escaneou_qr", "mudou_status"} <= eventos

    # Ordem "recentes" (seq desc): a transição (último append) vem primeiro.
    topo = body["items"][0]
    assert topo["evento"] == "mudou_status"
    assert topo["ator_nome"] == "Renan Petrim"
    assert topo["ator_setor"] == "vendedor"
    assert topo["estado_origem"] == "criada"
    assert topo["estado_destino"] == "retirada_vendedor"
    assert topo["acao"] == "identificar_e_assinar"
    assert topo["prova_codigo"] == codigo
    assert topo["prova_requerimento"] == "155295"
    # Captura de origem (middleware): IP do X-Forwarded-For + UA → rótulo.
    assert topo["ip"] == IP_CLIENTE
    assert topo["origem"] == "Aplicação Web · Chrome"
    # Chain: hash hex de 64 chars (sha256), sempre presente.
    assert len(topo["hash"]) == 64
    assert all(c in "0123456789abcdef" for c in topo["hash"])


async def test_filtro_por_evento(ctx: tuple[Any, ...]) -> None:
    client, _engine, ids = ctx
    await _gerar_eventos(client, ids)
    resp = await client.get(
        "/auditoria", params={"evento": "criou_prova"}, headers=_auth(ids["admin"], "studio", True)
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items and all(i["evento"] == "criou_prova" for i in items)


async def test_filtro_por_ator(ctx: tuple[Any, ...]) -> None:
    client, _engine, ids = ctx
    await _gerar_eventos(client, ids)
    resp = await client.get(
        "/auditoria",
        params={"ator_id": ids["vendedor"]},
        headers=_auth(ids["admin"], "studio", True),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    # Só os eventos do vendedor (escaneou_qr + mudou_status) — nunca o criou_prova (admin).
    assert items and all(i["ator_id"] == ids["vendedor"] for i in items)
    assert {i["evento"] for i in items} == {"escaneou_qr", "mudou_status"}


async def test_paginacao_server_side(ctx: tuple[Any, ...]) -> None:
    client, _engine, ids = ctx
    await _gerar_eventos(client, ids)
    resp = await client.get(
        "/auditoria", params={"page_size": 1}, headers=_auth(ids["admin"], "studio", True)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["total"] >= 3
    assert body["page_size"] == 1


async def test_atores_distintos(ctx: tuple[Any, ...]) -> None:
    client, _engine, ids = ctx
    await _gerar_eventos(client, ids)
    resp = await client.get("/auditoria/atores", headers=_auth(ids["admin"], "studio", True))
    assert resp.status_code == 200
    atores = {a["id"] for a in resp.json()}
    assert ids["admin"] in atores
    assert ids["vendedor"] in atores


async def test_verificar_integridade_chain_intacto(ctx: tuple[Any, ...]) -> None:
    client, _engine, ids = ctx
    await _gerar_eventos(client, ids)
    resp = await client.post(
        "/auditoria/verificar-integridade", headers=_auth(ids["admin"], "studio", True)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["intacto"] is True
    assert body["total"] >= 3
    assert body["quebrou_em"] is None


# ---------------------------------------------------------------------------
# Acesso 3Studio em duas camadas (gate + RLS) — não-admin → 403 em tudo
# ---------------------------------------------------------------------------
async def test_nao_admin_bloqueado_em_todos_os_endpoints(ctx: tuple[Any, ...]) -> None:
    client, _engine, ids = ctx
    await _gerar_eventos(client, ids)
    v = _auth(ids["vendedor"], "vendedor")
    assert (await client.get("/auditoria", headers=v)).status_code == 403
    assert (await client.get("/auditoria/atores", headers=v)).status_code == 403
    assert (await client.post("/auditoria/verificar-integridade", headers=v)).status_code == 403


async def test_log_e_read_only(ctx: tuple[Any, ...]) -> None:
    """Não há rota de mutação do log — DELETE/PUT/PATCH em /auditoria → 405."""
    client, _engine, ids = ctx
    h = _auth(ids["admin"], "studio", True)
    assert (await client.delete("/auditoria", headers=h)).status_code == 405
    assert (await client.put("/auditoria", headers=h, json={})).status_code == 405
    assert (await client.patch("/auditoria", headers=h, json={})).status_code == 405
