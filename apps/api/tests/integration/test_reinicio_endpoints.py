"""Reinício de ciclo (W3-C15) contra Postgres REAL (@db).

Exercita ``POST /provas/{id}/reiniciar`` pelo caminho HTTP inteiro como em produção
(``SET LOCAL ROLE authenticated`` + claims propagados — ADR-008), validando os
critérios §6 do C15:

- admin reinicia prova em ``Reprovada pelo Vendedor`` → ``Criada``, **rota
  preservada** (imutável), ``ciclo_atual`` INCREMENTADO (1→2), UMA movimentação
  (ator + data/hora, SEM motivo nem assinatura — ADR-066) carimbada com o ciclo
  que se ENCERRA (1) no log imutável (RNF-006), e o **histórico anterior
  preservado** (movimentações do ciclo 1 intactas);
- a transição (status) e o incremento (ciclo) caem na MESMA transação atômica
  (RNF-017) — o incremento de ``ciclo_atual`` exige o GRANT de coluna da migration
  0018 (sem ela, "permission denied for column" no role NOBYPASSRLS);
- estados inválidos: SÓ ``reprovada_vendedor`` (RN-006); qualquer outro estado →
  transição indefinida → 422 (sem incremento, sem movimentação);
- acesso em DUAS camadas: perfil não-admin → 403 na BORDA (gate ``REINICIAR_CICLO``),
  mesmo chamando o endpoint diretamente; sem token → 401;
- idempotência (RNF-015): reenvio com a mesma chave → 200, UMA movimentação e UM
  incremento (``ciclo_atual`` = 2, NUNCA 3);
- escopo (RLS): inexistente / fora do escopo → 404 genérico (anti-enumeração); a
  flag ``administrador`` é ortogonal ao setor (Vendedor-admin reinicia — ADR-064).
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
    engine: AsyncEngine,
    *,
    vendedor_id: str,
    status: str = "reprovada_vendedor",
    rota: str = "matriz",
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


async def _seed_movimentacao(
    engine: AsyncEngine, *, prova_id: str, ator_id: str, ciclo: int
) -> None:
    """Insere uma movimentação do ciclo anterior (como owner — semeadura), para
    provar que o reinício PRESERVA o histórico do ciclo passado."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO movimentacoes (id, prova_id, estado_origem, estado_destino, acao, "
                "ator_id, ciclo, idempotency_key) VALUES (:id, :p, 'criada', 'retirada_vendedor', "
                "'identificar_e_assinar', :ator, :ciclo, :idem)"
            ),
            {
                "id": str(uuid.uuid4()),
                "p": prova_id,
                "ator": ator_id,
                "ciclo": ciclo,
                "idem": str(uuid.uuid4()),
            },
        )


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, dict[str, Any]]]:
    engine = usuarios_engine
    ids = {
        "admin": await _seed_usuario(engine, setor="studio", administrador=True),
        "studio": await _seed_usuario(engine, setor="studio"),
        "vendedor1": await _seed_usuario(engine, setor="vendedor"),
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


async def _reiniciar(
    client: httpx.AsyncClient,
    prova_id: str,
    headers: dict[str, str],
    *,
    idem: str | None = None,
) -> httpx.Response:
    body = {"idempotency_key": idem or str(uuid.uuid4())}
    return await client.post(f"/provas/{prova_id}/reiniciar", json=body, headers=headers)


async def _movimentacoes(engine: AsyncEngine, prova_id: str) -> list[Any]:
    async with engine.connect() as conn:
        return list(
            (
                await conn.execute(
                    text(
                        "SELECT acao, ator_id, motivo, assinatura_ref, estado_origem, "
                        "estado_destino, ciclo, created_at FROM movimentacoes "
                        "WHERE prova_id = :p ORDER BY created_at"
                    ),
                    {"p": prova_id},
                )
            ).all()
        )


async def _prova_row(engine: AsyncEngine, prova_id: str) -> Any:
    async with engine.connect() as conn:
        return (
            await conn.execute(
                text("SELECT status, rota, ciclo_atual, finalizada_em FROM provas WHERE id = :p"),
                {"p": prova_id},
            )
        ).one()


# ---------------------------------------------------------------------------
# Caminho feliz — admin reinicia; status→Criada, ciclo++ , rota e histórico preservados
# ---------------------------------------------------------------------------
async def test_admin_reinicia_prova_reprovada_via_motor(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="reprovada_vendedor", rota="matriz"
    )
    # Histórico do ciclo 1 (semeado): uma movimentação anterior, ciclo 1.
    await _seed_movimentacao(engine, prova_id=prova, ator_id=ids["vendedor1"], ciclo=1)

    resp = await _reiniciar(client, prova, _auth(ids["admin"], "studio", admin=True))
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["status"] == "criada"  # volta ao início (mesma prova)
    assert corpo["ciclo_atual"] == 2  # ciclo incrementado (efeito do reinício)
    assert corpo["rota"] == "matriz"  # rota PRESERVADA (imutável — RN-007)
    assert corpo["finalizada_em"] is None  # CRIADA não é terminal

    linha = await _prova_row(engine, prova)
    assert linha.status == "criada"
    assert linha.ciclo_atual == 2  # incremento PERSISTIDO (GRANT da 0018)
    assert linha.rota == "matriz"

    movs = await _movimentacoes(engine, prova)
    # Histórico preservado: a movimentação anterior (ciclo 1) + a de reinício (ciclo 1).
    assert len(movs) == 2
    anterior, reinicio = movs
    assert anterior.ciclo == 1 and anterior.acao == "identificar_e_assinar"
    assert reinicio.acao == "reiniciar_ciclo"
    assert str(reinicio.ator_id) == ids["admin"]  # responsável gravado
    assert reinicio.estado_origem == "reprovada_vendedor"
    assert reinicio.estado_destino == "criada"
    assert reinicio.ciclo == 1  # carimbada com o ciclo que se ENCERRA (DP-3)
    assert reinicio.motivo is None  # reinício NÃO leva motivo (≠ cancelar)
    assert reinicio.assinatura_ref is None  # SEM assinatura desenhada (DP-2/ADR-066)
    assert reinicio.created_at is not None  # data/hora gravada


async def test_reinicio_preserva_rota_de_laminacao(ctx: tuple[Any, ...]) -> None:
    """A rota original é mantida em QUALQUER rota (imutável) — aqui lam_matriz."""
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="reprovada_vendedor", rota="lam_matriz"
    )
    resp = await _reiniciar(client, prova, _auth(ids["admin"], "studio", admin=True))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "criada"
    assert resp.json()["rota"] == "lam_matriz"  # rota de laminação preservada


