"""Fatia 2 — fonte da arte (servidor de arquivos): seleção e validação (offline).

Monta uma árvore de diretórios temporária imitando o share
(``<base>/<fat>/<clien>/<req>/VERSAO/VERSAO_<req>_V{n}.jpg``) e exercita a lógica
de escolha (ANEXO_IMAGEM → maior versão → mtime) e os dois modos de falha.
"""

from pathlib import Path

import pytest
from src.adapters.outbound.arte_fonte.filesystem_arte_fonte import (
    SistemaDeArquivosArteFonte,
    _versao_de,
)
from src.adapters.outbound.arte_fonte.unconfigured import UnconfiguredArteFonte
from src.application.ports.arte_fonte import ArteFonteError
from src.domain.requerimentos import ArteNaoDisponivelError

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
FAT, CLI, REQ = 10, 1058, 150288


def _versao_dir(base: Path) -> Path:
    d = base / str(FAT) / str(CLI) / str(REQ) / "VERSAO"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fonte(base: Path, teto_mb: int = 50) -> SistemaDeArquivosArteFonte:
    return SistemaDeArquivosArteFonte(str(base), teto_mb * 1024 * 1024)


def test_versao_de_extrai_numero() -> None:
    assert _versao_de("VERSAO_150288_V3.jpg") == 3
    assert _versao_de("VERSAO_150288_V12.png") == 12
    assert _versao_de("sem_versao.jpg") == -1


def test_prefere_o_arquivo_apontado_por_anexo_imagem(tmp_path: Path) -> None:
    versao = _versao_dir(tmp_path)
    (versao / "VERSAO_150288_V1.jpg").write_bytes(JPEG)
    (versao / "VERSAO_150288_V2.jpg").write_bytes(JPEG)
    (versao / "VERSAO_150288_V3.jpg").write_bytes(JPEG)

    arte = _fonte(tmp_path).obter_arte(FAT, CLI, REQ, "VERSAO_150288_V2.jpg")

    assert arte.nome_arquivo == "VERSAO_150288_V2.jpg"
    assert arte.content_type == "image/jpeg"
    assert arte.conteudo == JPEG


def test_fallback_maior_versao_quando_anexo_ausente(tmp_path: Path) -> None:
    versao = _versao_dir(tmp_path)
    (versao / "VERSAO_150288_V1.jpg").write_bytes(JPEG)
    (versao / "VERSAO_150288_V3.jpg").write_bytes(JPEG)
    (versao / "VERSAO_150288_V2.jpg").write_bytes(JPEG)

    arte = _fonte(tmp_path).obter_arte(FAT, CLI, REQ, None)

    assert arte.nome_arquivo == "VERSAO_150288_V3.jpg"  # maior _V{n}


def test_fallback_quando_anexo_nao_existe_no_disco(tmp_path: Path) -> None:
    versao = _versao_dir(tmp_path)
    (versao / "VERSAO_150288_V5.png").write_bytes(PNG)

    arte = _fonte(tmp_path).obter_arte(FAT, CLI, REQ, "arquivo_que_sumiu_V9.jpg")

    assert arte.nome_arquivo == "VERSAO_150288_V5.png"
    assert arte.content_type == "image/png"


def test_ignora_subpasta_anexo_e_arquivos_nao_imagem(tmp_path: Path) -> None:
    versao = _versao_dir(tmp_path)
    (versao / "VERSAO_150288_V1.jpg").write_bytes(JPEG)
    (versao / "notas.txt").write_text("não é imagem")

    arte = _fonte(tmp_path).obter_arte(FAT, CLI, REQ, None)
    assert arte.nome_arquivo == "VERSAO_150288_V1.jpg"


def test_sem_pasta_versao_levanta_arte_indisponivel(tmp_path: Path) -> None:
    # requerimento existe na árvore, mas sem subpasta VERSAO
    (tmp_path / str(FAT) / str(CLI) / str(REQ)).mkdir(parents=True)
    with pytest.raises(ArteNaoDisponivelError):
        _fonte(tmp_path).obter_arte(FAT, CLI, REQ, None)


def test_versao_vazia_levanta_arte_indisponivel(tmp_path: Path) -> None:
    _versao_dir(tmp_path)  # cria VERSAO vazia
    with pytest.raises(ArteNaoDisponivelError):
        _fonte(tmp_path).obter_arte(FAT, CLI, REQ, None)


def test_conteudo_nao_e_imagem_valida_levanta_indisponivel(tmp_path: Path) -> None:
    versao = _versao_dir(tmp_path)
    (versao / "VERSAO_150288_V1.jpg").write_bytes(b"isto nao e um jpeg")
    with pytest.raises(ArteNaoDisponivelError):
        _fonte(tmp_path).obter_arte(FAT, CLI, REQ, None)


def test_imagem_acima_do_teto_levanta_indisponivel(tmp_path: Path) -> None:
    versao = _versao_dir(tmp_path)
    (versao / "VERSAO_150288_V1.jpg").write_bytes(JPEG + b"\x00" * (2 * 1024 * 1024))
    with pytest.raises(ArteNaoDisponivelError):
        _fonte(tmp_path, teto_mb=1).obter_arte(FAT, CLI, REQ, None)


def test_health_true_quando_base_existe(tmp_path: Path) -> None:
    assert _fonte(tmp_path).health() is True


def test_health_false_quando_base_inexistente(tmp_path: Path) -> None:
    # Caminho LOCAL inexistente (evita timeout de SMB de um host UNC morto)
    fonte = SistemaDeArquivosArteFonte(str(tmp_path / "nao-existe"), 50 * 1024 * 1024)
    assert fonte.health() is False


def test_unconfigured_health_false_e_leitura_levanta() -> None:
    fonte = UnconfiguredArteFonte()
    assert fonte.health() is False
    with pytest.raises(ArteFonteError):
        fonte.obter_arte(FAT, CLI, REQ, None)
