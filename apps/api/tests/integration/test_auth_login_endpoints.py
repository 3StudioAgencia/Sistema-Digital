"""Login/refresh/logout da autenticação PRÓPRIA contra Postgres real (@db).

Migração Supabase->local: exercita o caminho pré-auth de ponta a ponta —
credencial (argon2) + emissão ES256 + refresh rotativo + cookies httpOnly —
contra as funções ``private.auth_*`` e a RLS deny-all das tabelas de auth.
"""

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from src.adapters.inbound.http.auth import JwtVerifier
from src.adapters.outbound.auth.argon2_hasher import Argon2PasswordHasher
from src.adapters.outbound.auth.es256_issuer import Es256TokenIssuer
from src.infrastructure.config import Settings

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

ISSUER = "rastreio-api"
SENHA = "SenhaForte1"
_HASHER = Argon2PasswordHasher()
_SENHA_HASH = _HASHER.hash(SENHA)


async def _seed_credencial(
    engine: AsyncEngine,
    *,
    setor: str = "vendedor",
    administrador: bool = False,
    ativo: bool = True,
    senha_hash: str = _SENHA_HASH,
) -> tuple[str, str]:
    """Insere usuário + credencial como OWNER (RLS bypass). Devolve (id, email)."""
    uid = str(uuid.uuid4())
    email = f"{uid}@x.z"
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador, ativo) "
                "VALUES (:id, 'U', :email, :setor, :loc, :adm, :ativo)"
            ),
            {"id": uid, "email": email, "setor": setor, "loc": loc, "adm": administrador,
             "ativo": ativo},
        )
        await conn.execute(
            text(
                "INSERT INTO auth_credentials (user_id, email, senha_hash) "
                "VALUES (:id, :email, :h)"
            ),
            {"id": uid, "email": email, "h": senha_hash},
        )
    return uid, email


@pytest.fixture
async def ctx(
    settings: Settings, fake_storage: FakeStorage, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine]]:
    """Client ASGI com emissor ES256 de teste + verifier da chave pública casada +
    sessão de sistema sobre o PG de teste."""
    key = ec.generate_private_key(ec.SECP256R1())
    issuer = Es256TokenIssuer(private_key=key, issuer=ISSUER, access_ttl_seconds=1800)
    verifier = JwtVerifier(public_key=key.public_key(), issuer=ISSUER)
    system_factory = async_sessionmaker(usuarios_engine, expire_on_commit=False)
    client = make_client(
        settings,
        fake_storage,
        ping_ok,
        jwt_verifier=verifier,
        token_issuer=issuer,
        system_session_factory=system_factory,
    )
    async with client as c:
        yield c, usuarios_engine


async def test_login_sucesso_seta_cookies_e_retorna_perfil(
    ctx: tuple[httpx.AsyncClient, AsyncEngine],
) -> None:
    client, engine = ctx
    uid, email = await _seed_credencial(engine, setor="vendedor", administrador=False)
    resp = await client.post("/auth/login", json={"email": email, "senha": SENHA})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == uid
    assert body["setor"] == "vendedor"
    assert body["administrador"] is False
    assert client.cookies.get("access_token")
    assert client.cookies.get("refresh_token")


async def test_login_senha_errada_401(ctx: tuple[httpx.AsyncClient, AsyncEngine]) -> None:
    client, engine = ctx
    _, email = await _seed_credencial(engine)
    resp = await client.post("/auth/login", json={"email": email, "senha": "ErradaTotal9"})
    assert resp.status_code == 401
    assert not client.cookies.get("access_token")


async def test_login_email_inexistente_401(ctx: tuple[httpx.AsyncClient, AsyncEngine]) -> None:
    client, _ = ctx
    resp = await client.post("/auth/login", json={"email": "naoexiste@x.z", "senha": SENHA})
    assert resp.status_code == 401


async def test_login_usuario_inativo_401(ctx: tuple[httpx.AsyncClient, AsyncEngine]) -> None:
    client, engine = ctx
    _, email = await _seed_credencial(engine, ativo=False)
    resp = await client.post("/auth/login", json={"email": email, "senha": SENHA})
    assert resp.status_code == 401


async def test_access_cookie_autentica_me(ctx: tuple[httpx.AsyncClient, AsyncEngine]) -> None:
    client, engine = ctx
    uid, email = await _seed_credencial(engine, setor="studio", administrador=True)
    await client.post("/auth/login", json={"email": email, "senha": SENHA})
    # O cookie access_token no jar autentica o /auth/me (verifier = chave pública).
    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["sub"] == uid


async def test_refresh_rotaciona_e_renova(ctx: tuple[httpx.AsyncClient, AsyncEngine]) -> None:
    client, engine = ctx
    _, email = await _seed_credencial(engine)
    await client.post("/auth/login", json={"email": email, "senha": SENHA})
    refresh_antigo = client.cookies.get("refresh_token")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200
    assert client.cookies.get("refresh_token") != refresh_antigo  # rotacionado


async def test_refresh_token_reusado_401(ctx: tuple[httpx.AsyncClient, AsyncEngine]) -> None:
    client, engine = ctx
    _, email = await _seed_credencial(engine)
    await client.post("/auth/login", json={"email": email, "senha": SENHA})
    antigo = client.cookies.get("refresh_token")
    await client.post("/auth/refresh")  # rotaciona → revoga o antigo
    client.cookies.clear()
    resp = await client.post("/auth/refresh", headers={"Cookie": f"refresh_token={antigo}"})
    assert resp.status_code == 401


async def test_logout_revoga_refresh(ctx: tuple[httpx.AsyncClient, AsyncEngine]) -> None:
    client, engine = ctx
    _, email = await _seed_credencial(engine)
    await client.post("/auth/login", json={"email": email, "senha": SENHA})
    antigo = client.cookies.get("refresh_token")
    out = await client.post("/auth/logout")
    assert out.status_code == 204
    client.cookies.clear()
    resp = await client.post("/auth/refresh", headers={"Cookie": f"refresh_token={antigo}"})
    assert resp.status_code == 401


async def test_authenticated_nao_le_credencial(
    ctx: tuple[httpx.AsyncClient, AsyncEngine],
) -> None:
    """Segurança: o role ``authenticated`` NÃO pode executar a leitura de
    credencial (senão um usuário logado colheria o hash alheio)."""
    _, engine = ctx
    with pytest.raises(DBAPIError):
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                await conn.execute(text("SET LOCAL ROLE authenticated"))
                await conn.execute(
                    text("SELECT * FROM private.auth_credencial_por_email('x@x.z')")
                )
            finally:
                await trans.rollback()
