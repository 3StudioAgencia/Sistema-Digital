"""Verificação de JWT do Supabase Auth (camada inbound HTTP) — W1-C03.

Princípios (CLAUDE.md §11, DAT §1.3, prompt W1-C03 §3 / DP-2):
- O backend NUNCA emite tokens — apenas VERIFICA a assinatura dos JWT que o
  Supabase Auth emite (PyJWT só verifica).
- Verificação robusta ao esquema real do projeto: o default atual do Supabase é
  ``ES256`` (assimétrico, chaves publicadas no JWKS do projeto); mantemos
  ``HS256`` (segredo legado) como *fallback* para resiliência/rotação (ADR-018).
  O algoritmo é decidido pelo header do token e validado contra uma lista
  explícita — nunca ``none``, sem confusão de algoritmo (chave pública só é
  usada para algoritmos assimétricos; o segredo só para HS256).
- Validamos assinatura, ``aud="authenticated"`` e expiração. Qualquer falha de
  verificação vira **401 genérico**, sem revelar QUAL parte falhou
  (anti-enumeração — CLAUDE.md §11); o motivo fica no log estruturado (apenas o
  tipo da exceção, nunca o token).

A verificação é síncrona (CPU + busca do JWKS via urllib, cacheada pelo
``PyJWKClient``); o endpoint a executa em *threadpool* para não bloquear o event
loop — mesmo padrão da ``StoragePort`` (boto3) no readiness.
"""

import logging
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel

from src.infrastructure.config import Settings

logger = logging.getLogger("rastreio.http.auth")

# Supabase emite o access token com aud="authenticated" para sessões logadas.
SUPABASE_AUDIENCE = "authenticated"
# Algoritmos assimétricos aceitos via JWKS. ES256 é o default atual do Supabase;
# RS256 entra por robustez (projetos/rotações antigas). NUNCA "none".
_ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")
_SYMMETRIC_ALGORITHM = "HS256"
# Claims exigidas: sem elas o token não é utilizável como prova de identidade.
_REQUIRED_CLAIMS = ("exp", "aud", "sub")


class InvalidToken(Exception):
    """Token ausente/inválido/expirado/com audience errada. Mapeado a 401."""


class AuthenticatedUser(BaseModel):
    """Identidade verificada extraída do JWT.

    Não há ida ao banco nem checagem de perfil aqui — isso é C04 (usuários) e
    C05 (RBAC). ``claims`` carrega o payload verificado para essas waves
    propagarem o escopo à RLS (ADR-008) sem reverificar.
    """

    sub: str
    email: str | None = None
    role: str | None = None
    claims: dict[str, Any]


