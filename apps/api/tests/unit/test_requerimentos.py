"""Fatia 1 (leitura do ERP legado): value object, config e mapeamento — offline.

Nada aqui toca o Firebird real: exercita as funções PURAS de normalização/mapeamento,
a validação de configuração (tudo-ou-nada) e o stand-in inerte. O adapter real é
coberto em ``tests/integration/test_firebird_reader.py`` (@firebird).
"""

import pytest
from pydantic import ValidationError
from src.adapters.outbound.firebird.requerimento_reader import (
    FirebirdRequerimentoReader,
    _mapear,
    _texto,
)
from src.adapters.outbound.firebird.unconfigured import UnconfiguredRequerimentoReader
from src.application.ports.requerimentos import RequerimentoReaderError
from src.domain.requerimentos import RequerimentoArte
from src.infrastructure.config import Settings

_PG = "postgresql+asyncpg://u:p@localhost:5432/x"


def _settings(**over: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "app_env": "test",
        "database_url": _PG,
        "migrations_database_url": _PG,
    }
    base.update(over)
    return Settings(**base)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [(None, None), ("  ABC  ", "ABC"), ("   ", None), ("", None), (10, "10")],
)
def test_texto_normaliza(entrada: object, esperado: str | None) -> None:
    assert _texto(entrada) == esperado


def test_mapear_linha_completa() -> None:
    # Ordem = _SQL_BUSCAR: req, prodart, cod_vende, nomven, cod_vend_fat, cod_clien, cliente, anexo
    row = (
        150288,
        "QUEIJO MUSSARELA",
        10,
        "REGISLAINE PETRIM",
        10,
        1058,
        "LATICINIOS FLORIDA LTDA",
        "VERSAO_150288_V3.jpg",
    )
    assert _mapear(row) == RequerimentoArte(
        cod_req_art=150288,
        nome="QUEIJO MUSSARELA",
        cod_cliente=1058,
        nome_cliente="LATICINIOS FLORIDA LTDA",
        cod_vendedor=10,
        nome_vendedor="REGISLAINE PETRIM",
        cod_vend_fat=10,
        anexo_imagem="VERSAO_150288_V3.jpg",
    )


def test_mapear_nulos_do_erp_viram_none() -> None:
    row = (1, None, 5, None, None, 9, None, None)
    r = _mapear(row)
    assert (r.nome, r.nome_vendedor, r.cod_vend_fat, r.nome_cliente, r.anexo_imagem) == (
        None,
        None,
        None,
        None,
        None,
    )
    assert (r.cod_req_art, r.cod_vendedor, r.cod_cliente) == (1, 5, 9)


def test_firebird_nao_configurado_por_padrao() -> None:
    assert _settings().firebird_configured is False


def test_firebird_parcial_falha_no_boot() -> None:
    with pytest.raises(ValidationError):
        _settings(firebird_database="localhost:C:/db.fdb")


def test_firebird_completo_configura_com_charset_padrao() -> None:
    s = _settings(
        firebird_database="localhost:C:/db.fdb",
        firebird_user="SYSDBA",
        firebird_password="masterkey",
    )
    assert s.firebird_configured is True
    assert s.firebird_charset == "WIN1252"


def test_from_settings_constroi_reader() -> None:
    s = _settings(
        firebird_database="localhost:C:/db.fdb",
        firebird_user="SYSDBA",
        firebird_password="masterkey",
        firebird_client_library="C:/fb/fbclient.dll",
    )
    reader = FirebirdRequerimentoReader.from_settings(s)
    assert reader._database == "localhost:C:/db.fdb"
    assert reader._password == "masterkey"  # get_secret_value resolvido
    assert reader._client_library == "C:/fb/fbclient.dll"


def test_from_settings_sem_config_levanta() -> None:
    with pytest.raises(RequerimentoReaderError):
        FirebirdRequerimentoReader.from_settings(_settings())


def test_unconfigured_health_false() -> None:
    assert UnconfiguredRequerimentoReader().health() is False


def test_unconfigured_buscar_levanta() -> None:
    with pytest.raises(RequerimentoReaderError):
        UnconfiguredRequerimentoReader().buscar(150288)
