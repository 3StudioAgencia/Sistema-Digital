"""Fonte da arte (Fatia 2) contra o servidor de arquivos REAL — SOMENTE LEITURA (@share).

Skip quando ``ARTE_SHARE_TEST_BASE`` não está definido (CI/offline). Lê a imagem do
requerimento de exemplo (150288) e valida seleção/health — nunca escreve. Config:
    ARTE_SHARE_TEST_BASE  ex.: \\\\172.16.0.6\\Artes\\STUDIO_TRANSICAO
"""

import os

import pytest
from src.adapters.outbound.arte_fonte.filesystem_arte_fonte import SistemaDeArquivosArteFonte

pytestmark = pytest.mark.share

FAT, CLI, REQ = 10, 1058, 150288


@pytest.fixture
def fonte() -> SistemaDeArquivosArteFonte:
    base = os.environ.get("ARTE_SHARE_TEST_BASE")
    if not base:
        pytest.skip("ARTE_SHARE_TEST_BASE não definido — teste do servidor de arquivos pulado")
    return SistemaDeArquivosArteFonte(base, 50 * 1024 * 1024)


def test_health_ok(fonte: SistemaDeArquivosArteFonte) -> None:
    assert fonte.health() is True


def test_le_a_versao_apontada_pelo_anexo(fonte: SistemaDeArquivosArteFonte) -> None:
    arte = fonte.obter_arte(FAT, CLI, REQ, "VERSAO_150288_V3.jpg")
    assert arte.nome_arquivo == "VERSAO_150288_V3.jpg"
    assert arte.content_type == "image/jpeg"
    assert arte.conteudo.startswith(b"\xff\xd8\xff")  # magic bytes JPEG
    assert len(arte.conteudo) > 1000


def test_fallback_maior_versao(fonte: SistemaDeArquivosArteFonte) -> None:
    arte = fonte.obter_arte(FAT, CLI, REQ, None)
    assert arte.nome_arquivo.startswith("VERSAO_150288_V")
    assert arte.content_type in ("image/jpeg", "image/png")
