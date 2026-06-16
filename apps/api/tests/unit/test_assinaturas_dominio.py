"""Domínio da assinatura digital (W3-C12) — ``validar_assinatura`` (RN-003)."""

import pytest
from src.domain.assinaturas import (
    ASSINATURA_TAMANHO_MAXIMO,
    AssinaturaInvalidaError,
    validar_assinatura,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff" + b"\x00" * 16


def test_png_valido_devolve_content_type() -> None:
    assert validar_assinatura(PNG) == "image/png"


def test_jpeg_valido_aceito_por_robustez() -> None:
    assert validar_assinatura(JPEG) == "image/jpeg"


def test_vazia_e_invalida() -> None:
    with pytest.raises(AssinaturaInvalidaError):
        validar_assinatura(b"")


def test_conteudo_nao_imagem_e_invalido() -> None:
    with pytest.raises(AssinaturaInvalidaError):
        validar_assinatura(b"isto nao e uma imagem")


def test_acima_do_teto_e_invalida() -> None:
    grande = PNG + b"\x00" * (ASSINATURA_TAMANHO_MAXIMO + 1)
    with pytest.raises(AssinaturaInvalidaError):
        validar_assinatura(grande)
