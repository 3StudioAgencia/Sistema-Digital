"""custom_access_token_hook (W1-C05) contra Postgres real (@db).

Invoca a funcao diretamente (``SELECT``) e valida que os claims de perfil sao
ELEVADOS ao nivel superior na posicao que a RLS le (DAT §7.2), preservando os
claims obrigatorios e nunca elevando privilegio por omissao.
"""

import json
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.db

_SUB = "11111111-1111-1111-1111-111111111111"
# Claims que o hook JAMAIS pode remover/alterar (subset dos obrigatorios — §1.1.1).
_OBRIGATORIOS = ("sub", "aud", "exp", "iat", "role", "email")


def _event(app_metadata: dict[str, Any]) -> dict[str, Any]:
    """Espelha o ``event`` que o GoTrue passa ao hook (app_metadata ja em claims)."""
    return {
        "user_id": _SUB,
        "claims": {
            "sub": _SUB,
            "aud": "authenticated",
            "exp": 9999999999,
            "iat": 1111111111,
            "role": "authenticated",
            "email": "x@y.z",
            "app_metadata": app_metadata,
            "user_metadata": {},
        },
        "authentication_method": "password",
    }


async def _claims(engine: AsyncEngine, app_metadata: dict[str, Any]) -> dict[str, Any]:
    async with engine.connect() as conn:
        devolvido = (
            await conn.execute(
                text("SELECT public.custom_access_token_hook(CAST(:e AS jsonb))"),
                {"e": json.dumps(_event(app_metadata))},
            )
        ).scalar_one()
    # asyncpg devolve jsonb como texto JSON — normaliza para dict.
    evento = devolvido if isinstance(devolvido, dict) else json.loads(devolvido)
    return evento["claims"]


@pytest.mark.parametrize(
    ("app_metadata", "setor_esperado", "admin_esperado"),
    [
        ({"setor": "studio", "administrador": True}, "studio", True),
        ({"setor": "vendedor", "administrador": False}, "vendedor", False),
        # Ortogonalidade (ADR-023): Vendedor pode ser Admin.
        ({"setor": "vendedor", "administrador": True}, "vendedor", True),
        ({"setor": "motorista", "administrador": False}, "motorista", False),
        ({"setor": "clicheria", "administrador": False}, "clicheria", False),
    ],
)
async def test_hook_eleva_claims_por_perfil(
    usuarios_engine: AsyncEngine,
    app_metadata: dict[str, Any],
    setor_esperado: str,
    admin_esperado: bool,
) -> None:
    claims = await _claims(usuarios_engine, app_metadata)
    assert claims["setor"] == setor_esperado
    assert claims["administrador"] is admin_esperado
    assert claims["user_id"] == _SUB
    # Claims obrigatorios preservados — auth nao quebra (§1.1.1).
    for chave in _OBRIGATORIOS:
        assert chave in claims


async def test_hook_sem_app_metadata_nao_quebra_e_nega_por_padrao(
    usuarios_engine: AsyncEngine,
) -> None:
    """Conta sem provisionamento (sem app_metadata): emite token, mas sem setor e
    com administrador=false (menor privilegio, sem enumeracao)."""
    claims = await _claims(usuarios_engine, {})
    assert "setor" not in claims
    assert claims["administrador"] is False
    assert claims["user_id"] == _SUB
    for chave in _OBRIGATORIOS:
        assert chave in claims


async def test_hook_sem_flag_administrador_assume_false(
    usuarios_engine: AsyncEngine,
) -> None:
    claims = await _claims(usuarios_engine, {"setor": "studio"})
    assert claims["setor"] == "studio"
    assert claims["administrador"] is False


async def test_hook_evento_malformado_nao_quebra_a_emissao(
    usuarios_engine: AsyncEngine,
) -> None:
    """Robustez (revisão de segurança W1-C05): evento SEM 'claims' não pode
    estourar em jsonb_set(NULL, ...) — devolve o evento intacto."""
    for evento in ({"user_id": _SUB}, {"user_id": _SUB, "claims": None}):
        async with usuarios_engine.connect() as conn:
            devolvido = (
                await conn.execute(
                    text("SELECT public.custom_access_token_hook(CAST(:e AS jsonb))"),
                    {"e": json.dumps(evento)},
                )
            ).scalar_one()
        resultado = devolvido if isinstance(devolvido, dict) else json.loads(devolvido)
        assert resultado == evento  # inalterado, sem erro


@pytest.mark.parametrize(
    "funcao",
    [
        "custom_access_token_hook",
        "app_current_claims",
        "app_setor",
        "app_is_admin",
        "app_current_user_id",
    ],
)
async def test_funcoes_de_seguranca_tem_search_path_fixo(
    usuarios_engine: AsyncEngine, funcao: str
) -> None:
    """W1-A-004: o hook + os 4 helpers de RLS fixam ``search_path`` (proconfig não
    nulo, contendo ``search_path=``) — advisor ``function_search_path_mutable``
    resolvido. As migrations 0004/0005 criam endurecido; 0006 endurece o banco já
    migrado."""
    async with usuarios_engine.connect() as conn:
        proconfig = (
            await conn.execute(
                text(
                    "SELECT proconfig FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = 'public' AND p.proname = :nome"
                ),
                {"nome": funcao},
            )
        ).scalar_one()
    assert proconfig is not None, f"{funcao}: proconfig NULL (search_path mutável)"
    assert any(item.startswith("search_path=") for item in proconfig)
