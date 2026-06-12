"""Endpoints de provas (W2-C06) contra Postgres REAL (@db) — criação atômica,
validações RF-001/RN-007, gate de admin e etiqueta PDF.

R2 mockado (FakeStorage); JWT HS256 de teste no formato pós-hook (W1-C05). A
``session_factory`` injetada é a de REQUEST (fail-closed — ADR-034): o caminho
HTTP inteiro roda exatamente como em produção, com a RLS valendo.
"""

import datetime as dt
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from src.adapters.inbound.http.auth import JwtVerifier
from src.adapters.outbound.db.models import UsuarioRow
from src.application.ports.storage import StorageError
from src.domain.provas import CODIGO_REGEX
from src.domain.usuarios import Localizacao, Setor
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"
ADMIN_ID = "11111111-1111-1111-1111-111111111111"
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"
JPEG_MINIMO = b"\xff\xd8\xff\xe0" + b"\x00" * 32


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


class StorageQuebrado(FakeStorage):
    def upload(self, key: str, data: bytes, content_type: str) -> str:
        raise StorageError("upload indisponível")


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, FakeStorage, AsyncEngine]]:
    storage = FakeStorage()
    client = make_client(
        settings,
        storage,
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(usuarios_engine),
    )
    await _seed_usuarios(usuarios_engine)
    async with client as c:
        yield c, storage, usuarios_engine


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
                nome="Renan Petrim",
                email="renan@3studio.test",
                setor=Setor.VENDEDOR,
                localizacao=Localizacao.MATRIZ,
            )
        )
        await session.commit()


def _form(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "nome": "Etiq Cafe Caproni Classico",
        "requerimento": "155295",
        "cliente": "Cafe Caproni",
        "vendedor_id": VENDEDOR_ID,
        "rota": "matriz",
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def _arte(conteudo: bytes = JPEG_MINIMO, content_type: str = "image/jpeg") -> dict[str, Any]:
    return {"arte": ("arte.jpg", conteudo, content_type)}


async def _criar_ok(client: httpx.AsyncClient) -> dict[str, Any]:
    resp = await client.post("/provas", data=_form(), files=_arte(), headers=_auth_admin())
    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    return body


# ---------------------------------------------------------------------------
# Criação (US-001)
# ---------------------------------------------------------------------------
async def test_criar_prova_caminho_feliz(ctx: tuple[Any, ...]) -> None:
    client, storage, _ = ctx
    body = await _criar_ok(client)

    assert CODIGO_REGEX.fullmatch(body["codigo"])  # RF-002: identificador canônico
    assert body["status"] == "criada"  # US-001: nasce "Criada"
    assert body["rota"] == "matriz"  # na rota selecionada
    assert body["vendedor_id"] == VENDEDOR_ID
    # arte persistida no storage sob a key derivada do id (RNF-017)
    assert storage.download(f"provas/{body['id']}/arte.jpg") == JPEG_MINIMO


async def test_criar_sem_rota_retorna_422_com_erro_claro(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.post("/provas", data=_form(rota=None), files=_arte(), headers=_auth_admin())
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert any("rota" in detalhe["loc"] for detalhe in body["details"])  # campo apontado


@pytest.mark.parametrize("campo", ["nome", "requerimento", "cliente", "vendedor_id"])
async def test_criar_sem_campo_obrigatorio_retorna_422(ctx: tuple[Any, ...], campo: str) -> None:
    client, _, _ = ctx
    resp = await client.post(
        "/provas", data=_form(**{campo: None}), files=_arte(), headers=_auth_admin()
    )
    assert resp.status_code == 422


async def test_requerimento_nao_numerico_retorna_422(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.post(
        "/provas", data=_form(requerimento="ABC123"), files=_arte(), headers=_auth_admin()
    )
    assert resp.status_code == 422


async def test_arte_de_tipo_invalido_retorna_422(ctx: tuple[Any, ...]) -> None:
    client, storage, _ = ctx
    resp = await client.post(
        "/provas",
        data=_form(),
        files=_arte(b"GIF89a" + b"\x00" * 16, "image/gif"),
        headers=_auth_admin(),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "arte_invalida"
    assert storage._objects == {}


async def test_arte_acima_de_10mb_retorna_422(ctx: tuple[Any, ...]) -> None:
    client, storage, _ = ctx
    gigante = JPEG_MINIMO + b"\x00" * (10 * 1024 * 1024)
    resp = await client.post("/provas", data=_form(), files=_arte(gigante), headers=_auth_admin())
    assert resp.status_code == 422
    assert "10 MB" in resp.json()["error"]["message"]
    assert storage._objects == {}


async def test_vendedor_de_outro_setor_retorna_422(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.post(
        "/provas", data=_form(vendedor_id=ADMIN_ID), files=_arte(), headers=_auth_admin()
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "vendedor_invalido"


async def test_criacao_atomica_storage_fora_nao_deixa_prova_orfa(
    settings: Settings, usuarios_engine: AsyncEngine
) -> None:
    """RNF-017: upload falhou → 503 claro e NENHUMA linha em provas."""
    client = make_client(
        settings,
        StorageQuebrado(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(usuarios_engine),
    )
    await _seed_usuarios(usuarios_engine)
    async with client as c:
        resp = await c.post("/provas", data=_form(), files=_arte(), headers=_auth_admin())
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "storage_indisponivel"
    async with usuarios_engine.connect() as conn:
        total = (await conn.execute(text("SELECT count(*) FROM provas"))).scalar_one()
    assert total == 0


# ---------------------------------------------------------------------------
# Gate de admin (Matriz §7, "Criar Prova") e superfícies inexistentes
# ---------------------------------------------------------------------------
async def test_nao_admin_recebe_403_generico(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.post("/provas", data=_form(), files=_arte(), headers=_auth_vendedor())
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "Acesso negado."


async def test_sem_token_recebe_401(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.post("/provas", data=_form(), files=_arte())
    assert resp.status_code == 401


async def test_nao_existe_superficie_de_update(ctx: tuple[Any, ...]) -> None:
    """DP-5(A): rota imutável — nenhum PATCH/PUT existe (405/404 por ausência);
    a rejeição no BANCO (trigger) é coberta em test_rls_provas.py."""
    client, _, _ = ctx
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
    client, _, _ = ctx
    body = await _criar_ok(client)

    resp = await client.get(f"/provas/{body['id']}/etiqueta.pdf", headers=_auth_admin())

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert body["codigo"] in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF")
    assert len(resp.content) > 1000  # etiqueta real (campos/QR cobertos no unit)


async def test_etiqueta_de_prova_inexistente_e_404_generico(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.get(f"/provas/{uuid.uuid4()}/etiqueta.pdf", headers=_auth_admin())
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "Prova não encontrada."


async def test_etiqueta_negada_a_nao_admin(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    body = await _criar_ok(client)
    resp = await client.get(f"/provas/{body['id']}/etiqueta.pdf", headers=_auth_vendedor())
    assert resp.status_code == 403
