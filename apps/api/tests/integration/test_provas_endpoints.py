"""Endpoints de provas (Fatia 3) contra Postgres REAL (@db) — criação por
REQUERIMENTO: resolução no ERP + mapeamento do vendedor + snapshot da imagem, gate
de admin e etiqueta PDF.

ERP e servidor de arquivos mockados (FakeRequerimentoReader/FakeArteFonte); JWT
HS256 de teste no formato pós-hook. A ``session_factory`` injetada é a de REQUEST
(fail-closed — ADR-034): o caminho HTTP inteiro roda com a RLS valendo.
"""

import datetime as dt
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from src.adapters.inbound.http.auth import JwtVerifier
from src.adapters.outbound.db.models import UsuarioRow
from src.application.ports.arte_fonte import ArteFonteError, ArteSelecionada
from src.application.ports.requerimentos import RequerimentoReaderError
from src.domain.provas import CODIGO_REGEX
from src.domain.requerimentos import ArteNaoDisponivelError, RequerimentoArte
from src.domain.usuarios import Localizacao, Setor
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
ADMIN_ID = "11111111-1111-1111-1111-111111111111"
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"
COD_REQ = 150288
COD_VENDE = 10
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32

REQ = RequerimentoArte(
    cod_req_art=COD_REQ,
    nome="QUEIJO MUSSARELA FLORA MILK",
    cod_cliente=1058,
    nome_cliente="LATICINIOS FLORIDA LTDA",
    cod_vendedor=COD_VENDE,
    nome_vendedor="REGISLAINE PETRIM",
    cod_vend_fat=10,
    anexo_imagem="VERSAO_150288_V3.jpg",
)
ARTE = ArteSelecionada(conteudo=JPEG, content_type="image/jpeg", nome_arquivo="V3.jpg")


def _token(sub: str, **overrides: Any) -> str:
    now = dt.datetime.now(tz=dt.UTC)
    claims: dict[str, Any] = {
        "sub": sub,
        "user_id": sub,
        "email": "x@y.z",
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }
    claims.update(overrides)
    return jwt.encode(claims, HS256_SECRET, algorithm="HS256")


def _auth_admin() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(ADMIN_ID, setor='studio', administrador=True)}"}


def _auth_vendedor() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(VENDEDOR_ID, setor='vendedor')}"}


async def _seed_usuarios(engine: AsyncEngine) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UsuarioRow(
                id=ADMIN_ID,
                nome="Mônica",
                email="monica@3studio.test",
                setor=Setor.STUDIO,
                administrador=True,
            )
        )
        session.add(
            UsuarioRow(
                id=VENDEDOR_ID,
                nome="Regislaine Petrim",
                email="regislaine@3studio.test",
                setor=Setor.VENDEDOR,
                localizacao=Localizacao.MATRIZ,
                cod_vendedor_firebird=COD_VENDE,  # mapeia ao COD_VENDE do requerimento
            )
        )
        await session.commit()


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, FakeStorage, FakeRequerimentoReader, FakeArteFonte]]:
    storage = FakeStorage()
    firebird = FakeRequerimentoReader({COD_REQ: REQ})
    arte_fonte = FakeArteFonte(ARTE)
    client = make_client(
        settings,
        storage,
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(usuarios_engine),
        requerimento_reader=firebird,
        arte_fonte=arte_fonte,
    )
    await _seed_usuarios(usuarios_engine)
    async with client as c:
        yield c, storage, firebird, arte_fonte


def _body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"cod_req_art": COD_REQ, "rota": "matriz"}
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


async def _criar_ok(client: httpx.AsyncClient) -> dict[str, Any]:
    resp = await client.post("/provas", json=_body(), headers=_auth_admin())
    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    return body


