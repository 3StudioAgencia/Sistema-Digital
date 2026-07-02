"""Carregamento das chaves ES256 (EC P-256) do JWT próprio.

As chaves vivem no ambiente em BASE64 do PEM (linha única — evita a fragilidade
de PEM multilinha em ``.env``). Segredos SÓ via ambiente (CLAUDE.md §9): a chave
privada é server-only; a pública pode ser distribuída (o proxy do Next a usa na
Fase 3 para verificar o cookie de sessão localmente).
"""

import base64

from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePrivateKey,
    EllipticCurvePublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)


def _pem_de_base64(valor_b64: str) -> bytes:
    return base64.b64decode(valor_b64.encode("ascii"))


def carregar_chave_privada_ec(valor_b64: str) -> EllipticCurvePrivateKey:
    """Chave privada EC a partir do base64 do PEM (``AUTH_JWT_PRIVATE_KEY``)."""
    chave = load_pem_private_key(_pem_de_base64(valor_b64), password=None)
    if not isinstance(chave, EllipticCurvePrivateKey):
        raise ValueError("AUTH_JWT_PRIVATE_KEY não é uma chave EC (P-256/ES256).")
    return chave


def carregar_chave_publica_ec(valor_b64: str) -> EllipticCurvePublicKey:
    """Chave pública EC a partir do base64 do PEM (``AUTH_JWT_PUBLIC_KEY``)."""
    chave = load_pem_public_key(_pem_de_base64(valor_b64))
    if not isinstance(chave, EllipticCurvePublicKey):
        raise ValueError("AUTH_JWT_PUBLIC_KEY não é uma chave EC (P-256/ES256).")
    return chave


__all__ = ["carregar_chave_privada_ec", "carregar_chave_publica_ec"]
