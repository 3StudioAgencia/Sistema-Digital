"""bootstrap_admin (W1-C04 / W1-A-018) — raiz de confiança do RBAC, @db.

O provisionamento do PRIMEIRO admin não tinha teste (cobertura 0%). Aqui o
provedor de identidade é dublado (FakeIdentityProvider) e o UPSERT corre contra
o Postgres real, provando: idempotência (repetir converge, não duplica), espelho
de claims no ``app_metadata`` e unban — sem nunca tocar o Supabase real.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from src.application.usuarios import montar_app_metadata
from src.domain.usuarios import Setor
from src.infrastructure.config import Settings
from src.tasks import bootstrap_admin as bm

from tests.conftest import FakeIdentityProvider

pytestmark = pytest.mark.db


class _FakeAdmin(FakeIdentityProvider):
    """FakeIdentityProvider + ``aclose`` (o bootstrap o chama no ``finally``)."""

    async def aclose(self) -> None:
        return None


def _settings(url: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=url,
        migrations_database_url=url,
        supabase_url="https://x.supabase.co",
        supabase_secret_key="sb_secret_dummy",
    )


async def test_bootstrap_upsert_idempotente_espelha_claims_e_desbane(
    usuarios_engine: AsyncEngine, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeAdmin()
    auth_id = fake.seed("admin@x.z")  # conta de auth pré-existente (dashboard)
    fake.users[auth_id]["banned"] = True  # estava banida — o bootstrap desfaz
    monkeypatch.setattr(bm, "SupabaseAdminIdentityProvider", lambda **kw: fake)
    settings = _settings(database_url)

    uid1 = await bm.bootstrap_admin(settings, email="admin@x.z", nome="Admin")
    # Segunda execução com NOME diferente: idempotente → UPDATE, não duplica.
    uid2 = await bm.bootstrap_admin(settings, email="admin@x.z", nome="Admin Renomeado")

    assert uid1 == auth_id
    assert uid2 == auth_id
    async with usuarios_engine.connect() as conn:
        linhas = (
            await conn.execute(
                text("SELECT nome, administrador, ativo, setor FROM usuarios WHERE id = :id"),
                {"id": auth_id},
            )
        ).all()
    assert len(linhas) == 1  # uma única linha (on_conflict_do_update)
    assert linhas[0].nome == "Admin Renomeado"  # o UPDATE aplicou
    assert linhas[0].administrador is True
    assert linhas[0].ativo is True
    assert linhas[0].setor == "studio"
    # Claims espelhadas no auth + unban (admin utilizável).
    assert fake.users[auth_id]["app_metadata"] == montar_app_metadata(
        Setor.STUDIO, administrador=True
    )
    assert fake.users[auth_id]["banned"] is False
    assert ("update_app_metadata", auth_id) in fake.calls
    assert ("set_banned", f"{auth_id}:False") in fake.calls


async def test_bootstrap_conta_auth_inexistente_levanta(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem conta de auth para o e-mail → erro claro apontando o dashboard; nada é
    escrito no domínio nem espelhado em claims."""
    fake = _FakeAdmin()  # vazio: find_user_by_email devolve None
    monkeypatch.setattr(bm, "SupabaseAdminIdentityProvider", lambda **kw: fake)
    settings = _settings(database_url)

    with pytest.raises(RuntimeError, match="conta de auth não encontrada"):
        await bm.bootstrap_admin(settings, email="ausente@x.z", nome="X")
    assert all(c[0] != "update_app_metadata" for c in fake.calls)
