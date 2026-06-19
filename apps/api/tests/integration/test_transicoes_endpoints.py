"""Transição da máquina de estados (W3-C11) contra Postgres REAL (@db).

Exercita ``POST /provas/{id}/transicoes`` pelo caminho HTTP inteiro como em
produção (``SET LOCAL ROLE authenticated`` + claims propagados — ADR-008),
validando os critérios §6:

- travessia COMPLETA de cada rota (Matriz/Lam.Matriz/Filial/Lam.Filial) com o
  perfil correto, até o terminal (``finalizada_em`` carimbado);
- transição não definida → 422; perfil não autorizado → 403; prova fora do
  escopo / inexistente → 404 genérico (anti-enumeração);
- Aprovar/Reprovar (motivo obrigatório); Cancelar (admin + motivo) e Reiniciar;
- idempotência: reenvio com a mesma chave → 200, UMA movimentação;
- o Motorista identifica+transiciona a prova de ORIGEM (escopo ampliado — a
  pendência que o C11 destravou);
- W3-C12: a assinatura desenhada nasce JUNTO com a movimentação (vínculo
  ``movimentacoes.assinatura_ref``), atomicamente; assinatura inválida → 422 sem
  efeito; ``GET /acoes-disponiveis`` orienta a tela de confirmação.
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
from src.domain.provas import gerar_codigo
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"
# Imagem mínima que passa por ``validar_assinatura`` (magic bytes de PNG), em base64.
ASSINATURA_PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16).decode()


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
        "motorista": await _seed_usuario(engine, setor="motorista"),
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


async def _transicionar(
    client: httpx.AsyncClient,
    prova_id: str,
    acao: str,
    headers: dict[str, str],
    *,
    motivo: str | None = None,
    idem: str | None = None,
) -> httpx.Response:
    body: dict[str, Any] = {
        "acao": acao,
        "assinatura": ASSINATURA_PNG_B64,
        "idempotency_key": idem or str(uuid.uuid4()),
    }
    if motivo is not None:
        body["motivo"] = motivo
    return await client.post(f"/provas/{prova_id}/transicoes", json=body, headers=headers)


async def _contar_movs(engine: AsyncEngine, prova_id: str) -> int:
    async with engine.connect() as conn:
        return int(
            (
                await conn.execute(
                    text("SELECT count(*) FROM movimentacoes WHERE prova_id = :p"),
                    {"p": prova_id},
                )
            ).scalar_one()
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
# Travessia completa de cada rota (caminho feliz) até o terminal
# ---------------------------------------------------------------------------
async def test_travessia_completa_rota_matriz(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    passos = [
        ("identificar_e_assinar", _auth(ids["vendedor1"], "vendedor"), "retirada_vendedor"),
        ("aprovar", _auth(ids["vendedor1"], "vendedor"), "aprovada_vendedor"),
        ("identificar_e_assinar", _auth(ids["studio"], "studio"), "de_volta_studio"),
        (
            "identificar_e_assinar",
            _auth(ids["motorista"], "motorista"),
            "com_motorista_entrega_final",
        ),
        ("identificar_e_assinar", _auth(ids["clicheria"], "clicheria"), "recebida_clicheria"),
    ]
    for acao, headers, destino in passos:
        resp = await _transicionar(client, prova, acao, headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == destino
    assert resp.json()["finalizada_em"] is not None  # terminal carimbado
    assert await _contar_movs(engine, prova) == 5


async def test_travessia_completa_rota_lam_matriz(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="criada", rota="lam_matriz"
    )
    v, s, m, cl = "vendedor", "studio", "motorista", "clicheria"
    passos = [
        ("identificar_e_assinar", ids["studio"], s, "encaminhada_para_laminacao"),
        ("identificar_e_assinar", ids["motorista"], m, "com_motorista_ida_laminacao"),
        ("identificar_e_assinar", ids["clicheria"], cl, "laminacao_concluida"),
        ("identificar_e_assinar", ids["motorista"], m, "com_motorista_volta_laminacao"),
        ("identificar_e_assinar", ids["studio"], s, "de_volta_studio_pos_laminacao"),
        ("identificar_e_assinar", ids["vendedor1"], v, "retirada_vendedor"),
        ("aprovar", ids["vendedor1"], v, "aprovada_vendedor"),
        ("identificar_e_assinar", ids["studio"], s, "de_volta_studio"),
        ("identificar_e_assinar", ids["motorista"], m, "com_motorista_entrega_final"),
        ("identificar_e_assinar", ids["clicheria"], cl, "recebida_clicheria"),
    ]
    for acao, sub, setor, destino in passos:
        resp = await _transicionar(client, prova, acao, _auth(sub, setor))
        assert resp.status_code == 200, f"{destino}: {resp.text}"
        assert resp.json()["status"] == destino
    assert await _contar_movs(engine, prova) == 10


async def test_travessia_completa_rota_filial(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="filial")
    passos = [
        ("identificar_e_assinar", _auth(ids["vendedor1"], "vendedor"), "encaminhada_para_vendedor"),
        ("aprovar", _auth(ids["vendedor1"], "vendedor"), "aprovada_vendedor"),
        ("identificar_e_assinar", _auth(ids["clicheria"], "clicheria"), "recebida_clicheria"),
    ]
    for acao, headers, destino in passos:
        resp = await _transicionar(client, prova, acao, headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == destino


async def test_travessia_completa_rota_lam_filial(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="criada", rota="lam_filial"
    )
    passos = [
        ("identificar_e_assinar", ids["studio"], "studio", "encaminhada_para_laminacao"),
        ("identificar_e_assinar", ids["motorista"], "motorista", "com_motorista_ida_laminacao"),
        ("identificar_e_assinar", ids["clicheria"], "clicheria", "laminacao_concluida"),
        ("identificar_e_assinar", ids["vendedor1"], "vendedor", "encaminhada_para_vendedor"),
        ("aprovar", ids["vendedor1"], "vendedor", "aprovada_vendedor"),
        ("identificar_e_assinar", ids["clicheria"], "clicheria", "recebida_clicheria"),
    ]
    for acao, sub, setor, destino in passos:
        resp = await _transicionar(client, prova, acao, _auth(sub, setor))
        assert resp.status_code == 200, f"{destino}: {resp.text}"
        assert resp.json()["status"] == destino


# ---------------------------------------------------------------------------
# O Motorista identifica+transiciona a ORIGEM (escopo ampliado — pendência C11)
# ---------------------------------------------------------------------------
async def test_motorista_transiciona_a_partir_de_estado_de_origem(ctx: tuple[Any, ...]) -> None:
    """Antes do C11 o Motorista recebia 404 em ``encaminhada_para_laminacao``
    (fora do escopo Em-Trânsito). A RLS ampliada destrava a travessia."""
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="encaminhada_para_laminacao", rota="lam_matriz"
    )
    resp = await _transicionar(
        client, prova, "identificar_e_assinar", _auth(ids["motorista"], "motorista")
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "com_motorista_ida_laminacao"


# ---------------------------------------------------------------------------
# 422 / 403 / 404
# ---------------------------------------------------------------------------
async def test_transicao_nao_definida_e_422(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    # Aprovar não é válido em "criada" (Matriz).
    resp = await _transicionar(client, prova, "aprovar", _auth(ids["vendedor1"], "vendedor"))
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "transicao_invalida"


async def test_perfil_nao_autorizado_e_403_generico(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    # Clicheria vê TODAS (em escopo), mas não é o ator de "criada" (Matriz) → 403.
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _transicionar(
        client, prova, "identificar_e_assinar", _auth(ids["clicheria"], "clicheria")
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()["error"]
    assert body["code"] == "transicao_nao_autorizada"
    assert "setor" not in body["message"].lower()  # não revela quem poderia (RN-014)
    # E nada foi gravado/transicionado (a prova segue "criada").
    assert await _contar_movs(engine, prova) == 0


async def test_fora_do_escopo_e_inexistente_mesmo_404(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    # Prova do vendedor1; o vendedor2 não a enxerga (RLS) → 404 (anti-enumeração).
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    fora = await _transicionar(
        client, prova, "identificar_e_assinar", _auth(ids["vendedor2"], "vendedor")
    )
    inexistente = await _transicionar(
        client, str(uuid.uuid4()), "identificar_e_assinar", _auth(ids["vendedor2"], "vendedor")
    )
    for r in (fora, inexistente):
        assert r.status_code == 404, r.text
        assert r.json()["error"]["message"] == "Prova não encontrada."


# ---------------------------------------------------------------------------
# Aprovar / Reprovar (motivo obrigatório)
# ---------------------------------------------------------------------------
async def test_reprovar_exige_motivo(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="retirada_vendedor", rota="matriz"
    )
    sem = await _transicionar(client, prova, "reprovar", _auth(ids["vendedor1"], "vendedor"))
    assert sem.status_code == 422
    assert sem.json()["error"]["code"] == "motivo_obrigatorio"
    com = await _transicionar(
        client, prova, "reprovar", _auth(ids["vendedor1"], "vendedor"), motivo="cor errada"
    )
    assert com.status_code == 200
    assert com.json()["status"] == "reprovada_vendedor"


# ---------------------------------------------------------------------------
# Cancelar (admin + motivo) e Reiniciar Ciclo (admin)
# ---------------------------------------------------------------------------
async def test_cancelar_e_admin_com_motivo(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    # Não-admin (studio) → 403.
    nao = await _transicionar(client, prova, "cancelar", _auth(ids["studio"], "studio"), motivo="x")
    assert nao.status_code == 403
    # Admin sem motivo → 422.
    sem = await _transicionar(client, prova, "cancelar", _auth(ids["admin"], "studio", admin=True))
    assert sem.status_code == 422
    # Admin com motivo → cancelada + carimbo terminal.
    ok = await _transicionar(
        client, prova, "cancelar", _auth(ids["admin"], "studio", admin=True), motivo="desistência"
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "cancelada"
    assert ok.json()["finalizada_em"] is not None


async def test_vendedor_admin_pode_cancelar_e_reiniciar(ctx: tuple[Any, ...]) -> None:
    """ADR-023: a ação "Exclusivo 3Studio" chaveia pela FLAG admin (não pelo
    setor) — um Vendedor-admin cancela/reinicia."""
    client, engine, _ids = ctx
    vadmin = await _seed_usuario(engine, setor="vendedor", administrador=True)
    prova = await _seed_prova(
        engine, vendedor_id=vadmin, status="reprovada_vendedor", rota="matriz"
    )
    resp = await _transicionar(
        client, prova, "reiniciar_ciclo", _auth(vadmin, "vendedor", admin=True)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "criada"  # novo ciclo (rota preservada)


# ---------------------------------------------------------------------------
# Idempotência (RNF-015/DP-2)
# ---------------------------------------------------------------------------
async def test_reenvio_com_mesma_chave_converge_uma_movimentacao(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    chave = str(uuid.uuid4())
    h = _auth(ids["vendedor1"], "vendedor")
    r1 = await _transicionar(client, prova, "identificar_e_assinar", h, idem=chave)
    r2 = await _transicionar(client, prova, "identificar_e_assinar", h, idem=chave)
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["status"] == r2.json()["status"] == "retirada_vendedor"
    assert await _contar_movs(engine, prova) == 1  # NÃO duplicou nem transicionou 2x


async def test_mesma_chave_para_operacao_diferente_e_409(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    p1 = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    p2 = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    chave = str(uuid.uuid4())
    h = _auth(ids["vendedor1"], "vendedor")
    r1 = await _transicionar(client, p1, "identificar_e_assinar", h, idem=chave)
    assert r1.status_code == 200
    conflito = await _transicionar(client, p2, "identificar_e_assinar", h, idem=chave)
    assert conflito.status_code == 409, conflito.text
    assert conflito.json()["error"]["code"] == "idempotencia_conflito"


# ---------------------------------------------------------------------------
# Gate de acesso
# ---------------------------------------------------------------------------
async def test_sem_token_e_401(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await client.post(
        f"/provas/{prova}/transicoes",
        json={
            "acao": "identificar_e_assinar",
            "assinatura": ASSINATURA_PNG_B64,
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 401


async def test_usuario_nao_provisionado_e_403(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _transicionar(
        client, prova, "identificar_e_assinar", _auth(str(uuid.uuid4()), "vendedor")
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# W3-C12: assinatura digital — vínculo, atomicidade, anti-enumeração
# ---------------------------------------------------------------------------
async def test_assinatura_nasce_vinculada_a_movimentacao(ctx: tuple[Any, ...]) -> None:
    """A transição grava UMA assinatura, e a movimentação a referencia
    (``assinatura_ref`` → ``assinaturas.id``), tudo na mesma transação."""
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _transicionar(
        client, prova, "identificar_e_assinar", _auth(ids["vendedor1"], "vendedor")
    )
    assert resp.status_code == 200, resp.text
    assert await _contar_assinaturas(engine, prova) == 1
    async with engine.connect() as conn:
        linha = (
            await conn.execute(
                text(
                    "SELECT m.assinatura_ref, a.id, a.ator_id, a.content_type,"
                    " octet_length(a.imagem) AS tamanho"
                    " FROM movimentacoes m JOIN assinaturas a ON a.id = m.assinatura_ref"
                    " WHERE m.prova_id = :p"
                ),
                {"p": prova},
            )
        ).one()
    assert linha.assinatura_ref == linha.id  # vínculo correto
    assert str(linha.ator_id) == ids["vendedor1"]  # ator = quem assinou
    assert linha.content_type == "image/png"
    assert linha.tamanho > 0  # a imagem foi persistida (bytea)


async def test_assinatura_invalida_e_422_sem_efeito(ctx: tuple[Any, ...]) -> None:
    """Imagem base64 que não é imagem → 422; nada é gravado (atomicidade)."""
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    lixo = base64.b64encode(b"isto nao e uma imagem").decode()
    resp = await client.post(
        f"/provas/{prova}/transicoes",
        json={
            "acao": "identificar_e_assinar",
            "assinatura": lixo,
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=_auth(ids["vendedor1"], "vendedor"),
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "assinatura_invalida"
    assert await _contar_movs(engine, prova) == 0
    assert await _contar_assinaturas(engine, prova) == 0


async def test_base64_malformado_e_422(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await client.post(
        f"/provas/{prova}/transicoes",
        json={
            "acao": "identificar_e_assinar",
            "assinatura": "@@@nao-e-base64@@@",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=_auth(ids["vendedor1"], "vendedor"),
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "assinatura_invalida"


async def test_reenvio_idempotente_nao_duplica_assinatura(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    chave = str(uuid.uuid4())
    h = _auth(ids["vendedor1"], "vendedor")
    r1 = await _transicionar(client, prova, "identificar_e_assinar", h, idem=chave)
    r2 = await _transicionar(client, prova, "identificar_e_assinar", h, idem=chave)
    assert r1.status_code == r2.status_code == 200
    assert await _contar_movs(engine, prova) == 1
    assert await _contar_assinaturas(engine, prova) == 1  # reenvio NÃO recriou


# ---------------------------------------------------------------------------
# W3-C12: GET /acoes-disponiveis — orienta a tela de confirmação (DP-3/DP-4)
# ---------------------------------------------------------------------------
async def _acoes(
    client: httpx.AsyncClient, prova_id: str, headers: dict[str, str]
) -> httpx.Response:
    return await client.get(f"/provas/{prova_id}/acoes-disponiveis", headers=headers)


async def test_acoes_disponiveis_proximo_ator_assina(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _acoes(client, prova, _auth(ids["vendedor1"], "vendedor"))
    assert resp.status_code == 200, resp.text
    assert [a["acao"] for a in resp.json()] == ["identificar_e_assinar"]


async def test_acoes_disponiveis_aprovar_reprovar_com_motivo(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(
        engine, vendedor_id=ids["vendedor1"], status="retirada_vendedor", rota="matriz"
    )
    resp = await _acoes(client, prova, _auth(ids["vendedor1"], "vendedor"))
    assert resp.status_code == 200
    por_acao = {a["acao"]: a for a in resp.json()}
    assert set(por_acao) == {"aprovar", "reprovar"}
    assert por_acao["reprovar"]["exige_motivo"] is True
    assert por_acao["aprovar"]["exige_motivo"] is False


async def test_acoes_disponiveis_nao_ator_lista_vazia(ctx: tuple[Any, ...]) -> None:
    """Clicheria vê a prova (em escopo) mas não é o ator de 'criada' → lista vazia
    (a UI mostra o bloqueio genérico, sem revelar quem é — RN-014)."""
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _acoes(client, prova, _auth(ids["clicheria"], "clicheria"))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_acoes_disponiveis_admin_nao_lista_cancelar(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _acoes(client, prova, _auth(ids["admin"], "studio", admin=True))
    assert resp.status_code == 200
    assert "cancelar" not in {a["acao"] for a in resp.json()}


async def test_acoes_disponiveis_fora_do_escopo_e_404(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor1"], status="criada", rota="matriz")
    resp = await _acoes(client, prova, _auth(ids["vendedor2"], "vendedor"))
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "Prova não encontrada."