# ---------------------------------------------------------------------------
# Criação por requerimento (US-001)
# ---------------------------------------------------------------------------
async def test_criar_prova_resolve_do_erp(ctx: tuple[Any, ...]) -> None:
    client, storage, _, _ = ctx
    body = await _criar_ok(client)

    assert CODIGO_REGEX.fullmatch(body["codigo"])  # RF-002
    assert body["status"] == "criada"  # US-001
    assert body["rota"] == "matriz"
    assert body["requerimento"] == str(COD_REQ)
    assert body["nome"] == "QUEIJO MUSSARELA FLORA MILK"  # PRODART do ERP
    assert body["cliente"] == "LATICINIOS FLORIDA LTDA"  # TB_CLIENTES.CLIENTE
    assert body["vendedor_id"] == VENDEDOR_ID  # COD_VENDE -> usuário do app
    assert storage.download(f"provas/{body['id']}/arte.jpg") == JPEG  # snapshot


async def test_requerimento_inexistente_e_404(ctx: tuple[Any, ...]) -> None:
    client, _, _, _ = ctx
    resp = await client.post("/provas", json=_body(cod_req_art=999999), headers=_auth_admin())
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "requerimento_nao_encontrado"


async def test_requerimento_incompleto_e_422(ctx: tuple[Any, ...]) -> None:
    client, storage, firebird, _ = ctx
    firebird._dados[COD_REQ] = RequerimentoArte(
        COD_REQ, "Prod", 1058, "Cli", COD_VENDE, "Vend", None, "a.jpg"  # cod_vend_fat None
    )
    resp = await client.post("/provas", json=_body(), headers=_auth_admin())
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "requerimento_incompleto"
    assert storage._objects == {}


async def test_vendedor_nao_mapeado_e_422(ctx: tuple[Any, ...]) -> None:
    client, storage, firebird, _ = ctx
    # requerimento cujo COD_VENDE não corresponde a nenhum usuário cadastrado
    firebird._dados[COD_REQ] = RequerimentoArte(
        COD_REQ, "Prod", 1058, "Cli", 99999, "Vend", 10, "a.jpg"
    )
    resp = await client.post("/provas", json=_body(), headers=_auth_admin())
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "vendedor_nao_mapeado"
    assert storage._objects == {}


async def test_arte_indisponivel_e_422(ctx: tuple[Any, ...]) -> None:
    client, storage, _, arte_fonte = ctx
    arte_fonte.erro = ArteNaoDisponivelError()
    resp = await client.post("/provas", json=_body(), headers=_auth_admin())
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "arte_indisponivel"
    assert storage._objects == {}


async def test_erp_fora_do_ar_e_503(ctx: tuple[Any, ...]) -> None:
    client, _, firebird, _ = ctx
    firebird.erro = RequerimentoReaderError("ERP down")
    resp = await client.post("/provas", json=_body(), headers=_auth_admin())
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "erp_indisponivel"


async def test_share_fora_do_ar_e_503(ctx: tuple[Any, ...]) -> None:
    client, _, _, arte_fonte = ctx
    arte_fonte.erro = ArteFonteError("share down")
    resp = await client.post("/provas", json=_body(), headers=_auth_admin())
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "arte_fonte_indisponivel"


async def test_sem_rota_retorna_422(ctx: tuple[Any, ...]) -> None:
    client, _, _, _ = ctx
    resp = await client.post("/provas", json=_body(rota=None), headers=_auth_admin())
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_cod_req_art_nao_positivo_retorna_422(ctx: tuple[Any, ...]) -> None:
    client, _, _, _ = ctx
    resp = await client.post("/provas", json=_body(cod_req_art=0), headers=_auth_admin())
    assert resp.status_code == 422


async def test_reenvio_com_prova_id_e_idempotente(ctx: tuple[Any, ...]) -> None:
    """RNF-015: resposta perdida + retry com a MESMA chave não duplica prova."""
    client, _, _, _ = ctx
    chave = str(uuid.uuid4())

    primeira = await client.post("/provas", json=_body(prova_id=chave), headers=_auth_admin())
    segunda = await client.post("/provas", json=_body(prova_id=chave), headers=_auth_admin())

    assert primeira.status_code == 201 and segunda.status_code == 201
    assert segunda.json()["id"] == primeira.json()["id"]
    assert segunda.json()["codigo"] == primeira.json()["codigo"]

    # mesma chave com rota DIFERENTE → 409, nunca sobrescrita
    divergente = await client.post(
        "/provas", json=_body(prova_id=chave, rota="filial"), headers=_auth_admin()
    )
    assert divergente.status_code == 409
    assert divergente.json()["error"]["code"] == "criacao_divergente"


