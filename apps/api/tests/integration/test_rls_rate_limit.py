"""RLS + upsert do contador de tentativas (W3-C10) contra Postgres real (@db).

Exercita a tabela ``rate_limit_contadores`` como o backend a verá em produção
(``SET LOCAL ROLE authenticated`` + claims propagados — ADR-008):

- o upsert atômico INCREMENTA dentro da MESMA janela (determinístico na mesma
  transação: ``now()`` é estável → mesmo minuto);
- o ator só vê/grava a PRÓPRIA linha (``rate_limit_contadores_self``) — um ator
  nunca lê nem incrementa o contador de outro (isolamento anti-abuso);
- o ``WITH CHECK`` barra gravar a linha de outro ator (defesa em profundidade);
- ``authenticated`` não tem GRANT de DELETE (a app nunca apaga — privilégio mínimo).
"""

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

pytestmark = pytest.mark.db

# Espelho do upsert do ``SqlAlchemyRateLimiter`` (mantê-los iguais — a lógica de
# janela é testada aqui contra o Postgres real).
_UPSERT = (
    "INSERT INTO rate_limit_contadores (user_id, chave, janela_inicio, contador) "
    "VALUES (public.app_current_user_id(), :chave, date_trunc('minute', now()), 1) "
    "ON CONFLICT (user_id, chave) DO UPDATE SET "
    "contador = CASE WHEN rate_limit_contadores.janela_inicio = date_trunc('minute', now()) "
    "THEN rate_limit_contadores.contador + 1 ELSE 1 END, "
    "janela_inicio = date_trunc('minute', now()) "
    "RETURNING contador"
)


def _claims(sub: str, setor: str = "vendedor") -> str:
    return json.dumps(
        {
            "sub": sub,
            "user_id": sub,
            "setor": setor,
            "administrador": False,
            "role": "authenticated",
            "aud": "authenticated",
        }
    )


async def _autenticar(conn: AsyncConnection, sub: str) -> None:
    await conn.execute(
        text("SELECT set_config('request.jwt.claims', :c, true)"), {"c": _claims(sub)}
    )
    await conn.execute(text("SET LOCAL ROLE authenticated"))


async def test_upsert_incrementa_na_mesma_janela(usuarios_engine: AsyncEngine) -> None:
    """Duas tentativas no mesmo minuto (mesma transação → ``now()`` estável):
    1 e depois 2 — determinístico, sem depender do relógio de parede."""
    sub = str(uuid.uuid4())
    async with usuarios_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub)
            c1 = (await conn.execute(text(_UPSERT), {"chave": "identificar"})).scalar_one()
            c2 = (await conn.execute(text(_UPSERT), {"chave": "identificar"})).scalar_one()
            await trans.commit()
        except BaseException:
            await trans.rollback()
            raise
    assert (c1, c2) == (1, 2)


async def test_ator_so_ve_e_incrementa_a_propria_linha(usuarios_engine: AsyncEngine) -> None:
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    engine = usuarios_engine

    # A incrementa duas vezes (→ 2).
    async with engine.connect() as conn:
        trans = await conn.begin()
        await _autenticar(conn, a)
        await conn.execute(text(_UPSERT), {"chave": "identificar"})
        await conn.execute(text(_UPSERT), {"chave": "identificar"})
        await trans.commit()

    # B não enxerga a linha de A (RLS) e parte do zero ao incrementar (→ 1).
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, b)
            visiveis = (
                await conn.execute(text("SELECT user_id FROM rate_limit_contadores"))
            ).scalars().all()
            assert {str(x) for x in visiveis} == set()  # nada de A
            cb = (await conn.execute(text(_UPSERT), {"chave": "identificar"})).scalar_one()
            assert cb == 1  # contador de B é independente do de A
        finally:
            await trans.rollback()


async def test_with_check_barra_gravar_linha_de_outro_ator(usuarios_engine: AsyncEngine) -> None:
    """Defesa em profundidade: mesmo forjando o user_id de outro, o WITH CHECK
    da policy rejeita (o ator só grava a própria linha)."""
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    with pytest.raises(DBAPIError):
        async with usuarios_engine.connect() as conn:
            trans = await conn.begin()
            try:
                await _autenticar(conn, a)
                await conn.execute(
                    text(
                        "INSERT INTO rate_limit_contadores "
                        "(user_id, chave, janela_inicio, contador) "
                        "VALUES (:outro, 'identificar', now(), 1)"
                    ),
                    {"outro": b},  # tenta gravar a linha de B
                )
                await trans.commit()
            except BaseException:
                await trans.rollback()
                raise


async def test_authenticated_nao_tem_grant_de_delete(usuarios_engine: AsyncEngine) -> None:
    """Privilégio mínimo: a app nunca apaga contadores (o upsert reseta a janela)."""
    sub = str(uuid.uuid4())
    with pytest.raises(DBAPIError, match=r"permission denied|InsufficientPrivilege"):
        async with usuarios_engine.connect() as conn:
            trans = await conn.begin()
            try:
                await _autenticar(conn, sub)
                await conn.execute(text("DELETE FROM rate_limit_contadores"))
            finally:
                await trans.rollback()
