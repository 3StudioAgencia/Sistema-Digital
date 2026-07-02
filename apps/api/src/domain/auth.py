"""Domínio da autenticação própria — refresh tokens opacos (migração Supabase->local).

Camada interna (CLAUDE.md §5.2): sem framework/ORM/IO. Gera e faz o hash dos
refresh tokens ROTATIVOS. O token CRU vai ao cliente (cookie httpOnly); o banco
guarda SÓ o SHA-256 (``auth_sessions.refresh_hash``) — um vazamento do banco não
revela tokens utilizáveis. ``secrets`` (CSPRNG) é o mesmo mecanismo do código de
prova (``domain/provas.py``).
"""

import hashlib
import secrets

# 32 bytes (256 bits) de entropia — token_urlsafe produz ~43 chars base64url.
_REFRESH_TOKEN_BYTES = 32


def gerar_refresh_token() -> str:
    """Refresh token opaco de alta entropia (nunca persistido em claro)."""
    return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """SHA-256 (hex) do refresh token — o que é comparado/persistido.

    SHA-256 (e não argon2) porque o token já é aleatório de 256 bits: não há
    ataque de dicionário a mitigar, e o lookup por hash precisa ser determinístico
    e barato (``auth_sessions.refresh_hash`` é UNIQUE/indexado).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = ["gerar_refresh_token", "hash_refresh_token"]