# ---------------------------------------------------------------------------
# Gate de admin (Matriz §7, "Criar Prova") e superfícies inexistentes
# ---------------------------------------------------------------------------
async def test_nao_admin_recebe_403_generico(ctx: tuple[Any, ...]) -> None:
    client, _, _, _ = ctx
    resp = await client.post("/provas", json=_body(), headers=_auth_vendedor())
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "Acesso negado."


async def test_sem_token_recebe_401(ctx: tuple[Any, ...]) -> None:
    client, _, _, _ = ctx
    resp = await client.post("/provas", json=_body())
    assert resp.status_code == 401


async def test_nao_existe_superficie_de_update(ctx: tuple[Any, ...]) -> None:
    """DP-5(A): rota imutável — nenhum PATCH/PUT existe (405/404 por ausência)."""
    client, _, _, _ = ctx
    body = await _criar_ok(client)
    patch_colecao = await client.patch("/provas", json={"rota": "filial"}, headers=_auth_admin())
    assert patch_colecao.status_code == 405
    patch_item = await client.patch(
        f"/provas/{body['id']}", json={"rota": "filial"}, headers=_auth_admin()
    )
    assert patch_item.status_code in (404, 405)


# ---------------------------------------------------------------------------
# Etiqueta (RF-003/DP-7)
# ---------------------------------------------------------------------------
async def test_etiqueta_pdf_para_download(ctx: tuple[Any, ...]) -> None:
    client, _, _, _ = ctx
    body = await _criar_ok(client)

    resp = await client.get(f"/provas/{body['id']}/etiqueta.pdf", headers=_auth_admin())

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert body["codigo"] in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF")
    assert len(resp.content) > 1000


async def test_etiqueta_acessivel_ao_vendedor_dono(ctx: tuple[Any, ...]) -> None:
    """DP-8: a etiqueta deixou de ser admin-only — o vendedor dono (mapeado ao
    requerimento) enxerga a prova pela RLS e pode imprimi-la."""
    client, _, _, _ = ctx
    body = await _criar_ok(client)
    resp = await client.get(f"/provas/{body['id']}/etiqueta.pdf", headers=_auth_vendedor())
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


# ---------------------------------------------------------------------------
# Preview da arte do requerimento (imagem do share, sem criar) — ajuste Fatia 4
# ---------------------------------------------------------------------------
async def test_preview_arte_do_requerimento(ctx: tuple[Any, ...]) -> None:
    client, _, _, arte_fonte = ctx
    resp = await client.get(f"/provas/requerimento/{COD_REQ}/arte", headers=_auth_admin())
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == JPEG
    # leu do share com os códigos do requerimento (fat, clien, req, anexo)
    assert arte_fonte.chamadas == [(10, 1058, COD_REQ, "VERSAO_150288_V3.jpg")]


async def test_preview_arte_requerimento_inexistente_e_404(ctx: tuple[Any, ...]) -> None:
    client, _, _, _ = ctx
    resp = await client.get("/provas/requerimento/999999/arte", headers=_auth_admin())
    assert resp.status_code == 404


async def test_preview_arte_indisponivel_e_422(ctx: tuple[Any, ...]) -> None:
    client, _, _, arte_fonte = ctx
    arte_fonte.erro = ArteNaoDisponivelError()
    resp = await client.get(f"/provas/requerimento/{COD_REQ}/arte", headers=_auth_admin())
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "arte_indisponivel"


async def test_preview_arte_nao_admin_e_403(ctx: tuple[Any, ...]) -> None:
    client, _, _, _ = ctx
    resp = await client.get(f"/provas/requerimento/{COD_REQ}/arte", headers=_auth_vendedor())
    assert resp.status_code == 403