class JwtVerifier:
    """Verifica JWT do Supabase: ES256/RS256 via JWKS (cache) + HS256 (fallback).

    Stateless quanto à sessão; o ``PyJWKClient`` mantém apenas um cache de chaves
    públicas (não há estado de usuário). Sem JWKS e sem segredo configurados, é
    um *null object* que rejeita qualquer token — default seguro nos testes que
    não exercitam auth.
    """

    def __init__(
        self,
        *,
        jwks_client: PyJWKClient | None = None,
        hs256_secret: str | None = None,
        audience: str = SUPABASE_AUDIENCE,
        issuer: str | None = None,
    ) -> None:
        self._jwks_client = jwks_client
        self._hs256_secret = hs256_secret
        self._audience = audience
        # Validação de ``iss`` só quando configurada (derivada de SUPABASE_URL):
        # protege o fallback HS256 contra um segredo compartilhado entre projetos
        # (W1-A-013). Mantida opcional para não quebrar verifiers de teste/sem URL.
        self._issuer = issuer

    def verify(self, token: str) -> AuthenticatedUser:
        """Verifica o token e devolve a identidade, ou levanta ``InvalidToken``."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise self._reject(exc) from exc

        alg = header.get("alg")
        try:
            if alg in _ASYMMETRIC_ALGORITHMS:
                claims = self._decode_asymmetric(token)
            elif alg == _SYMMETRIC_ALGORITHM:
                claims = self._decode_symmetric(token)
            else:
                raise InvalidToken(f"unsupported alg: {alg!r}")
        except jwt.InvalidTokenError as exc:
            raise self._reject(exc) from exc
        except InvalidToken as exc:
            raise self._reject(exc) from exc
        except Exception as exc:
            # PyJWKClient pode levantar erros próprios (kid ausente, JWKS
            # inacessível). Normalizamos tudo a 401 + log do tipo da exceção.
            raise self._reject(exc) from exc

        return self._identity(claims)

    def _decode_asymmetric(self, token: str) -> dict[str, Any]:
        if self._jwks_client is None:
            raise InvalidToken("asymmetric verification unavailable (no JWKS)")
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        return self._decode(token, signing_key.key, list(_ASYMMETRIC_ALGORITHMS))

    def _decode_symmetric(self, token: str) -> dict[str, Any]:
        if self._hs256_secret is None:
            raise InvalidToken("symmetric verification unavailable (no secret)")
        return self._decode(token, self._hs256_secret, [_SYMMETRIC_ALGORITHM])

    def _decode(self, token: str, key: Any, algorithms: list[str]) -> dict[str, Any]:
        # Exige e valida ``iss`` apenas quando o emissor é conhecido (W1-A-013);
        # com ``issuer=None``/``verify_iss=False`` o comportamento é o de antes.
        valida_iss = self._issuer is not None
        require = [*_REQUIRED_CLAIMS, "iss"] if valida_iss else list(_REQUIRED_CLAIMS)
        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=self._audience,
            issuer=self._issuer,
            options={
                "require": require,
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": valida_iss,
            },
        )

    def _identity(self, claims: dict[str, Any]) -> AuthenticatedUser:
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise self._reject(InvalidToken("missing or non-string sub claim"))
        email = claims.get("email")
        role = claims.get("role")
        return AuthenticatedUser(
            sub=sub,
            email=email if isinstance(email, str) else None,
            role=role if isinstance(role, str) else None,
            claims=claims,
        )

    @staticmethod
    def _reject(exc: BaseException) -> InvalidToken:
        """Loga a falha (só o tipo — nunca o token/segredo) e devolve InvalidToken."""
        logger.warning(
            "falha na verificação de JWT",
            extra={"event": "jwt_verification_failed", "error_type": type(exc).__name__},
        )
        return exc if isinstance(exc, InvalidToken) else InvalidToken(type(exc).__name__)


def build_jwt_verifier(settings: Settings) -> JwtVerifier:
    """Constrói o verifier a partir do ambiente (chamado no composition root).

    JWKS explícito (``SUPABASE_JWKS_URL``) ou derivado de ``SUPABASE_URL``;
    ``SUPABASE_JWT_SECRET`` opcional habilita o fallback HS256.
    """
    jwks_url = settings.effective_jwks_url
    # timeout curto: sob outage do Supabase, a busca do JWKS não pode segurar
    # threads do pool por 30s (default do urllib) — falha rápido em 401.
    jwks_client = PyJWKClient(jwks_url, timeout=5) if jwks_url else None
    secret = (
        settings.supabase_jwt_secret.get_secret_value()
        if settings.supabase_jwt_secret is not None
        else None
    )
    return JwtVerifier(
        jwks_client=jwks_client,
        hs256_secret=secret,
        issuer=settings.effective_issuer,
    )


# ---------------------------------------------------------------------------
# Dependência FastAPI + endpoint de prova
# ---------------------------------------------------------------------------
# auto_error=False: cabeçalho ausente/ mal-formado devolve None, e NÓS levantamos
# o 401 genérico (o default do FastAPI seria 403, e revelaria o esquema esperado).
_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedUser:
    """Dependência: exige Bearer JWT válido; devolve a identidade verificada."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    verifier: JwtVerifier = request.app.state.jwt_verifier
    try:
        return await run_in_threadpool(verifier.verify, credentials.credentials)
    except InvalidToken as exc:
        raise _unauthorized() from exc


class MeResponse(BaseModel):
    """Identidade verificada exposta pelo /auth/me (visão enxuta, sem claims crus)."""

    sub: str
    email: str | None = None
    role: str | None = None


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=MeResponse)
async def me(user: AuthenticatedUser = Depends(get_current_user)) -> MeResponse:
    """Prova demonstrável de que o caminho de verificação de JWT funciona.

    Exige um Bearer válido (ES256 via JWKS ou HS256) e devolve a identidade
    verificada. NÃO consulta o banco nem checa perfil/RBAC — isso é C04/C05.
    """
    return MeResponse(sub=user.sub, email=user.email, role=user.role)


__all__ = [
    "AuthenticatedUser",
    "InvalidToken",
    "JwtVerifier",
    "MeResponse",
    "build_jwt_verifier",
    "get_current_user",
    "router",
]
