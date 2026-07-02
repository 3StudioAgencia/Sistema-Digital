"""bootstrap_admin — raiz de confiança do RBAC, contra Postgres real (@db).

Auth própria (migração Supabase->local): cria o admin inicial COM senha,
inserindo direto (owner) ``usuarios`` + ``auth_credentials``. Prova idempotência
(repetir converge, reseta a senha) e que a credencial é utilizável (hash argon2id).
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from src.adapters.outbound.auth.argon2_hasher import Argon2PasswordHasher
from src.infrastructure.config import Settings
from src.tasks import bootstrap_admin as bm

pytestmark = pytest.mark.db


def _settings(url: str) -> Settings:
    return Settings(_env_file=None, database_url=url, migrations_database_url=url)


async def test_bootstrap_cria_admin_com_credencial_idempotente(
    usuarios_engine: AsyncEngine, database_url: str
) -> None:
    settings = _settings(database_url)

    uid1 = await bm.bootstrap_admin(settings, email="Admin@X.Z", nome="Admin", senha="SenhaForte1")
    # 2ª execução com nome E senha diferentes: idempotente → UPDATE (reset), não duplica.
    uid2 = await bm.bootstrap_admin(
        settings, email="admin@x.z", nome="Admin Renomeado", senha="OutraForte2"
    )

    assert uid1 == uid2  # reusa o id do e-mail existente (normalizado)
    async with usuarios_engine.connect() as conn:
        linhas = (
            await conn.execute(
                text("SELECT nome, administrador, ativo, setor FROM usuarios WHERE id = :id"),
                {"id": uid1},
            )
        ).all()
        cred = (
            await conn.execute(
                text("SELECT email, senha_hash FROM auth_credentials WHERE user_id = :id"),
                {"id": uid1},
            )
        ).all()

    assert len(linhas) == 1  # uma única linha (on_conflict_do_update)
    assert linhas[0].nome == "Admin Renomeado"
    assert linhas[0].administrador is True
    assert linhas[0].ativo is True
    assert linhas[0].setor == "studio"

    assert len(cred) == 1  # uma única credencial
    assert cred[0].email == "admin@x.z"  # e-mail normalizado (lower)
    # A senha foi RESETADA na 2ª execução e é verificável (argon2id).
    hasher = Argon2PasswordHasher()
    assert hasher.verificar("OutraForte2", cred[0].senha_hash)
    assert not hasher.verificar("SenhaForte1", cred[0].senha_hash)
