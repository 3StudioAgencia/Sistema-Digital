"""Endpoint ``GET /provas/requerimento/{n}`` (Fatia 1) contra Postgres real (@db).

O ERP é mockado (``FakeRequerimentoReader``): o caminho HTTP inteiro roda como em
produção (gate ``CRIAR_PROVA`` + RLS), sem tocar o Firebird. JWT HS256 de teste no
formato pós-hook (setor/administrador nos claims)."""

import datetime as dt
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from src.adapters.inbound.http.auth import JwtVerifier
from src.adapters.outbound.db.models import UsuarioRow
from src.application.ports.requerimentos import RequerimentoReaderError
from src.domain.requerimentos import RequerimentoArte
from src.domain.usuarios import Localizacao, Setor
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeRequerimentoReader, FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"
ADMIN_ID = "11111111-1111-1111-1111-111111111111"
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"

REQ_150288 = RequerimentoArte(
    cod_req_art=150288,
    nome="QUEIJO MUSSARELA FLORA MILK (25 X 50)",
    cod_cliente=1058,
    nome_cliente="LATICINIOS FLORIDA LTDA",
    cod_vendedor=10,
    nome_vendedor="REGISLAINE PETRIM",
    cod_vend_fat=10,
    anexo_imagem="VERSAO_150288_V3.jpg",
)


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


async def _seed(engine: AsyncEngine) -> None:
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


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, FakeRequerimentoReader]]:
    reader = FakeRequerimentoReader({150288: REQ_150288})
    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(usuarios_engine),
        requerimento_reader=reader,
    )
    await _seed(usuarios_engine)
    async with client as c:
        yield c, reader


async def test_consulta_requerimento_ok(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    resp = await client.get("/provas/requerimento/150288", headers=_auth_admin())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nome"] == "QUEIJO MUSSARELA FLORA MILK (25 X 50)"
    assert body["nome_cliente"] == "LATICINIOS FLORIDA LTDA"
    assert body["nome_vendedor"] == "REGISLAINE PETRIM"
    assert body["cod_vend_fat"] == 10
    assert body["cod_cliente"] == 1058
    assert body["anexo_imagem"] == "VERSAO_150288_V3.jpg"


async def test_requerimento_inexistente_e_404(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    resp = await client.get("/provas/requerimento/999999", headers=_auth_admin())
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "requerimento_nao_encontrado"


async def test_erp_fora_do_ar_e_503(ctx: tuple[Any, ...]) -> None:
    client, reader = ctx
    reader.erro = RequerimentoReaderError("ERP indisponível")
    resp = await client.get("/provas/requerimento/150288", headers=_auth_admin())
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "erp_indisponivel"


async def test_nao_admin_recebe_403_generico(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    resp = await client.get("/provas/requerimento/150288", headers=_auth_vendedor())
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "Acesso negado."


async def test_sem_token_recebe_401(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    resp = await client.get("/provas/requerimento/150288")
    assert resp.status_code == 401


async def test_cod_req_art_nao_positivo_e_422(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    resp = await client.get("/provas/requerimento/0", headers=_auth_admin())
    assert resp.status_code == 422