# ---------------------------------------------------------------------------
# Estados inválidos — só REPROVADA_VENDEDOR (RN-006); outros → 422 sem efeito
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "status",
    ["criada", "retirada_vendedor", "aprovada_vendedor", "recebida_clicheria", "cancelada"],
)
async def test_reiniciar_estado_invalido_e_422_sem_incremento(
    ctx: tuple[Any, ...], status: str
) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status=status, rota="matriz")
    resp = await _reiniciar(client, prova, _auth(ids["admin"], "studio", admin=True))
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "transicao_invalida"
    linha = await _prova_row(engine, prova)
    assert linha.status == status  # inalterado
    assert linha.ciclo_atual == 1  # NÃO incrementou
    assert await _movimentacoes(engine, prova) == []  # nada gravado


# ---------------------------------------------------------------------------
# Acesso em DUAS camadas — não-admin barrado na BORDA (gate REINICIAR_CICLO)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("sub_key", "setor"),
    [("studio", "studio"), ("vendedor1", "vendedor"), ("clicheria", "clicheria")],
)
async def test_nao_admin_e_403_na_borda(ctx: tuple[Any, ...], sub_key: str, setor: str) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="reprovada_vendedor", rota="matriz"
    )
    resp = await _reiniciar(client, prova, _auth(ids[sub_key], setor))
    assert resp.status_code == 403, resp.text
    linha = await _prova_row(engine, prova)
    assert linha.status == "reprovada_vendedor"  # nada transicionado
    assert linha.ciclo_atual == 1
    assert await _movimentacoes(engine, prova) == []


