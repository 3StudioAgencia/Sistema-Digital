"""Verificação de JWT (W1-C03) — testes unitários do ``JwtVerifier``. OFFLINE.

ES256 é exercitado com uma chave EC P-256 gerada na hora + um JWKS dublê (sem
rede); HS256 com um segredo de teste. Cobre os caminhos felizes e a recusa de
expirado, audience errada, assinatura inválida, malformado, sub ausente,
algoritmo não suportado e a ausência de configuração (deny-all).
"""

import datetime as dt
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from src.adapters.inbound.http.auth import (
    AuthenticatedUser,
    InvalidToken,
    JwtVerifier,
    build_jwt_verifier,
)
from src.infrastructure.config import Settings

_LOCAL_PG = "postgresql://postgres:postgres@localhost:5432/x"

HS256_SECRET = "segredo-de-teste-nunca-em-producao"
AUDIENCE = "authenticated"
SUB = "11111111-1111-1111-1111-111111111111"
EMAIL = "vendedor@3studio.test"


def _claims(**overrides: Any) -> dict[str, Any]:
    now = dt.datetime.now(tz=dt.UTC)
    base: dict[str, Any] = {
        "sub": SUB,
        "email": EMAIL,
        "role": AUDIENCE,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }
    base.update(overrides)
    return base


class _FakeJwksClient:
    """Dublê do PyJWKClient: devolve sempre a chave pública dada (sem rede)."""

    def __init__(self, public_key: Any) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> Any:
        return SimpleNamespace(key=self._public_key)


@pytest.fixture
def ec_private_key() -> EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def es256_verifier(ec_private_key: EllipticCurvePrivateKey) -> JwtVerifier:
    """Verifier só-assimétrico: tem JWKS (chave pública), não tem segredo HS256."""
    return JwtVerifier(jwks_client=_FakeJwksClient(ec_private_key.public_key()))


def _es256(private_key: EllipticCurvePrivateKey, **overrides: Any) -> str:
    return jwt.encode(_claims(**overrides), private_key, algorithm="ES256")


# --- Caminhos felizes -------------------------------------------------------
def test_es256_token_valido(
    es256_verifier: JwtVerifier, ec_private_key: EllipticCurvePrivateKey
) -> None:
    user = es256_verifier.verify(_es256(ec_private_key))
    assert isinstance(user, AuthenticatedUser)
    assert user.sub == SUB
    assert user.email == EMAIL
    assert user.role == AUDIENCE
    assert user.claims["aud"] == AUDIENCE


def test_hs256_token_valido() -> None:
    verifier = JwtVerifier(hs256_secret=HS256_SECRET)
    token = jwt.encode(_claims(), HS256_SECRET, algorithm="HS256")
    user = verifier.verify(token)
    assert user.sub == SUB
    assert user.email == EMAIL


# --- Recusas ----------------------------------------------------------------
def test_es256_expirado(
    es256_verifier: JwtVerifier, ec_private_key: EllipticCurvePrivateKey
) -> None:
    past = dt.datetime.now(tz=dt.UTC) - dt.timedelta(hours=1)
    with pytest.raises(InvalidToken):
        es256_verifier.verify(_es256(ec_private_key, exp=past))


def test_hs256_expirado() -> None:
    verifier = JwtVerifier(hs256_secret=HS256_SECRET)
    past = dt.datetime.now(tz=dt.UTC) - dt.timedelta(seconds=1)
    token = jwt.encode(_claims(exp=past), HS256_SECRET, algorithm="HS256")
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_audience_incorreta(
    es256_verifier: JwtVerifier, ec_private_key: EllipticCurvePrivateKey
) -> None:
    with pytest.raises(InvalidToken):
        es256_verifier.verify(_es256(ec_private_key, aud="anon"))


def test_assinatura_invalida_hs256() -> None:
    verifier = JwtVerifier(hs256_secret=HS256_SECRET)
    token = jwt.encode(_claims(), "outro-segredo-diferente-porem-bem-longo", algorithm="HS256")
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_assinatura_invalida_es256(es256_verifier: JwtVerifier) -> None:
    # Token assinado por OUTRA chave; o verifier só tem a chave pública original.
    outra = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(InvalidToken):
        es256_verifier.verify(_es256(outra))


def test_token_malformado() -> None:
    verifier = JwtVerifier(hs256_secret=HS256_SECRET)
    with pytest.raises(InvalidToken):
        verifier.verify("isto-nao-e-um-jwt")


def test_sub_ausente() -> None:
    verifier = JwtVerifier(hs256_secret=HS256_SECRET)
    claims = _claims()
    del claims["sub"]
    token = jwt.encode(claims, HS256_SECRET, algorithm="HS256")
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_verifier_sem_configuracao_rejeita_tudo() -> None:
    # Default deny-all: sem JWKS e sem segredo, nenhum token passa.
    verifier = JwtVerifier()
    token = jwt.encode(_claims(), HS256_SECRET, algorithm="HS256")
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_hs256_recusado_quando_so_ha_jwks(es256_verifier: JwtVerifier) -> None:
    # Defesa contra downgrade/confusão de algoritmo: verifier só-assimétrico não
    # aceita HS256 (não há segredo configurado).
    token = jwt.encode(_claims(), HS256_SECRET, algorithm="HS256")
    with pytest.raises(InvalidToken):
        es256_verifier.verify(token)


