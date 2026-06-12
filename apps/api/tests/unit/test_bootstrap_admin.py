"""bootstrap_admin (W1-A-018) — guards e contrato de run()/main(). OFFLINE.

Cobre os ramos que não tocam o banco: o guard de configuração ausente, e os
exit codes/log estruturado de ``run``/``main`` (espelha tests/unit/test_keep_alive).
"""

import pytest
from src.infrastructure.config import Settings
from src.tasks import bootstrap_admin as bm

_PG = "postgresql://postgres:postgres@localhost:5432/x"


def _settings(**extra: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "database_url": _PG,
        "migrations_database_url": _PG,
    }
    base.update(extra)
    return Settings(**base)  # type: ignore[arg-type]


async def test_bootstrap_sem_secret_levanta_sem_tocar_provedor() -> None:
    # supabase_url presente, secret ausente → guard antes de criar engine/provedor.
    settings = _settings(supabase_url="https://x.supabase.co")
    with pytest.raises(RuntimeError, match="SUPABASE_URL e SUPABASE_SECRET_KEY"):
        await bm.bootstrap_admin(settings, email="a@b.c", nome="X")


def test_run_sucesso_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _ok(settings: Settings, email: str, nome: str) -> str:
        return "uid-123"

    monkeypatch.setattr(bm, "bootstrap_admin", _ok)
    assert bm.run(_settings(), email="a@b.c", nome="X") == 0


def test_run_falha_exit_1_com_detalhe_seguro(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def _boom(settings: Settings, email: str, nome: str) -> str:
        raise RuntimeError("conta de auth não encontrada")

    monkeypatch.setattr(bm, "bootstrap_admin", _boom)
    assert bm.run(_settings(), email="a@b.c", nome="X") == 1
    # O log carrega a mensagem segura, nunca a connection string/segredo.
    saida = capsys.readouterr().out
    assert "postgres:postgres" not in saida
    assert "sb_secret" not in saida


def test_main_falha_ao_carregar_config_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> Settings:
        raise RuntimeError("env inválido")

    monkeypatch.setattr(bm, "get_settings", _boom)
    assert bm.main(["--email", "a@b.c", "--nome", "X"]) == 1


def test_main_sucesso_delega_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bm, "get_settings", lambda: _settings())
    monkeypatch.setattr(bm, "run", lambda settings, email, nome: 0)
    assert bm.main(["--email", "a@b.c", "--nome", "X"]) == 0
