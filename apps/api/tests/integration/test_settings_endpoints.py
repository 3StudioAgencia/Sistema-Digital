"""Endpoints de configurações (W2-C09) contra Postgres REAL (@db).

Cobre os critérios §6: acesso 3Studio-only (guard), tempo de atraso salvo e
imediato (US-016), validação por chave, idempotência (PUT) e a INTEGRAÇÃO com a
etiqueta (C06) — a geração reflete a config salva (padrão vs. personalizado).

JWT HS256 de teste no formato pós-hook (W1-C05); a ``session_factory`` injetada é
a de REQUEST (fail-closed — ADR-034): o caminho HTTP roda como em produção, RLS
valendo.
"""

import datetime as dt
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from src.adapters.inbound.http.auth import JwtVerifier
from src.adapters.outbound.db.models import UsuarioRow
from src.application.ports.arte_fonte import ArteSelecionada
from src.domain.requerimentos import RequerimentoArte
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
JPEG_MINIMO = b"\xff\xd8\xff\xe0" + b"\x00" * 32
COD_REQ = 155295
COD_VENDE = 10
MM_PARA_PT = 72 / 25.4

_REQ = RequerimentoArte(
    cod_req_art=COD_REQ,
    nome="Etiq Cafe Caproni",
    cod_cliente=1058,
    nome_cliente="Cafe Caproni",
    cod_vendedor=COD_VENDE,
    nome_vendedor="Renan Petrim",
    cod_vend_fat=10,
    anexo_imagem="VERSAO_155295_V1.jpg",
)
_ARTE = ArteSelecionada(conteudo=JPEG_MINIMO, content_type="image/jpeg", nome_arquivo="V1.jpg")


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


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine]]:
    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(usuarios_engine),
        requerimento_reader=FakeRequerimentoReader({COD_REQ: _REQ}),
        arte_fonte=FakeArteFonte(_ARTE),
    )
    await _seed_usuarios(usuarios_engine)
    async with client as c:
        yield c, usuarios_engine


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
                cod_vendedor_firebird=COD_VENDE,
            )
        )
        await session.commit()


async def _criar_prova(client: httpx.AsyncClient) -> dict[str, Any]:
    resp = await client.post(
        "/provas", json={"cod_req_art": COD_REQ, "rota": "matriz"}, headers=_auth_admin()
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _media_box(pdf: bytes) -> tuple[float, float]:
    m = re.search(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", pdf)
    assert m is not None
    return float(m.group(1)), float(m.group(2))


# ---------------------------------------------------------------------------
# Leitura / defaults (RF-022)
# ---------------------------------------------------------------------------
async def test_admin_le_defaults(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    resp = await client.get("/settings", headers=_auth_admin())
    assert resp.status_code == 200
    configs = {c["chave"]: c for c in resp.json()}
    assert configs["delay_horas_uteis"]["valor"] == 48
    assert configs["delay_horas_uteis"]["default"] == 48
    assert configs["delay_horas_uteis"]["atualizado_em"] is None  # sem sobrescrita
    assert configs["etiqueta_template"]["valor"]["modo"] == "padrao"


# ---------------------------------------------------------------------------
# Tempo de atraso: salvo, imediato (US-016) e validado
# ---------------------------------------------------------------------------
async def test_salvar_delay_e_imediato(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    put = await client.put("/settings/delay_horas_uteis", json={"valor": 72}, headers=_auth_admin())
    assert put.status_code == 200
    assert put.json()["valor"] == 72
    assert put.json()["atualizado_por"] == ADMIN_ID  # auditoria leve
    # imediatismo (US-016): a leitura subsequente já reflete (sem cache — DP-4)
    get = await client.get("/settings", headers=_auth_admin())
    configs = {c["chave"]: c for c in get.json()}
    assert configs["delay_horas_uteis"]["valor"] == 72


@pytest.mark.parametrize("valor", [0, -5, "x", 48.5, True])
async def test_salvar_delay_invalido_retorna_422(ctx: tuple[Any, ...], valor: object) -> None:
    client, _ = ctx
    resp = await client.put(
        "/settings/delay_horas_uteis", json={"valor": valor}, headers=_auth_admin()
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "configuracao_invalida"


async def test_salvar_chave_desconhecida_retorna_422(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    resp = await client.put("/settings/nao_existe", json={"valor": 1}, headers=_auth_admin())
    assert resp.status_code == 422


async def test_salvar_e_idempotente(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    a = await client.put("/settings/delay_horas_uteis", json={"valor": 60}, headers=_auth_admin())
    b = await client.put("/settings/delay_horas_uteis", json={"valor": 60}, headers=_auth_admin())
    assert a.status_code == b.status_code == 200
    assert a.json()["valor"] == b.json()["valor"] == 60


# ---------------------------------------------------------------------------
# Acesso negado a não-3Studio (guard — camada superior; a RLS é o test_rls_*)
# ---------------------------------------------------------------------------
async def test_vendedor_nao_le_configuracoes(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    resp = await client.get("/settings", headers=_auth_vendedor())
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "Acesso negado."


async def test_vendedor_nao_salva_configuracoes(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    resp = await client.put(
        "/settings/delay_horas_uteis", json={"valor": 1}, headers=_auth_vendedor()
    )
    assert resp.status_code == 403


async def test_sem_token_recebe_401(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    assert (await client.get("/settings")).status_code == 401


# ---------------------------------------------------------------------------
# Integração com a etiqueta (C06): a geração respeita a config salva (RN-011)
# ---------------------------------------------------------------------------
async def test_etiqueta_respeita_template_personalizado(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    body = await _criar_prova(client)

    # Antes de configurar: etiqueta no tamanho padrão (95 x 55 mm).
    padrao = await client.get(f"/provas/{body['id']}/etiqueta.pdf", headers=_auth_admin())
    assert padrao.status_code == 200
    largura, altura = _media_box(padrao.content)
    assert largura == pytest.approx(95 * MM_PARA_PT, abs=0.1)
    assert altura == pytest.approx(55 * MM_PARA_PT, abs=0.1)

    # Salva template personalizado e a etiqueta passa a sair em 100 x 60 mm.
    cfg = await client.put(
        "/settings/etiqueta_template",
        json={"valor": {"modo": "personalizado", "largura": 100, "altura": 60}},
        headers=_auth_admin(),
    )
    assert cfg.status_code == 200
    custom = await client.get(f"/provas/{body['id']}/etiqueta.pdf", headers=_auth_admin())
    largura, altura = _media_box(custom.content)
    assert largura == pytest.approx(100 * MM_PARA_PT, abs=0.1)
    assert altura == pytest.approx(60 * MM_PARA_PT, abs=0.1)


async def test_etiqueta_volta_ao_padrao_com_modo_padrao(ctx: tuple[Any, ...]) -> None:
    client, _ = ctx
    body = await _criar_prova(client)
    # modo 'padrao' ignora sobrescritas → volta ao tamanho físico padrão.
    await client.put(
        "/settings/etiqueta_template",
        json={"valor": {"modo": "padrao", "largura": 100, "altura": 60}},
        headers=_auth_admin(),
    )
    resp = await client.get(f"/provas/{body['id']}/etiqueta.pdf", headers=_auth_admin())
    largura, altura = _media_box(resp.content)
    assert largura == pytest.approx(95 * MM_PARA_PT, abs=0.1)
    assert altura == pytest.approx(55 * MM_PARA_PT, abs=0.1)
