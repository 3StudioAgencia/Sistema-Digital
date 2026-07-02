"""Testes do domínio de auth — refresh tokens opacos. OFFLINE."""

from src.domain.auth import gerar_refresh_token, hash_refresh_token


def test_refresh_token_alta_entropia_e_unico() -> None:
    tokens = {gerar_refresh_token() for _ in range(100)}
    assert len(tokens) == 100  # CSPRNG: sem colisão em 100 amostras
    assert all(len(t) >= 40 for t in tokens)


def test_hash_refresh_token_deterministico_e_sha256() -> None:
    token = gerar_refresh_token()
    h1 = hash_refresh_token(token)
    h2 = hash_refresh_token(token)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 em hex
    assert h1 != token  # o hash nunca é o token cru


def test_hash_difere_por_token() -> None:
    assert hash_refresh_token("token-a") != hash_refresh_token("token-b")
