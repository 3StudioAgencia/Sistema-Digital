"""Criação de prova ponta a ponta (Fatia 3) — ERP + share + DB + storage REAIS.

Exercita a cadeia INTEIRA (Fatias 1+2+3) contra os sistemas externos de verdade:
resolve o requerimento 150288 no Firebird, lê a imagem no servidor de arquivos, faz
o snapshot no storage de disco e INSERE no Postgres — tudo pelo caminho HTTP real.

Skip se faltar Postgres (@db), o Firebird (@firebird) ou o share (@share). Só
LEITURA nos sistemas legados. Config por env (não versiona caminhos/segredos):
    FIREBIRD_TEST_DATABASE / _USER / _PASSWORD / _CHARSET / _CLIENT_LIBRARY
    ARTE_SHARE_TEST_BASE
"""

import datetime as dt
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from src.adapters.inbound.http.auth import JwtVerifier
from src.adapters.outbound.arte_fonte.filesystem_arte_fonte import SistemaDeArquivosArteFonte
from src.adapters.outbound.db.models import UsuarioRow
from src.adapters.outbound.firebird.requerimento_reader import FirebirdRequerimentoReader
from src.adapters.outbound.storage.filesystem_storage import FilesystemStorage
from src.domain.usuarios import Localizacao, Setor
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import make_client, ping_ok

pytestmark = [pytest.mark.db, pytest.mark.firebird, pytest.mark.share]

HS256_SECRET = "segredo-integracao-nunca-em-producao"
ADMIN_ID = "11111111-1111-1111-1111-111111111111"
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"
# Requerimento de exemplo do ERP real: COD_VENDE=10, cliente LATICINIOS FLORIDA.
COD_REQ = 150288
COD_VENDE = 10


def _auth_admin() -> dict[str, str]:
    now = dt.datetime.now(tz=dt.UTC)
    claims: dict[str, Any] = {
        "sub": ADMIN_ID,
        "user_id": ADMIN_ID,
        "email": "admin@x.z",
        "role": "authenticated",
        "aud": "authenticated",
        "setor": "studio",
        "administrador": True,
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }
    return {"Authorization": f"Bearer {jwt.encode(claims, HS256_SECRET, algorithm='HS256')}"}


async def _seed(engine: AsyncEngine) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UsuarioRow(
                id=ADMIN_ID,
                nome="Admin",
                email="admin@3studio.test",
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
                cod_vendedor_firebird=COD_VENDE,
            )
        )
        await session.commit()


@pytest.fixture
async def client_e2e(
    settings: Settings, usuarios_engine: AsyncEngine, tmp_path: Path
) -> AsyncIterator[httpx.AsyncClient]:
    fb_db = os.environ.get("FIREBIRD_TEST_DATABASE")
    share = os.environ.get("ARTE_SHARE_TEST_BASE")
    if not fb_db:
        pytest.skip("FIREBIRD_TEST_DATABASE não definido — e2e do ERP pulado")
    if not share:
        pytest.skip("ARTE_SHARE_TEST_BASE não definido — e2e do servidor de arquivos pulado")

    firebird = FirebirdRequerimentoReader(
        database=fb_db,
        user=os.environ.get("FIREBIRD_TEST_USER", "SYSDBA"),
        password=os.environ.get("FIREBIRD_TEST_PASSWORD", "masterkey"),
        charset=os.environ.get("FIREBIRD_TEST_CHARSET", "WIN1252"),
        client_library=os.environ.get("FIREBIRD_TEST_CLIENT_LIBRARY"),
    )
    arte_fonte = SistemaDeArquivosArteFonte(share, 50 * 1024 * 1024)
    storage = FilesystemStorage(str(tmp_path / "artes"))
    client = make_client(
        settings,
        storage,
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(usuarios_engine),
        requerimento_reader=firebird,
        arte_fonte=arte_fonte,
    )
    await _seed(usuarios_engine)
    async with client as c:
        yield c


async def test_cria_prova_do_requerimento_real(client_e2e: httpx.AsyncClient) -> None:
    resp = await client_e2e.post(
        "/provas", json={"cod_req_art": COD_REQ, "rota": "matriz"}, headers=_auth_admin()
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["requerimento"] == str(COD_REQ)
    assert "QUEIJO" in body["nome"]  # PRODART do ERP real
    assert body["cliente"] == "LATICINIOS FLORIDA LTDA"
    assert body["vendedor_id"] == VENDEDOR_ID  # COD_VENDE=10 -> usuário do app

    # a imagem oficial (VERSAO\) foi copiada para o storage e é servida pelo proxy
    arte = await client_e2e.get(f"/provas/{body['id']}/arte", headers=_auth_admin())
    assert arte.status_code == 200
    assert arte.headers["content-type"] == "image/jpeg"
    assert arte.content.startswith(b"\xff\xd8\xff")  # JPEG real do servidor de arquivos
    assert len(arte.content) > 100_000  # arte de verdade (não um stub)