async def test_sem_token_e_401(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="reprovada_vendedor", rota="matriz"
    )
    resp = await client.post(
        f"/provas/{prova}/reiniciar", json={"idempotency_key": str(uuid.uuid4())}
    )
    assert resp.status_code == 401


async def test_usuario_nao_provisionado_e_403(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="reprovada_vendedor", rota="matriz"
    )
    # Token de admin, mas sem linha em ``usuarios`` → gate nega (defesa em profundidade).
    resp = await _reiniciar(client, prova, _auth(str(uuid.uuid4()), "studio", admin=True))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Flag administrador é ortogonal ao setor (ADR-064)
# ---------------------------------------------------------------------------
async def test_vendedor_admin_reinicia_a_propria_prova(ctx: tuple[Any, ...]) -> None:
    client, engine, _ids = ctx
    vadmin = await _seed_usuario(engine, setor="vendedor", administrador=True)
    prova = await _seed_prova(
        engine, vendedor_id=vadmin, status="reprovada_vendedor", rota="matriz"
    )
    resp = await _reiniciar(client, prova, _auth(vadmin, "vendedor", admin=True))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "criada"
    assert resp.json()["ciclo_atual"] == 2


async def test_inexistente_e_404(ctx: tuple[Any, ...]) -> None:
    client, _engine, ids = ctx
    resp = await _reiniciar(client, str(uuid.uuid4()), _auth(ids["admin"], "studio", admin=True))
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["message"] == "Prova não encontrada."


# ---------------------------------------------------------------------------
# Idempotência (RNF-015) — reenvio converge: UMA movimentação, UM incremento
# ---------------------------------------------------------------------------
async def test_reenvio_com_mesma_chave_converge_um_incremento(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="reprovada_vendedor", rota="matriz"
    )
    chave = str(uuid.uuid4())
    h = _auth(ids["admin"], "studio", admin=True)
    r1 = await _reiniciar(client, prova, h, idem=chave)
    r2 = await _reiniciar(client, prova, h, idem=chave)
    assert r1.status_code == r2.status_code == 200, (r1.text, r2.text)
    assert r1.json()["ciclo_atual"] == r2.json()["ciclo_atual"] == 2  # NÃO incrementou 2x (≠ 3)
    assert (await _prova_row(engine, prova)).ciclo_atual == 2
    assert len(await _movimentacoes(engine, prova)) == 1  # UMA movimentação


async def test_reiniciar_de_novo_apos_novo_ciclo_volta_a_reprovar(ctx: tuple[Any, ...]) -> None:
    """Após reiniciar (→ Criada, ciclo 2), a prova NÃO está mais reprovada → um novo
    reinício (chave nova) é transição indefinida → 422 (não reincrementa)."""
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="reprovada_vendedor", rota="matriz"
    )
    h = _auth(ids["admin"], "studio", admin=True)
    primeiro = await _reiniciar(client, prova, h)
    assert primeiro.status_code == 200, primeiro.text
    # Agora em ``criada`` (ciclo 2): reiniciar de novo → 422 (estado inválido).
    de_novo = await _reiniciar(client, prova, h, idem=str(uuid.uuid4()))
    assert de_novo.status_code == 422, de_novo.text
    assert de_novo.json()["error"]["code"] == "transicao_invalida"
    assert (await _prova_row(engine, prova)).ciclo_atual == 2  # segue 2, não 3
