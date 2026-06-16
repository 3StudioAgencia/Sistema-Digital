"""Identificação de prova (W3-C10) contra Postgres REAL (@db).

Exercita ``POST /provas/identificar`` pelo caminho HTTP inteiro como em produção
(``SET LOCAL ROLE authenticated`` + claims propagados — ADR-008/ADR-034),
validando os critérios de aceitação §6:

- QR e código manual resolvem o MESMO registro pelo mesmo caminho (idempotente);
- ANTI-ENUMERAÇÃO (RN-014): código malformado, inexistente E fora do escopo
  retornam o MESMO 404 genérico (mensagem idêntica);
- a resolução respeita a RLS (Motorista só "Em Trânsito", Vendedor só as suas);
- RATE LIMITING: 30/ator/minuto → 429, e o contador é POR usuário.
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
from src.application.provas import LIMITE_IDENTIFICACAO
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"

# Códigos canônicos conhecidos (formato C06: PRV-AAAA-MM-NNNNNN, charset sem
# 0/O/1/I/L). Conhecê-los permite enviá-los como "QR/manual" e checar a resolução.
CODIGO_REG = "PRV-2026-06-A2KMQ9"  # prova "criada" da Regiane
CODIGO_PACK = "PRV-2026-06-B3T7XC"  # prova "criada" do Packon
CODIGO_TRANSITO = "PRV-2026-06-C4U8YD"  # prova "Em Trânsito" da Regiane


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


def _auth(sub: str, setor: str, admin: bool = False) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(sub, setor, admin)}"}


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


async def _seed_prova(
    engine: AsyncEngine,
    *,
    vendedor_id: str,
    codigo: str,
    status: str = "criada",
    rota: str = "matriz",
) -> str:
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type) VALUES (:id, :codigo, 'Mussarela', '155295', "
                "'Edulat', :vendedor, :rota, :status, 'provas/x/arte.png', 'image/png')"
            ),
            {"id": uid, "codigo": codigo, "vendedor": vendedor_id, "rota": rota, "status": status},
        )
    return uid


async def _seed_contador(
    engine: AsyncEngine, user_id: str, *, contador: int, chave: str = "identificar"
) -> None:
    """Semeia o contador do ator no minuto CORRENTE (atalho para o caso 429 sem
    disparar dezenas de requisições)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO rate_limit_contadores (user_id, chave, janela_inicio, contador) "
                "VALUES (:uid, :chave, date_trunc('minute', now()), :c)"
            ),
            {"uid": user_id, "chave": chave, "c": contador},
        )


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, dict[str, Any]]]:
    engine = usuarios_engine
    regiane = await _seed_usuario(engine, setor="vendedor", nome="Regiane")
    packon = await _seed_usuario(engine, setor="vendedor", nome="Packon")
    motorista = await _seed_usuario(engine, setor="motorista", nome="Moto Op")

    await _seed_prova(engine, vendedor_id=regiane, codigo=CODIGO_REG)
    await _seed_prova(engine, vendedor_id=packon, codigo=CODIGO_PACK)
    await _seed_prova(
        engine,
        vendedor_id=regiane,
        codigo=CODIGO_TRANSITO,
        status="com_motorista_ida_laminacao",
        rota="lam_matriz",
    )

    ids = {"regiane": regiane, "packon": packon, "motorista": motorista}
    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    async with client as c:
        yield c, engine, ids


async def _identificar(
    client: httpx.AsyncClient, codigo: str, headers: dict[str, str]
) -> httpx.Response:
    return await client.post("/provas/identificar", json={"codigo": codigo}, headers=headers)


