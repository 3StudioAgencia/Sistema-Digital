"""bootstrap_admin — guards e contrato de run()/main(). OFFLINE.

Cobre os ramos que não tocam o banco: a validação de senha (roda antes do engine)
e os exit codes/log estruturado de ``run``/``main`` (espelha test_keep_alive).
"""

import pytest
from src.domain.usuarios import SenhaFracaError
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


async def test_bootstrap_senha_fraca_levanta_sem_tocar_banco() -> None:
    # validar_senha roda ANTES de abrir o engine → falha offline, sem I/O.
    with pytest.raises(SenhaFracaError):
        await bm.bootstrap_admin(_settings(), email="a@b.c", nome="X", senha="curta1")


def test_run_sucesso_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _ok(settings: Settings, email: str, nome: str, senha: str) -> str:
        return "uid-123"

    monkeypatch.setattr(bm, "bootstrap_admin", _ok)
    assert bm.run(_settings(), email="a@b.c", nome="X", senha="SenhaForte1") == 0


def test_run_falha_exit_1_sem_vazar_segredo(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def _boom(settings: Settings, email: str, nome: str, senha: str) -> str:
        raise RuntimeError("algo deu errado")

    monkeypatch.setattr(bm, "bootstrap_admin", _boom)
    assert bm.run(_settings(), email="a@b.c", nome="X", senha="SenhaForte1") == 1
    saida = capsys.readouterr().out
    assert "postgres:postgres" not in saida  # nunca a connection string
    assert "SenhaForte1" not in saida  # a senha nunca vai ao log


def test_main_falha_ao_carregar_config_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> Settings:
        raise RuntimeError("env inválido")

    monkeypatch.setattr(bm, "get_settings", _boom)
    assert bm.main(["--email", "a@b.c", "--nome", "X", "--senha", "SenhaForte1"]) == 1


def test_main_sucesso_delega_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bm, "get_settings", lambda: _settings())
    monkeypatch.setattr(bm, "run", lambda settings, email, nome, senha: 0)
    assert bm.main(["--email", "a@b.c", "--nome", "X", "--senha", "SenhaForte1"]) == 0
