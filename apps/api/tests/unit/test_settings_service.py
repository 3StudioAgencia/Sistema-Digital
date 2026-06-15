"""Serviço de configurações (W2-C09) — merge default x sobrescrita, save, validação.

Roda offline com dublês de repositório/UoW (sem Postgres). O comportamento contra
o banco (RLS, imediatismo end-to-end) é coberto pelos testes @db.
"""

import datetime as dt
from typing import Any

import pytest
from src.application.ports.settings_repository import RegistroConfiguracao, SettingsRepositoryPort
from src.application.ports.unit_of_work import UnitOfWork
from src.application.settings import SettingsService
from src.domain.settings import CHAVE_DELAY, CHAVE_ETIQUETA, ConfiguracaoInvalidaError

_AGORA = dt.datetime(2026, 6, 15, 12, 0, tzinfo=dt.UTC)


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


class FakeSettingsRepository(SettingsRepositoryPort):
    def __init__(self) -> None:
        self.dados: dict[str, RegistroConfiguracao] = {}
        self.saves: list[tuple[str, Any, str | None]] = []

    async def carregar(self) -> list[RegistroConfiguracao]:
        return list(self.dados.values())

    async def obter(self, chave: str) -> RegistroConfiguracao | None:
        return self.dados.get(chave)

    async def salvar(
        self, chave: str, valor: Any, atualizado_por: str | None
    ) -> RegistroConfiguracao:
        self.saves.append((chave, valor, atualizado_por))
        registro = RegistroConfiguracao(
            chave=chave, valor=valor, atualizado_em=_AGORA, atualizado_por=atualizado_por
        )
        self.dados[chave] = registro
        return registro


def _service() -> tuple[SettingsService, FakeSettingsRepository, FakeUnitOfWork]:
    repo, uow = FakeSettingsRepository(), FakeUnitOfWork()
    return SettingsService(repo=repo, uow=uow), repo, uow


async def test_listar_sem_sobrescritas_devolve_defaults() -> None:
    service, _, _ = _service()
    configs = {c.chave: c for c in await service.listar()}
    assert set(configs) == {CHAVE_DELAY, CHAVE_ETIQUETA}
    delay = configs[CHAVE_DELAY]
    assert delay.valor == 48 and delay.default == 48
    assert delay.atualizado_em is None and delay.atualizado_por is None


async def test_listar_aplica_sobrescrita_sobre_o_default() -> None:
    service, repo, _ = _service()
    repo.dados[CHAVE_DELAY] = RegistroConfiguracao(
        chave=CHAVE_DELAY, valor=72, atualizado_em=_AGORA, atualizado_por="admin-1"
    )
    configs = {c.chave: c for c in await service.listar()}
    assert configs[CHAVE_DELAY].valor == 72  # efetivo = sobrescrita
    assert configs[CHAVE_DELAY].default == 48  # default preservado
    assert configs[CHAVE_DELAY].atualizado_por == "admin-1"
    assert configs[CHAVE_ETIQUETA].valor == configs[CHAVE_ETIQUETA].default  # sem sobrescrita


async def test_salvar_valido_persiste_e_commita() -> None:
    service, repo, uow = _service()
    resultado = await service.salvar(CHAVE_DELAY, 96, "admin-1")
    assert resultado.valor == 96
    assert repo.saves == [(CHAVE_DELAY, 96, "admin-1")]
    assert uow.commits == 1


async def test_salvar_delay_invalido_nao_toca_o_repo() -> None:
    service, repo, uow = _service()
    with pytest.raises(ConfiguracaoInvalidaError):
        await service.salvar(CHAVE_DELAY, 0, "admin-1")
    assert repo.saves == [] and uow.commits == 0


async def test_salvar_chave_desconhecida_e_rejeitado() -> None:
    service, repo, _ = _service()
    with pytest.raises(ConfiguracaoInvalidaError):
        await service.salvar("inexistente", 1, "admin-1")
    assert repo.saves == []


async def test_salvar_etiqueta_normaliza_o_objeto() -> None:
    service, repo, _ = _service()
    await service.salvar(
        CHAVE_ETIQUETA, {"modo": "personalizado", "largura": 100, "fonte": "times"}, "admin-1"
    )
    _, valor, _ = repo.saves[0]
    assert valor["modo"] == "personalizado"
    assert valor["largura"] == 100.0  # coagido a float
    assert valor["altura"] == 55.0  # campo ausente preenchido com o default


async def test_salvar_e_idempotente() -> None:
    service, _, uow = _service()
    a = await service.salvar(CHAVE_DELAY, 60, "admin-1")
    b = await service.salvar(CHAVE_DELAY, 60, "admin-1")
    assert a.valor == b.valor == 60
    assert uow.commits == 2  # cada PUT commita; o valor final é o mesmo (idempotente)


async def test_obter_config_etiqueta_reflete_a_sobrescrita() -> None:
    service, _, _ = _service()
    await service.salvar(CHAVE_ETIQUETA, {"modo": "personalizado", "largura": 120}, "admin-1")
    config = await service.obter_config_etiqueta()
    assert config.personalizado and config.largura == 120.0
