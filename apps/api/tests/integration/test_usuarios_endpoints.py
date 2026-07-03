"""Endpoints de usuários (W1-C04) contra Postgres REAL (@db) — guard, CRUD,
filtros e regras de negócio expostas via HTTP.

Auth própria (migração Supabase->local): a criação grava a credencial local
(auth_credentials) na MESMA transação. O Postgres é o local de teste
(TEST_DATABASE_URL); JWT assinado com segredo HS256 de teste.
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
from src.domain.usuarios import Localizacao, Setor
from src.infrastructure.config import Settings

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"
ADMIN_ID = "11111111-1111-1111-1111-111111111111"
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"
SENHA_OK = "senha-forte-1"


def _token(sub: str, **overrides: Any) -> str:
    """JWT de teste já no formato PÓS-HOOK (W1-C05): carrega ``user_id`` (= sub) e,
    quando o ator é admin, ``administrador``/``setor`` — os claims que o Custom
    Access Token Hook eleva em produção e que a RLS lê (DAT §7.2)."""
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


def _auth(sub: str, **overrides: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(sub, **overrides)}"}


def _auth_admin() -> dict[str, str]:
    """Ator administrador 3Studio — claims que a RLS admin de ``usuarios`` lê."""
    return _auth(ADMIN_ID, setor="studio", administrador=True)


@pytest.fixture
async def ctx(
    settings: Settings, fake_storage: FakeStorage, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, Any]]:
    """Client ASGI + engine do PG de teste + session factory (auth própria local)."""
    factory = async_sessionmaker(usuarios_engine, expire_on_commit=False)
    verifier = JwtVerifier(hs256_secret=HS256_SECRET)
    client = make_client(
        settings,
        fake_storage,
        ping_ok,
        jwt_verifier=verifier,
        session_factory=factory,
    )
    async with client as c:
        yield c, usuarios_engine, factory


async def _seed_usuario(
    factory: Any,
    *,
    usuario_id: str,
    nome: str,
    email: str,
    setor: Setor = Setor.STUDIO,
    localizacao: Localizacao | None = None,
    administrador: bool = False,
    ativo: bool = True,
) -> None:
    async with factory() as session:
        session.add(
            UsuarioRow(
                id=usuario_id,
                nome=nome,
                email=email,
                setor=setor,
                localizacao=localizacao,
                administrador=administrador,
                ativo=ativo,
            )
        )
        await session.commit()


async def _seed_admin(factory: Any) -> None:
    await _seed_usuario(
        factory,
        usuario_id=ADMIN_ID,
        nome="Mônica",
        email="monica@3studio.test",
        administrador=True,
    )


def _payload_criacao(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "nome": "Mario Souza",
        "email": "mario@estudio.com.br",
        "senha": SENHA_OK,
        "setor": "vendedor",
        "localizacao": "matriz",
        "administrador": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Guard de admin (DP-5) — critério de aceitação §6.4
# ---------------------------------------------------------------------------
async def test_listagem_sem_token_401(ctx: Any) -> None:
    client, _, _ = ctx
    resp = await client.get("/usuarios")
    assert resp.status_code == 401


async def test_listagem_token_sem_linha_de_dominio_403(ctx: Any) -> None:
    client, _, _ = ctx
    resp = await client.get("/usuarios", headers=_auth(str(uuid.uuid4())))
    assert resp.status_code == 403


async def test_listagem_nao_admin_403(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_usuario(
        factory,
        usuario_id=VENDEDOR_ID,
        nome="Ana",
        email="ana@x.y",
        setor=Setor.VENDEDOR,
        localizacao=Localizacao.MATRIZ,
    )
    resp = await client.get("/usuarios", headers=_auth(VENDEDOR_ID))
    assert resp.status_code == 403


async def test_admin_inativo_403(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_usuario(
        factory,
        usuario_id=ADMIN_ID,
        nome="Mônica",
        email="monica@3studio.test",
        administrador=True,
        ativo=False,
    )
    resp = await client.get("/usuarios", headers=_auth_admin())
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /usuarios/me — alimenta o shell (qualquer autenticado provisionado)
# ---------------------------------------------------------------------------
async def test_me_devolve_linha_do_proprio_usuario(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_usuario(
        factory,
        usuario_id=VENDEDOR_ID,
        nome="Ana Lima",
        email="ana@x.y",
        setor=Setor.VENDEDOR,
        localizacao=Localizacao.FILIAL,
    )
    resp = await client.get("/usuarios/me", headers=_auth(VENDEDOR_ID))
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome"] == "Ana Lima"
    assert body["setor"] == "vendedor"
    assert body["localizacao"] == "filial"
    assert body["administrador"] is False


async def test_me_sem_provisionamento_404(ctx: Any) -> None:
    client, _, _ = ctx
    resp = await client.get("/usuarios/me", headers=_auth(str(uuid.uuid4())))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /usuarios — criação coordenada
# ---------------------------------------------------------------------------
async def test_criar_usuario_caminho_feliz(ctx: Any) -> None:
    client, engine, factory = ctx
    await _seed_admin(factory)

    resp = await client.post("/usuarios", json=_payload_criacao(), headers=_auth_admin())

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "mario@estudio.com.br"
    assert body["ativo"] is True
    assert body["created_at"] is not None
    # Credencial de login criada JUNTO (mesma transação), com hash argon2id.
    async with engine.connect() as conn:
        cred = (
            await conn.execute(
                text("SELECT email, senha_hash FROM auth_credentials WHERE user_id = :id"),
                {"id": body["id"]},
            )
        ).one()
    assert cred.email == "mario@estudio.com.br"
    assert cred.senha_hash.startswith("$argon2id$")
    # persistido de fato (visível em nova listagem)
    listagem = await client.get("/usuarios", headers=_auth_admin())
    emails = [u["email"] for u in listagem.json()["items"]]
    assert "mario@estudio.com.br" in emails


@pytest.mark.parametrize(
    "payload_ruim",
    [
        {"senha": "curta1"},  # < 8
        {"senha": "semnumero"},  # sem dígito
        {"senha": "12345678"},  # sem letra
        {"email": "nao-e-email"},
        {"nome": "   "},
        {"setor": "diretoria"},  # fora do enum
    ],
)
async def test_criar_payload_invalido_422(ctx: Any, payload_ruim: dict[str, Any]) -> None:
    client, _, factory = ctx
    await _seed_admin(factory)
    resp = await client.post(
        "/usuarios", json=_payload_criacao(**payload_ruim), headers=_auth_admin()
    )
    assert resp.status_code == 422  # rejeitado na borda (validação de forma)


async def test_criar_vendedor_sem_localizacao_422(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_admin(factory)
    resp = await client.post(
        "/usuarios",
        json=_payload_criacao(localizacao=None),
        headers=_auth_admin(),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "localizacao_invalida"


async def test_criar_email_duplicado_409(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_admin(factory)
    primeiro = await client.post("/usuarios", json=_payload_criacao(), headers=_auth_admin())
    assert primeiro.status_code == 201
    segundo = await client.post(
        "/usuarios", json=_payload_criacao(nome="Outro"), headers=_auth_admin()
    )
    assert segundo.status_code == 409
    assert segundo.json()["error"]["code"] == "email_ja_cadastrado"


# ---------------------------------------------------------------------------
# GET /usuarios — paginação, busca e filtros (RNF-019/RNF-023)
# ---------------------------------------------------------------------------
async def _seed_listagem(factory: Any) -> None:
    await _seed_admin(factory)
    dados = [
        ("Ana Lima", "ana@x.y", Setor.VENDEDOR, Localizacao.MATRIZ, True),
        ("Bruno Reis", "bruno@x.y", Setor.MOTORISTA, None, True),
        ("Carla Souza", "carla@x.y", Setor.CLICHERIA, None, False),
        ("Diego Cruz", "diego@x.y", Setor.VENDEDOR, Localizacao.FILIAL, True),
    ]
    for i, (nome, email, setor, loc, ativo) in enumerate(dados):
        await _seed_usuario(
            factory,
            usuario_id=f"00000000-0000-0000-0000-00000000000{i + 2}",
            nome=nome,
            email=email,
            setor=setor,
            localizacao=loc,
            ativo=ativo,
        )


async def test_listagem_paginada_e_ordenada(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_listagem(factory)

    resp = await client.get("/usuarios", params={"page": 1, "page_size": 2}, headers=_auth_admin())
    body = resp.json()
    assert body["total"] == 5  # 4 + admin
    assert [u["nome"] for u in body["items"]] == ["Ana Lima", "Bruno Reis"]

    resp2 = await client.get("/usuarios", params={"page": 2, "page_size": 2}, headers=_auth_admin())
    assert [u["nome"] for u in resp2.json()["items"]] == ["Carla Souza", "Diego Cruz"]


async def test_busca_por_nome_ou_email(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_listagem(factory)

    por_nome = await client.get("/usuarios", params={"busca": "souza"}, headers=_auth_admin())
    assert [u["nome"] for u in por_nome.json()["items"]] == ["Carla Souza"]

    por_email = await client.get("/usuarios", params={"busca": "bruno@"}, headers=_auth_admin())
    assert [u["nome"] for u in por_email.json()["items"]] == ["Bruno Reis"]


async def test_busca_escapa_curingas(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_listagem(factory)
    resp = await client.get("/usuarios", params={"busca": "%"}, headers=_auth_admin())
    assert resp.json()["total"] == 0  # '%' literal não casa com nada


async def test_filtros_setor_e_status(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_listagem(factory)

    vendedores = await client.get("/usuarios", params={"setor": "vendedor"}, headers=_auth_admin())
    assert {u["nome"] for u in vendedores.json()["items"]} == {"Ana Lima", "Diego Cruz"}

    inativos = await client.get("/usuarios", params={"status": "inativo"}, headers=_auth_admin())
    assert [u["nome"] for u in inativos.json()["items"]] == ["Carla Souza"]

    combinado = await client.get(
        "/usuarios",
        params={"setor": "vendedor", "status": "ativo", "busca": "diego"},
        headers=_auth_admin(),
    )
    assert [u["nome"] for u in combinado.json()["items"]] == ["Diego Cruz"]


# ---------------------------------------------------------------------------
# PATCH /usuarios/{id} + desativar/reativar — RN-009/RN-010 via API
# ---------------------------------------------------------------------------
async def test_editar_usuario(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_listagem(factory)

    resp = await client.patch(
        "/usuarios/00000000-0000-0000-0000-000000000002",
        json={"nome": "Ana de Lima", "administrador": True},
        headers=_auth_admin(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome"] == "Ana de Lima"
    assert body["administrador"] is True
    assert body["setor"] == "vendedor"  # inalterado


async def test_editar_auto_remocao_de_admin_422(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_admin(factory)
    resp = await client.patch(
        f"/usuarios/{ADMIN_ID}",
        json={"administrador": False},
        headers=_auth_admin(),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "auto_remocao_admin"


async def test_editar_inexistente_404(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_admin(factory)
    resp = await client.patch(
        f"/usuarios/{uuid.uuid4()}", json={"nome": "X"}, headers=_auth_admin()
    )
    assert resp.status_code == 404


async def test_desativar_e_reativar(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_listagem(factory)
    alvo = "00000000-0000-0000-0000-000000000002"

    desativa = await client.post(f"/usuarios/{alvo}/desativar", headers=_auth_admin())
    assert desativa.status_code == 200
    assert desativa.json()["ativo"] is False

    # idempotente: repetir converge (RNF-015)
    repete = await client.post(f"/usuarios/{alvo}/desativar", headers=_auth_admin())
    assert repete.status_code == 200
    assert repete.json()["ativo"] is False

    # histórico preservado: a linha segue lá (US-015)
    lista = await client.get("/usuarios", params={"status": "inativo"}, headers=_auth_admin())
    assert any(u["id"] == alvo for u in lista.json()["items"])

    reativa = await client.post(f"/usuarios/{alvo}/reativar", headers=_auth_admin())
    assert reativa.status_code == 200
    assert reativa.json()["ativo"] is True


async def test_auto_desativacao_422(ctx: Any) -> None:
    client, _, factory = ctx
    await _seed_admin(factory)
    resp = await client.post(f"/usuarios/{ADMIN_ID}/desativar", headers=_auth_admin())
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "auto_desativacao"


async def test_desativar_outro_admin_passa_pelo_lock_transacional(ctx: Any) -> None:
    """Com DOIS admins ativos, desativar o outro exercita o caminho completo:
    advisory lock + recheck + UPDATE com lock otimista, contra Postgres real."""
    client, _, factory = ctx
    await _seed_admin(factory)
    outro = "33333333-3333-3333-3333-333333333333"
    await _seed_usuario(factory, usuario_id=outro, nome="Bia", email="bia@x.y", administrador=True)

    resp = await client.post(f"/usuarios/{outro}/desativar", headers=_auth_admin())
    assert resp.status_code == 200
    assert resp.json()["ativo"] is False


# ---------------------------------------------------------------------------
# Repositório (regressões da revisão adversarial W1-C04)
# ---------------------------------------------------------------------------
async def test_update_com_snapshot_obsoleto_levanta_conflito(ctx: Any) -> None:
    """Lock otimista: UPDATE baseado num updated_at antigo → 409, nunca
    sobrescrita silenciosa de uma escrita concorrente."""
    from src.adapters.outbound.db.usuarios_repository import SqlAlchemyUsuariosRepository
    from src.domain.usuarios import ConflitoDeConcorrenciaError

    _, _, factory = ctx
    await _seed_admin(factory)
    async with factory() as session:
        repo = SqlAlchemyUsuariosRepository(session)
        usuario = await repo.get(ADMIN_ID)
        assert usuario is not None
        # 1ª escrita avança o updated_at
        await repo.update(usuario.com(nome="Mônica A"))
        await session.commit()

    async with factory() as session:
        repo = SqlAlchemyUsuariosRepository(session)
        # snapshot OBSOLETO (updated_at anterior à 1ª escrita)
        with pytest.raises(ConflitoDeConcorrenciaError):
            await repo.update(usuario.com(nome="Mônica B"))


async def test_insert_email_duplicado_no_banco_vira_regra_de_negocio(ctx: Any) -> None:
    """A violação do índice único de e-mail (corrida que passa pela
    pré-checagem) é traduzida para EmailJaCadastradoError (409), não 500."""
    from src.adapters.outbound.db.usuarios_repository import SqlAlchemyUsuariosRepository
    from src.application.usuarios import EmailJaCadastradoError
    from src.domain.usuarios import Setor as SetorDom
    from src.domain.usuarios import Usuario as UsuarioDom

    _, _, factory = ctx
    await _seed_admin(factory)
    async with factory() as session:
        repo = SqlAlchemyUsuariosRepository(session)
        duplicado = UsuarioDom(
            id=str(uuid.uuid4()),
            nome="Clone",
            email="MONICA@3studio.test",  # case diferente — índice é lower(email)
            setor=SetorDom.STUDIO,
        )
        with pytest.raises(EmailJaCadastradoError):
            await repo.add(duplicado)


# ---------------------------------------------------------------------------
# Código do vendedor no ERP (Firebird) — Fatia 4
# ---------------------------------------------------------------------------
async def test_criar_vendedor_com_cod_firebird(ctx: tuple[Any, ...]) -> None:
    client, _, factory = ctx
    await _seed_admin(factory)
    resp = await client.post(
        "/usuarios", json=_payload_criacao(cod_vendedor_firebird=42), headers=_auth_admin()
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["cod_vendedor_firebird"] == 42


async def test_criar_nao_vendedor_com_cod_firebird_e_422(ctx: tuple[Any, ...]) -> None:
    client, _, factory = ctx
    await _seed_admin(factory)
    resp = await client.post(
        "/usuarios",
        json=_payload_criacao(setor="studio", localizacao=None, cod_vendedor_firebird=42),
        headers=_auth_admin(),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "cod_vendedor_firebird_invalido"


async def test_editar_define_cod_firebird(ctx: tuple[Any, ...]) -> None:
    client, _, factory = ctx
    await _seed_admin(factory)
    criado = await client.post(
        "/usuarios", json=_payload_criacao(email="v@x.z"), headers=_auth_admin()
    )
    uid = criado.json()["id"]
    resp = await client.patch(
        f"/usuarios/{uid}", json={"cod_vendedor_firebird": 77}, headers=_auth_admin()
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["cod_vendedor_firebird"] == 77


async def test_editar_trocar_setor_zera_cod_firebird(ctx: tuple[Any, ...]) -> None:
    """Fatia 3 (nota): mudar o setor para fora de Vendedor DEVE zerar o código —
    senão o CHECK do banco rejeitaria o UPDATE (500)."""
    client, _, factory = ctx
    await _seed_admin(factory)
    criado = await client.post(
        "/usuarios",
        json=_payload_criacao(email="v2@x.z", cod_vendedor_firebird=99),
        headers=_auth_admin(),
    )
    uid = criado.json()["id"]
    assert criado.json()["cod_vendedor_firebird"] == 99
    resp = await client.patch(
        f"/usuarios/{uid}",
        json={"setor": "clicheria", "localizacao": None},
        headers=_auth_admin(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["setor"] == "clicheria"
    assert resp.json()["cod_vendedor_firebird"] is None