def test_algoritmo_none_rejeitado() -> None:
    # JWT "unsecured" (alg=none) NUNCA é aceito — vetor clássico de bypass.
    verifier = JwtVerifier(hs256_secret=HS256_SECRET)
    token = jwt.encode(_claims(), None, algorithm="none")
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_es256_sem_jwks_rejeitado(ec_private_key: EllipticCurvePrivateKey) -> None:
    # Token ES256 chegando a um verifier sem JWKS configurado → recusa.
    verifier = JwtVerifier()
    with pytest.raises(InvalidToken):
        verifier.verify(_es256(ec_private_key))


def test_jwks_indisponivel_vira_invalid_token(ec_private_key: EllipticCurvePrivateKey) -> None:
    # Falha ao obter a chave do JWKS (rede/kid) NÃO pode vazar como 500:
    # normaliza para InvalidToken (→ 401 genérico no endpoint).
    class _BoomJwksClient:
        def get_signing_key_from_jwt(self, token: str) -> Any:
            raise RuntimeError("JWKS indisponível")

    verifier = JwtVerifier(jwks_client=_BoomJwksClient())
    with pytest.raises(InvalidToken):
        verifier.verify(_es256(ec_private_key))


def test_sub_nao_string_rejeitado() -> None:
    # sub presente (passa o require do decode) porém não-string → recusa no _identity.
    verifier = JwtVerifier(hs256_secret=HS256_SECRET)
    token = jwt.encode(_claims(sub=12345), HS256_SECRET, algorithm="HS256")
    with pytest.raises(InvalidToken):
        verifier.verify(token)


# --- Validação de issuer (iss) — W1-A-013 -----------------------------------
ISSUER = "https://proj.supabase.co/auth/v1"


def test_issuer_correto_aceito(ec_private_key: EllipticCurvePrivateKey) -> None:
    verifier = JwtVerifier(jwks_client=_FakeJwksClient(ec_private_key.public_key()), issuer=ISSUER)
    assert verifier.verify(_es256(ec_private_key, iss=ISSUER)).sub == SUB


def test_issuer_incorreto_rejeitado(ec_private_key: EllipticCurvePrivateKey) -> None:
    verifier = JwtVerifier(jwks_client=_FakeJwksClient(ec_private_key.public_key()), issuer=ISSUER)
    with pytest.raises(InvalidToken):
        verifier.verify(_es256(ec_private_key, iss="https://evil.supabase.co/auth/v1"))


def test_issuer_ausente_rejeitado_quando_exigido(
    ec_private_key: EllipticCurvePrivateKey,
) -> None:
    verifier = JwtVerifier(jwks_client=_FakeJwksClient(ec_private_key.public_key()), issuer=ISSUER)
    with pytest.raises(InvalidToken):
        verifier.verify(_es256(ec_private_key))  # sem claim iss


def test_hs256_issuer_validado() -> None:
    """Caminho que de fato importa (W1-A-013): segredo HS256 partilhável entre
    projetos — o ``iss`` distingue o emissor."""
    verifier = JwtVerifier(hs256_secret=HS256_SECRET, issuer=ISSUER)
    bom = jwt.encode(_claims(iss=ISSUER), HS256_SECRET, algorithm="HS256")
    assert verifier.verify(bom).sub == SUB
    ruim = jwt.encode(
        _claims(iss="https://outro.supabase.co/auth/v1"), HS256_SECRET, algorithm="HS256"
    )
    with pytest.raises(InvalidToken):
        verifier.verify(ruim)


def test_issuer_nao_exigido_quando_nao_configurado(
    ec_private_key: EllipticCurvePrivateKey,
) -> None:
    # Back-compat: verifier sem issuer (default) aceita token sem iss.
    verifier = JwtVerifier(jwks_client=_FakeJwksClient(ec_private_key.public_key()))
    assert verifier.verify(_es256(ec_private_key)).sub == SUB


# --- Fábrica a partir do Settings (composition root) ------------------------
def test_build_verifier_deriva_jwks_e_segredo() -> None:
    settings = Settings(
        _env_file=None,
        database_url=_LOCAL_PG,
        migrations_database_url=_LOCAL_PG,
        supabase_url="https://proj.supabase.co/",
        supabase_jwt_secret="hs-secret",
    )
    assert settings.effective_jwks_url == ("https://proj.supabase.co/auth/v1/.well-known/jwks.json")
    assert settings.effective_issuer == "https://proj.supabase.co/auth/v1"
    verifier = build_jwt_verifier(settings)
    assert verifier._jwks_client is not None
    assert verifier._hs256_secret == "hs-secret"
    # Derivado da MESMA base do JWKS — sem divergência (W1-A-013).
    assert verifier._issuer == "https://proj.supabase.co/auth/v1"


def test_build_verifier_sem_supabase_e_denyall() -> None:
    settings = Settings(
        _env_file=None,
        database_url=_LOCAL_PG,
        migrations_database_url=_LOCAL_PG,
    )
    assert settings.effective_jwks_url is None
    assert settings.effective_issuer is None
    verifier = build_jwt_verifier(settings)
    assert verifier._jwks_client is None
    assert verifier._hs256_secret is None
    assert verifier._issuer is None
