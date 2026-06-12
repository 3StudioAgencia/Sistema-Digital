"""Adapter concreto da Admin API do Supabase Auth (GoTrue) — W1-C04 / ADR-025.

ÚNICO lugar do sistema que toca a chave secreta (``SUPABASE_SECRET_KEY``,
formato ``sb_secret_...`` ou a ``service_role`` legada). A chave:
- vive SOMENTE no ambiente do backend (Railway) — nunca em ``NEXT_PUBLIC_*``;
- nunca é logada (logs registram apenas status HTTP e ``error_code``);
- dá BYPASSRLS via PostgREST — por isso toda operação passa por aqui, com
  autorização verificada ANTES na borda HTTP (guard de admin — DP-5).

Endpoints GoTrue usados (REST estável):
- ``POST   /auth/v1/admin/users``                — criar (email_confirm=true)
- ``DELETE /auth/v1/admin/users/{id}``           — remover (compensação)
- ``PUT    /auth/v1/admin/users/{id}``           — ban_duration / app_metadata
- ``POST   /auth/v1/admin/users/{id}/logout``    — revogar sessões (best-effort)
- ``GET    /auth/v1/admin/users?page&per_page``  — busca por e-mail (paginada)
"""

import logging
from collections.abc import Mapping
from datetime import datetime
from types import TracebackType
from typing import Any, Self

import httpx

from src.application.ports.identity_provider import (
    EmailJaExisteNoProvedorError,
    IdentidadeAuth,
    IdentityProviderError,
    IdentityProviderNaoConfigurado,
    IdentityProviderPort,
)

logger = logging.getLogger("rastreio.identity")

# Ban "permanente": GoTrue não tem flag perpétua — usa duração longa (100 anos).
# A reativação manda "none". O estado canônico de ativo/inativo é a coluna
# usuarios.ativo; o ban é o espelho no auth (ADR-025).
_BAN_PERMANENTE = "876000h"
_BAN_NENHUM = "none"
# Busca por e-mail: varre a listagem paginada (client-side match — endpoint de
# filtro não é estável entre versões do GoTrue). Cap de páginas como guarda de
# runaway; a operação roda só em adoção de órfão/bootstrap, nunca em hot path.
_BUSCA_POR_EMAIL_MAX_PAGINAS = 20
_BUSCA_POR_EMAIL_POR_PAGINA = 100

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _parse_created_at(valor: object) -> datetime | None:
    """``created_at`` ISO do GoTrue → datetime aware (idade p/ adoção de órfão)."""
    if not isinstance(valor, str) or not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