# ---------------------------------------------------------------------------
# Resolução QR/manual (mesmo caminho, mesmo registro)
# ---------------------------------------------------------------------------
async def test_identifica_pelo_codigo_e_devolve_o_detalhe(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    resp = await _identificar(client, CODIGO_REG, _auth(ids["regiane"], "vendedor"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["codigo"] == CODIGO_REG
    assert body["nome"] == "Mussarela"
    assert body["requerimento"] == "155295"
    assert body["vendedor_nome"] == "Regiane"  # nome resolvido (DP-7) para a confirmação
    assert body["status"] == "criada"


@pytest.mark.parametrize(
    "entrada",
    [CODIGO_REG, f"  {CODIGO_REG}\n", CODIGO_REG.lower()],
)
async def test_qr_e_manual_resolvem_o_mesmo_registro(ctx: tuple[Any, ...], entrada: str) -> None:
    """QR (carrega o próprio código — C06), digitação com espaço/quebra e
    minúsculas convergem para a MESMA prova (normalização server-side)."""
    client, _, ids = ctx
    resp = await _identificar(client, entrada, _auth(ids["regiane"], "vendedor"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["codigo"] == CODIGO_REG


# ---------------------------------------------------------------------------
# Anti-enumeração (RN-014): inválido == inexistente == fora-de-escopo → 404
# ---------------------------------------------------------------------------
async def test_invalido_inexistente_e_fora_escopo_mesmo_404(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    reg = _auth(ids["regiane"], "vendedor")
    malformado = await _identificar(client, "3S-1234-5678", reg)  # máscara legada do design
    inexistente = await _identificar(client, "PRV-2026-06-ZZ9999", reg)  # formato ok, não existe
    fora = await _identificar(client, CODIGO_PACK, reg)  # existe, mas é do Packon

    for r in (malformado, inexistente, fora):
        assert r.status_code == 404, r.text
        assert r.json()["error"]["code"] == "prova_nao_encontrada"
    # mensagem IDÊNTICA nos três — nada distingue os casos (sem canal lateral)
    mensagens = {r.json()["error"]["message"] for r in (malformado, inexistente, fora)}
    assert mensagens == {"Prova não encontrada."}


async def test_motorista_identifica_em_transito_mas_nao_a_criada(ctx: tuple[Any, ...]) -> None:
    """A resolução respeita a RLS: o Motorista só enxerga "Em Trânsito"."""
    client, _, ids = ctx
    moto = _auth(ids["motorista"], "motorista")
    ok = await _identificar(client, CODIGO_TRANSITO, moto)
    assert ok.status_code == 200
    nao = await _identificar(client, CODIGO_REG, moto)  # "criada" não é "Em Trânsito"
    assert nao.status_code == 404
    assert nao.json()["error"]["message"] == "Prova não encontrada."


async def test_sem_token_e_401(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.post("/provas/identificar", json={"codigo": CODIGO_REG})
    assert resp.status_code == 401


async def test_usuario_nao_provisionado_e_403(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await _identificar(client, CODIGO_REG, _auth(str(uuid.uuid4()), "vendedor"))
    assert resp.status_code == 403


async def test_codigo_vazio_e_404_generico(ctx: tuple[Any, ...]) -> None:
    """Anti-enumeração: código vazio é só mais um valor que não resolve — MESMO 404
    genérico (não um 422 distinguível por comprimento), e é contado no rate limit.
    Só a AUSÊNCIA do campo ``codigo`` (corpo estrutural inválido) seria 422."""
    client, _, ids = ctx
    resp = await client.post(
        "/provas/identificar", json={"codigo": ""}, headers=_auth(ids["regiane"], "vendedor")
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "Prova não encontrada."


# ---------------------------------------------------------------------------
# Rate limiting (RN-014: 30/ator/minuto) — 429 e isolamento por usuário
# ---------------------------------------------------------------------------
async def test_acima_do_limite_responde_429(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    # Já com 30 no minuto corrente → a próxima (31ª) excede e é bloqueada.
    await _seed_contador(engine, ids["regiane"], contador=LIMITE_IDENTIFICACAO)
    resp = await _identificar(client, CODIGO_REG, _auth(ids["regiane"], "vendedor"))
    assert resp.status_code == 429, resp.text
    assert resp.json()["error"]["code"] == "limite_de_tentativas"


async def test_rate_limit_e_por_usuario(ctx: tuple[Any, ...]) -> None:
    """O contador saturado de um ator NÃO afeta outro (linha própria, RLS)."""
    client, engine, ids = ctx
    await _seed_contador(engine, ids["regiane"], contador=LIMITE_IDENTIFICACAO)
    # Packon, com contador zerado, identifica a própria prova normalmente.
    resp = await _identificar(client, CODIGO_PACK, _auth(ids["packon"], "vendedor"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["codigo"] == CODIGO_PACK
