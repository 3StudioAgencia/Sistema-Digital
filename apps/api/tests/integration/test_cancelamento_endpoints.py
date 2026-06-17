"""Cancelamento de prova (W3-C14) contra Postgres REAL (@db).

Exercita ``POST /provas/{id}/cancelar`` pelo caminho HTTP inteiro como em produção
(``SET LOCAL ROLE authenticated`` + claims propagados — ADR-008), validando os
critérios §6 do C14:

- admin cancela prova ATIVA (qualquer estado ≠ terminal) com motivo → ``Cancelada``,
  carimbo terminal, UMA movimentação (ator + data/hora + motivo) no log imutável
  (RNF-006), SEM assinatura desenhada (``assinatura_ref`` NULL — DP-2/ADR-066);
- motivo obrigatório (front E back): ausente → 422; em branco → 422
  (``motivo_obrigatorio``);
- estados inválidos: prova já ``Cancelada`` ou ``Recebida pela Clicheria``
  (terminais) → transição indefinida → 422;
- acesso em DUAS camadas: perfil não-admin → 403 na BORDA (gate ``CANCELAR_PROVA``),
  mesmo chamando o endpoint diretamente; sem token → 401;
- IRREVERSIBILIDADE (RN-005): após cancelar, não há transição de saída (recancelar
  com nova chave → 422);
- idempotência: reenvio com a mesma chave → 200, UMA movimentação;
- escopo (RLS): inexistente / fora do escopo do ator → 404 genérico
  (anti-enumeração); a flag ``administrador`` é ortogonal ao setor (Vendedor-admin
  cancela a PRÓPRIA prova — ADR-064).
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
from src.domain.provas import gerar_codigo
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"


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


async def _seed_usuario(engine: AsyncEngine, *, setor: str, administrador: bool = False) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id, 'U', :email, :setor, :loc, :adm)"
            ),
            {"id": uid, "email": f"{uid}@x.z", "setor": setor, "loc": loc, "adm": administrador},
        )
    return uid


async def _seed_prova(
    engine: AsyncEngine, *, vendedor_id: str, status: str = "criada", rota: str = "matriz"
) -> str:
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


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, dict[str, Any]]]:
    engine = usuarios_engine
    ids = {
        "admin": await _seed_usuario(engine, setor="studio", administrador=True),
        "studio": await _seed_usuario(engine, setor="studio"),
        "vendedor1": await _seed_usuario(engine, setor="vendedor"),
        "vendedor2": await _seed_usuario(engine, setor="vendedor"),
        "clicheria": await _seed_usuario(engine, setor="clicheria"),
    }
    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    async with client as c:
        yield c, engine, ids


async def _cancelar(
    client: httpx.AsyncClient,
    prova_id: str,
    headers: dict[str, str],
    *,
    motivo: str | None = "cliente desistiu",
    idem: str | None = None,
) -> httpx.Response:
    body: dict[str, Any] = {"idempotency_key": idem or str(uuid.uuid4())}
    if motivo is not None:
        body["motivo"] = motivo
    return await client.post(f"/provas/{prova_id}/cancelar", json=body, headers=headers)


async def _movimentacoes(engine: AsyncEngine, prova_id: str) -> list[Any]:
    async with engine.connect() as conn:
        return list(
            (
                await conn.execute(
                    text(
                        "SELECT acao, ator_id, motivo, assinatura_ref, estado_destino, created_at"
                        " FROM movimentacoes WHERE prova_id = :p ORDER BY created_at"
                    ),
                    {"p": prova_id},
                )
            ).all()
        )


async def _contar_assinaturas(engine: AsyncEngine, prova_id: str) -> int:
    async with engine.connect() as conn:
        return int(
            (
                await conn.execute(
                    text("SELECT count(*) FROM assinaturas WHERE prova_id = :p"),
                    {"p": prova_id},
                )
            ).scalar_one()
        )


# ---------------------------------------------------------------------------
# Caminho feliz — admin cancela; movimentação registrada SEM assinatura
# ---------------------------------------------------------------------------
async def test_admin_cancela_prova_ativa_via_motor(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _cancelar(client, prova, _auth(ids["admin"], "studio", admin=True), motivo="erro")
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["status"] == "cancelada"
    assert corpo["finalizada_em"] is not None  # terminal carimbado (RN-005)

    movs = await _movimentacoes(engine, prova)
    assert len(movs) == 1  # exatamente UMA movimentação (RNF-006)
    (mov,) = movs
    assert mov.acao == "cancelar"
    assert str(mov.ator_id) == ids["admin"]  # usuário responsável gravado
    assert mov.motivo == "erro"
    assert mov.estado_destino == "cancelada"
    assert mov.assinatura_ref is None  # SEM assinatura desenhada (DP-2/ADR-066)
    assert mov.created_at is not None  # data/hora gravada
    assert await _contar_assinaturas(engine, prova) == 0


async def test_cancela_de_estado_intermediario_ativo(ctx: tuple[Any, ...]) -> None:
    """Cancelar vale em QUALQUER estado ATIVO (RF-011/§6.6), não só em 'criada'."""
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine,
        vendedor_id=ids["vendedor1"],
        status="com_motorista_ida_laminacao",
        rota="lam_matriz",
    )
    resp = await _cancelar(client, prova, _auth(ids["admin"], "studio", admin=True))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelada"


# ---------------------------------------------------------------------------
# Motivo obrigatório (front E back)
# ---------------------------------------------------------------------------
async def test_cancelar_sem_motivo_e_422(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    # Sem o campo motivo → 422 (schema: motivo é obrigatório, min_length=1).
    resp = await _cancelar(client, prova, _auth(ids["admin"], "studio", admin=True), motivo=None)
    assert resp.status_code == 422, resp.text
    assert await _movimentacoes(engine, prova) == []  # nada gravado


async def test_cancelar_motivo_em_branco_e_422(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    # Motivo só com espaços passa o schema, mas o domínio o rejeita (motivo.strip()).
    resp = await _cancelar(client, prova, _auth(ids["admin"], "studio", admin=True), motivo="   ")
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "motivo_obrigatorio"
    assert await _movimentacoes(engine, prova) == []


# ---------------------------------------------------------------------------
# Estados inválidos — terminais não podem ser cancelados (422)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("terminal", ["cancelada", "recebida_clicheria"])
async def test_cancelar_estado_terminal_e_422(ctx: tuple[Any, ...], terminal: str) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status=terminal, rota="matriz")
    resp = await _cancelar(client, prova, _auth(ids["admin"], "studio", admin=True))
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "transicao_invalida"


# ---------------------------------------------------------------------------
# Irreversibilidade (RN-005) — Cancelada é terminal, sem transição de saída
# ---------------------------------------------------------------------------
async def test_cancelada_nao_reativa_recancelar_com_nova_chave_e_422(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    h = _auth(ids["admin"], "studio", admin=True)
    primeiro = await _cancelar(client, prova, h)
    assert primeiro.status_code == 200, primeiro.text
    # Recancelar (chave NOVA) → estado terminal não tem transição → 422 (não reativa).
    de_novo = await _cancelar(client, prova, h, idem=str(uuid.uuid4()))
    assert de_novo.status_code == 422, de_novo.text
    assert de_novo.json()["error"]["code"] == "transicao_invalida"
    assert len(await _movimentacoes(engine, prova)) == 1  # histórico preservado, sem nova mov


# ---------------------------------------------------------------------------
# Acesso em DUAS camadas — não-admin barrado na BORDA (gate CANCELAR_PROVA)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("sub_key", "setor"),
    [("studio", "studio"), ("vendedor1", "vendedor"), ("clicheria", "clicheria")],
)
async def test_nao_admin_e_403_na_borda(ctx: tuple[Any, ...], sub_key: str, setor: str) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _cancelar(client, prova, _auth(ids[sub_key], setor))
    assert resp.status_code == 403, resp.text
    assert await _movimentacoes(engine, prova) == []  # nada gravado/transicionado


async def test_sem_token_e_401(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await client.post(
        f"/provas/{prova}/cancelar",
        json={"motivo": "x", "idempotency_key": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


async def test_usuario_nao_provisionado_e_403(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    # Token de admin, mas sem linha em ``usuarios`` → gate nega (defesa em profundidade).
    resp = await _cancelar(client, prova, _auth(str(uuid.uuid4()), "studio", admin=True))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Flag administrador é ortogonal ao setor (ADR-064)
# ---------------------------------------------------------------------------
async def test_vendedor_admin_cancela_a_propria_prova(ctx: tuple[Any, ...]) -> None:
    client, engine, _ids = ctx
    vadmin = await _seed_usuario(engine, setor="vendedor", administrador=True)
    prova = await _seed_prova(engine, vendedor_id=vadmin, status="criada", rota="matriz")
    resp = await _cancelar(client, prova, _auth(vadmin, "vendedor", admin=True))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelada"


async def test_admin_enxerga_e_cancela_prova_de_qualquer_vendedor(ctx: tuple[Any, ...]) -> None:
    """A RLS de ``provas`` dá ao ADMIN (flag — ``app_is_admin()``, qualquer setor)
    visibilidade TOTAL (ADR-039): um Vendedor-admin enxerga e cancela a prova de
    OUTRO vendedor. Não há, portanto, caso "admin em-escopo → 404" para o cancelar
    (admins veem tudo); o 404 cobre só a prova inexistente (teste à parte)."""
    client, engine, ids = ctx
    vadmin = await _seed_usuario(engine, setor="vendedor", administrador=True)
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _cancelar(client, prova, _auth(vadmin, "vendedor", admin=True))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelada"


async def test_inexistente_e_404(ctx: tuple[Any, ...]) -> None:
    client, _engine, ids = ctx
    resp = await _cancelar(client, str(uuid.uuid4()), _auth(ids["admin"], "studio", admin=True))
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["message"] == "Prova não encontrada."


# ---------------------------------------------------------------------------
# Idempotência (RNF-015) — reenvio converge, sem duplicar
# ---------------------------------------------------------------------------
async def test_reenvio_com_mesma_chave_converge_uma_movimentacao(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    chave = str(uuid.uuid4())
    h = _auth(ids["admin"], "studio", admin=True)
    r1 = await _cancelar(client, prova, h, idem=chave)
    r2 = await _cancelar(client, prova, h, idem=chave)
    assert r1.status_code == r2.status_code == 200, (r1.text, r2.text)
    assert r1.json()["status"] == r2.json()["status"] == "cancelada"
    assert len(await _movimentacoes(engine, prova)) == 1  # NÃO duplicou