class SupabaseAdminIdentityProvider(IdentityProviderPort):
    """Fala com a Admin API via httpx assíncrono (uma instância por processo)."""

    def __init__(self, supabase_url: str, secret_key: str) -> None:
        base = f"{supabase_url.rstrip('/')}/auth/v1"
        self._client = httpx.AsyncClient(
            base_url=base,
            headers={
                "apikey": secret_key,
                "Authorization": f"Bearer {secret_key}",
            },
            timeout=_TIMEOUT,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ porta
    async def create_user(self, email: str, senha: str, app_metadata: Mapping[str, object]) -> str:
        resp = await self._request(
            "POST",
            "/admin/users",
            json={
                "email": email,
                "password": senha,
                # Admin cria contas prontas para uso — sem fluxo de confirmação
                # por e-mail (DP-3).
                "email_confirm": True,
                "app_metadata": dict(app_metadata),
            },
            ok=(200, 201),
            conflito_email=True,
        )
        body = resp.json()
        user_id = body.get("id")
        if not isinstance(user_id, str) or not user_id:
            raise IdentityProviderError("resposta do provedor sem id de usuário")
        return user_id

    async def delete_user(self, user_id: str) -> None:
        # 404 tolerado: repetir a compensação/adoção converge (RNF-015).
        await self._request("DELETE", f"/admin/users/{user_id}", ok=(200, 204, 404))

    async def set_banned(self, user_id: str, banned: bool) -> None:
        await self._request(
            "PUT",
            f"/admin/users/{user_id}",
            json={"ban_duration": _BAN_PERMANENTE if banned else _BAN_NENHUM},
            ok=(200,),
        )

    async def update_app_metadata(self, user_id: str, app_metadata: Mapping[str, object]) -> None:
        await self._request(
            "PUT",
            f"/admin/users/{user_id}",
            json={"app_metadata": dict(app_metadata)},
            ok=(200,),
        )

    async def revoke_sessions(self, user_id: str) -> None:
        # Best-effort declarado na porta: 404 = endpoint indisponível na versão
        # do GoTrue → o ban segura o fluxo e os tokens expiram pelo TTL.
        resp = await self._request("POST", f"/admin/users/{user_id}/logout", ok=(200, 204, 404))
        if resp.status_code == 404:
            logger.info(
                "logout administrativo indisponível nesta versão do GoTrue",
                extra={"event": "admin_logout_indisponivel"},
            )

    async def find_user_by_email(self, email: str) -> IdentidadeAuth | None:
        alvo = email.strip().lower()
        for page in range(1, _BUSCA_POR_EMAIL_MAX_PAGINAS + 1):
            resp = await self._request(
                "GET",
                "/admin/users",
                params={"page": page, "per_page": _BUSCA_POR_EMAIL_POR_PAGINA},
                ok=(200,),
            )
            usuarios = resp.json().get("users") or []
            for u in usuarios:
                if str(u.get("email", "")).lower() == alvo:
                    metadata = u.get("app_metadata")
                    return IdentidadeAuth(
                        id=str(u.get("id", "")),
                        email=alvo,
                        app_metadata=metadata if isinstance(metadata, dict) else {},
                        created_at=_parse_created_at(u.get("created_at")),
                    )
            if len(usuarios) < _BUSCA_POR_EMAIL_POR_PAGINA:
                return None
        logger.warning(
            "busca por e-mail excedeu o cap de páginas da Admin API",
            extra={"event": "busca_email_cap_excedido"},
        )
        return None

    # --------------------------------------------------------------- interno
    async def _request(
        self,
        metodo: str,
        caminho: str,
        *,
        ok: tuple[int, ...],
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        conflito_email: bool = False,
    ) -> httpx.Response:
        try:
            resp = await self._client.request(metodo, caminho, json=json, params=params)
        except httpx.HTTPError as exc:
            # Nunca logar URL completa/headers (carregam a chave) — só o tipo.
            logger.error(
                "falha de comunicação com a Admin API",
                extra={"event": "admin_api_erro_rede", "error_type": type(exc).__name__},
            )
            raise IdentityProviderError("falha de comunicação com o provedor") from exc

        if resp.status_code in ok:
            return resp

        error_code = self._error_code(resp)
        if conflito_email and self._email_ja_existe(resp.status_code, error_code):
            raise EmailJaExisteNoProvedorError(error_code or "email_exists")

        logger.error(
            "Admin API respondeu erro",
            extra={
                "event": "admin_api_erro",
                "status": resp.status_code,
                "error_code": error_code,
            },
        )
        raise IdentityProviderError(f"provedor respondeu {resp.status_code}")

    @staticmethod
    def _error_code(resp: httpx.Response) -> str | None:
        try:
            body = resp.json()
        except ValueError:
            return None
        code = body.get("error_code") or body.get("code") or body.get("msg")
        return str(code) if code is not None else None

    @staticmethod
    def _email_ja_existe(status: int, error_code: str | None) -> bool:
        if status not in (400, 409, 422):
            return False
        texto = (error_code or "").lower()
        return "email_exists" in texto or "already" in texto

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()


class UnconfiguredIdentityProvider(IdentityProviderPort):
    """Stand-in quando ``SUPABASE_SECRET_KEY`` não está configurada.

    Mesmo padrão do ``UnconfiguredStorage`` (W0-C01): a app SOBE e as rotas de
    leitura funcionam; operações de gestão falham com erro claro (503) em vez
    de derrubar o boot.
    """

    async def create_user(self, email: str, senha: str, app_metadata: Mapping[str, object]) -> str:
        raise IdentityProviderNaoConfigurado()

    async def delete_user(self, user_id: str) -> None:
        raise IdentityProviderNaoConfigurado()

    async def set_banned(self, user_id: str, banned: bool) -> None:
        raise IdentityProviderNaoConfigurado()

    async def update_app_metadata(self, user_id: str, app_metadata: Mapping[str, object]) -> None:
        raise IdentityProviderNaoConfigurado()

    async def revoke_sessions(self, user_id: str) -> None:
        raise IdentityProviderNaoConfigurado()

    async def find_user_by_email(self, email: str) -> IdentidadeAuth | None:
        raise IdentityProviderNaoConfigurado()


__all__ = ["SupabaseAdminIdentityProvider", "UnconfiguredIdentityProvider"]
