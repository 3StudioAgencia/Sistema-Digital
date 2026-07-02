"""Emissor de access token ES256 — TESTE-GUARDA DO CONTRATO DE CLAIMS. OFFLINE.

Protege contra o risco #1 da migração: se o token perder/renomear as chaves
``user_id``/``setor``/``administrador`` (ou trocar tipos), a RLS degrada em
SILÊNCIO (vendedor não vê as próprias provas; admin barrado) — sem erro. Aqui
travamos o formato exato e a compatibilidade com o verifier próprio.
"""

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from src.adapters.inbound.http.auth import AUTH_AUDIENCE, JwtVerifier
from src.adapters.outbound.auth.es256_issuer import Es256TokenIssuer

SUB = "11111111-1111-1111-1111-111111111111"
ISSUER = "rastreio-api"


def _issuer(private_key: ec.EllipticCurvePrivateKey) -> Es256TokenIssuer:
    return Es256TokenIssuer(private_key=private_key, issuer=ISSUER, access_ttl_seconds=1800)


def test_claims_contrato_verbatim() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    token = _issuer(key).emitir_access(
        sub=SUB, email="v@x.test", setor="vendedor", administrador=False
    )
    claims = jwt.decode(token, key.public_key(), algorithms=["ES256"], audience=AUTH_AUDIENCE)
    assert claims["sub"] == SUB
    assert claims["user_id"] == SUB  # user_id = sub — a RLS casa por user_id!
    assert claims["aud"] == "authenticated"
    assert claims["role"] == "authenticated"
    assert claims["setor"] == "vendedor"
    assert claims["administrador"] is False
    assert claims["iss"] == ISSUER
    assert claims["email"] == "v@x.test"
    assert "exp" in claims and "iat" in claims


def test_administrador_true_e_boolean_json() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    token = _issuer(key).emitir_access(sub=SUB, email=None, setor="studio", administrador=True)
    claims = jwt.decode(token, key.public_key(), algorithms=["ES256"], audience=AUTH_AUDIENCE)
    # boolean JSON, não string "true" (senão app_is_admin()/perfilDeClaims quebram).
    assert claims["administrador"] is True
    assert "email" not in claims  # email None é omitido do token


def test_token_emitido_passa_no_verifier_proprio() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    token = _issuer(key).emitir_access(sub=SUB, email=None, setor="motorista", administrador=False)
    verifier = JwtVerifier(public_key=key.public_key(), issuer=ISSUER)
    user = verifier.verify(token)
    assert user.sub == SUB
    assert user.claims["user_id"] == SUB
    assert user.claims["setor"] == "motorista"
