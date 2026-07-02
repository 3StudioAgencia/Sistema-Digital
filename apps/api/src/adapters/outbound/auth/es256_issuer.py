"""Adapter emissor de access token — JWT ES256 (autenticação própria).

Emite o token com o CONTRATO DE CLAIMS que a RLS e os gates dependem (CLAUDE.md
§5.4). Preservar as chaves de topo VERBATIM é crítico:
- ``sub`` e ``user_id`` = UUID do usuário — a RLS de ``provas`` casa por
  ``user_id`` (``app_current_user_id()``), NÃO por ``sub``; esquecer ``user_id``
  faz o vendedor não enxergar as próprias provas (fail-closed silencioso);
- ``aud="authenticated"`` (o verifier valida) e ``role="authenticated"``;
- ``setor``/``administrador`` (lidos por ``app_setor()``/``app_is_admin()`` e
  por ``perfilDeClaims`` no front) — ``setor`` em lowercase (= ``setor_enum``),
  ``administrador`` como boolean JSON (não string).
"""

import datetime as dt

import jwt
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

from src.application.ports.tokens import TokenIssuerPort

_ALGORITHM = "ES256"
_AUDIENCE = "authenticated"
_ROLE = "authenticated"


class Es256TokenIssuer(TokenIssuerPort):
    def __init__(
        self,
        *,
        private_key: EllipticCurvePrivateKey,
        issuer: str,
        access_ttl_seconds: int,
    ) -> None:
        self._key = private_key
        self._issuer = issuer
        self._ttl = access_ttl_seconds

    def emitir_access(
        self, *, sub: str, email: str | None, setor: str, administrador: bool
    ) -> str:
        agora = dt.datetime.now(tz=dt.UTC)
        claims: dict[str, object] = {
            "sub": sub,
            # user_id = sub — a RLS (app_current_user_id) lê user_id, não sub.
            "user_id": sub,
            "aud": _AUDIENCE,
            "role": _ROLE,
            "setor": setor,
            "administrador": administrador,
            "iss": self._issuer,
            "iat": agora,
            "exp": agora + dt.timedelta(seconds=self._ttl),
        }
        if email is not None:
            claims["email"] = email
        return jwt.encode(claims, self._key, algorithm=_ALGORITHM)


__all__ = ["Es256TokenIssuer"]
