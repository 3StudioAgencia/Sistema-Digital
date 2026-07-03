"""Adapter Firebird (Fatia 1) contra o ERP legado REAL — SOMENTE LEITURA (@firebird).

Skip quando ``FIREBIRD_TEST_DATABASE`` não está definido (CI/offline). Valida a
leitura ponta a ponta (conexão read-only + join + mapeamento) e o health — nunca
escreve. Config via env (não versiona caminho/senha da máquina):
    FIREBIRD_TEST_DATABASE  ex.: localhost:C:\\bancos\\STUDIOEART_2010.FDB
    FIREBIRD_TEST_USER      (default SYSDBA)
    FIREBIRD_TEST_PASSWORD  (default masterkey)
    FIREBIRD_TEST_CHARSET   (default WIN1252)
    FIREBIRD_TEST_CLIENT_LIBRARY  caminho da fbclient.dll (opcional)
"""

import os

import pytest
from src.adapters.outbound.firebird.requerimento_reader import FirebirdRequerimentoReader

pytestmark = pytest.mark.firebird


@pytest.fixture
def reader() -> FirebirdRequerimentoReader:
    database = os.environ.get("FIREBIRD_TEST_DATABASE")
    if not database:
        pytest.skip("FIREBIRD_TEST_DATABASE não definido — teste do ERP legado pulado")
    return FirebirdRequerimentoReader(
        database=database,
        user=os.environ.get("FIREBIRD_TEST_USER", "SYSDBA"),
        password=os.environ.get("FIREBIRD_TEST_PASSWORD", "masterkey"),
        charset=os.environ.get("FIREBIRD_TEST_CHARSET", "WIN1252"),
        client_library=os.environ.get("FIREBIRD_TEST_CLIENT_LIBRARY"),
    )


def test_health_ok(reader: FirebirdRequerimentoReader) -> None:
    assert reader.health() is True


def test_buscar_requerimento_conhecido(reader: FirebirdRequerimentoReader) -> None:
    r = reader.buscar(150288)
    assert r is not None
    assert r.cod_req_art == 150288
    assert r.cod_vend_fat == 10  # compõe o caminho da arte
    assert r.cod_cliente == 1058
    assert r.nome is not None and "QUEIJO" in r.nome
    assert r.nome_vendedor == "REGISLAINE PETRIM"  # acentos/charset WIN1252 ok
    assert r.nome_cliente == "LATICINIOS FLORIDA LTDA"
    assert r.anexo_imagem is not None and r.anexo_imagem.startswith("VERSAO_150288_V")


def test_buscar_inexistente_retorna_none(reader: FirebirdRequerimentoReader) -> None:
    assert reader.buscar(999999999) is None
