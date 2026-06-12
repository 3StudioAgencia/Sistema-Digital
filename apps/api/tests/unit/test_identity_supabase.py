"""Adapter da Admin API do Supabase (W1-C04) — offline via httpx.MockTransport.

Valida o CONTRATO HTTP (payloads, headers, mapeamento de erros) sem rede e sem
chave real. A fronteira tipada com o GoTrue é exatamente este adapter.
"""

import json
from typing import Any

import httpx
import pytest
from src.adapters.outbound.identity.supabase_admin import (
    SupabaseAdminIdentityProvider,
    UnconfiguredIdentityProvider,
)
from src.application.ports.identity_provider import (
    EmailJaExisteNoProvedorError,
    IdentityProviderError,
    IdentityProviderNaoConfigurado,
)

SECRET = "sb_secret_teste_nunca_real"
URL = "https://projeto.supabase.co"


def _provider(handler: Any) -> SupabaseAdminIdentityProvider:
    provider = SupabaseAdminIdentityProvider(supabase_url=URL, secret_key=SECRET)
    # substitui o client interno por um com MockTransport (mesma base_url/headers)
    provider._client = httpx.AsyncClient(  # acesso privado deliberado: teste do adapter
        base_url=f"{URL}/auth/v1",
        headers={"apikey": SECRET, "Authorization": f"Bearer {SECRET}"},
        transport=httpx.MockTransport(handler),
    )
    return provider


async def test_create_user_payload_e_headers() -> None:
    capturado: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["headers"] = dict(request.headers)
        capturado["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "uuid-novo"})

    provider = _provider(handler)
    user_id = await provider.create_user(
        "x@y.z", "senha-forte-1", {"setor": "vendedor", "administrador": False}
    )

    assert user_id == "uuid-novo"
    assert capturado["url"].endswith("/auth/v1/admin/users")
    assert capturado["headers"]["apikey"] == SECRET
    assert capturado["headers"]["authorization"] == f"Bearer {SECRET}"
    assert capturado["body"] == {
        "email": "x@y.z",
        "password": "senha-forte-1",
        "email_confirm": True,
        "app_metadata": {"setor": "vendedor", "administrador": False},
    }
    await provider.aclose()


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (422, {"error_code": "email_exists"}),
        (400, {"msg": "A user with this email address has already been registered"}),
    ],
)
async def test_create_user_email_existente(status: int, body: dict[str, Any]) -> None:
    provider = _provider(lambda _req: httpx.Response(status, json=body))
    with pytest.raises(EmailJaExisteNoProvedorError):
        await provider.create_user("x@y.z", "senha-forte-1", {})
    await provider.aclose()


async def test_create_user_erro_generico() -> None:
    provider = _provider(lambda _req: httpx.Response(500, json={"msg": "boom"}))
    with pytest.raises(IdentityProviderError):
        await provider.create_user("x@y.z", "senha-forte-1", {})
    await provider.aclose()


async def test_create_user_resposta_sem_id() -> None:
    provider = _provider(lambda _req: httpx.Response(200, json={}))
    with pytest.raises(IdentityProviderError):
        await provider.create_user("x@y.z", "senha-forte-1", {})
    await provider.aclose()


async def test_delete_user_404_e_idempotente() -> None:
    provider = _provider(lambda _req: httpx.Response(404, json={"msg": "not found"}))
    await provider.delete_user("uuid-x")  # não levanta
    await provider.aclose()


@pytest.mark.parametrize(("banned", "esperado"), [(True, "876000h"), (False, "none")])
async def test_set_banned_payload(banned: bool, esperado: str) -> None:
    capturado: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["body"] = json.loads(request.content)
        capturado["metodo"] = request.method
        return httpx.Response(200, json={})

    provider = _provider(handler)
    await provider.set_banned("uuid-x", banned=banned)
    assert capturado["metodo"] == "PUT"
    assert capturado["body"] == {"ban_duration": esperado}
    await provider.aclose()


async def test_update_app_metadata_payload() -> None:
    capturado: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    provider = _provider(handler)
    await provider.update_app_metadata("uuid-x", {"setor": "studio", "administrador": True})
    assert capturado["body"] == {"app_metadata": {"setor": "studio", "administrador": True}}
    await provider.aclose()


async def test_revoke_sessions_tolera_endpoint_inexistente() -> None:
    provider = _provider(lambda _req: httpx.Response(404, json={}))
    await provider.revoke_sessions("uuid-x")  # não levanta (best-effort)
    await provider.aclose()


async def test_find_user_by_email_pagina_ate_achar() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        if page == 1:
            users = [{"id": f"u{i}", "email": f"u{i}@x.y", "app_metadata": {}} for i in range(100)]
        else:
            users = [
                {
                    "id": "alvo",
                    "email": "ACHA@x.y",
                    "app_metadata": {"k": 1},
                    "created_at": "2026-06-01T12:00:00Z",
                }
            ]
        return httpx.Response(200, json={"users": users})

    provider = _provider(handler)
    achado = await provider.find_user_by_email("acha@x.y")
    assert achado is not None
    assert achado.id == "alvo"
    assert achado.app_metadata == {"k": 1}
    assert achado.created_at is not None
    assert achado.created_at.isoformat() == "2026-06-01T12:00:00+00:00"
    await provider.aclose()


async def test_find_user_by_email_nao_achou() -> None:
    provider = _provider(lambda _req: httpx.Response(200, json={"users": []}))
    assert await provider.find_user_by_email("nao@x.y") is None
    await provider.aclose()


async def test_erro_de_rede_vira_identity_provider_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("rede caiu")

    provider = _provider(handler)
    with pytest.raises(IdentityProviderError):
        await provider.set_banned("uuid-x", banned=True)
    await provider.aclose()


async def test_unconfigured_levanta_erro_claro() -> None:
    provider = UnconfiguredIdentityProvider()
    with pytest.raises(IdentityProviderNaoConfigurado):
        await provider.create_user("x@y.z", "senha-forte-1", {})
    with pytest.raises(IdentityProviderNaoConfigurado):
        await provider.find_user_by_email("x@y.z")
