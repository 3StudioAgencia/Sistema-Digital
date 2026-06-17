"""TEMPORARY audit introspection (Wave 3 audit — read-only, DISPOSABLE).

Reads the live test Postgres catalog to verify the DB-layer guarantees the RLS
relies on (Area F2): roles cannot BYPASSRLS, sensitive tables have FORCE RLS,
the audit tables (movimentacoes/assinaturas) are append-only and have no
UPDATE/DELETE grant to authenticated, and provas UPDATE grants are column-limited.

Run:  TEST_DATABASE_URL=... uv run python -m audit.introspect_rls
"""

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from src.infrastructure.config import coerce_asyncpg_url

URL = coerce_asyncpg_url(
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/rastreio_test")
)
SENSITIVE = ["provas", "movimentacoes", "assinaturas", "usuarios", "system_settings", "rate_limit_contadores"]


async def main() -> None:
    engine = create_async_engine(URL, poolclass=NullPool)
    async with engine.connect() as conn:
        print("== ROLES (rolbypassrls, rolcanlogin, rolsuper) ==")
        rows = (await conn.execute(text(
            "SELECT rolname, rolbypassrls, rolcanlogin, rolsuper FROM pg_roles "
            "WHERE rolname IN ('rastreio_runtime','authenticated','anon','postgres') ORDER BY rolname"
        ))).all()
        for r in rows:
            print(f"   {r.rolname:20} bypassrls={r.rolbypassrls} login={r.rolcanlogin} super={r.rolsuper}")

        print("\n== TABLE RLS (relrowsecurity = ENABLE, relforcerowsecurity = FORCE) ==")
        rows = (await conn.execute(text(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = ANY(:t) AND relkind='r' ORDER BY relname"
        ), {"t": SENSITIVE})).all()
        for r in rows:
            print(f"   {r.relname:24} enable={r.relrowsecurity} force={r.relforcerowsecurity}")

        print("\n== POLICIES per table (cmd) ==")
        rows = (await conn.execute(text(
            "SELECT tablename, policyname, cmd, roles FROM pg_policies "
            "WHERE tablename = ANY(:t) ORDER BY tablename, cmd, policyname"
        ), {"t": SENSITIVE})).all()
        for r in rows:
            print(f"   {r.tablename:22} {r.cmd:7} {r.policyname}  roles={r.roles}")

        print("\n== TRIGGERS on movimentacoes / assinaturas (append-only enforcement) ==")
        rows = (await conn.execute(text(
            "SELECT event_object_table AS tbl, trigger_name, event_manipulation AS evt, action_timing AS tm "
            "FROM information_schema.triggers WHERE event_object_table IN ('movimentacoes','assinaturas') "
            "ORDER BY tbl, trigger_name, evt"
        ))).all()
        for r in rows:
            print(f"   {r.tbl:16} {r.trigger_name:34} {r.tm} {r.evt}")

        print("\n== GRANTS to authenticated on movimentacoes/assinaturas (must be SELECT/INSERT only) ==")
        rows = (await conn.execute(text(
            "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
            "WHERE grantee='authenticated' AND table_name IN ('movimentacoes','assinaturas') "
            "ORDER BY table_name, privilege_type"
        ))).all()
        for r in rows:
            print(f"   {r.table_name:16} {r.privilege_type}")

        print("\n== COLUMN GRANTS to authenticated on provas UPDATE (must be status/finalizada_em/updated_at/ciclo_atual) ==")
        rows = (await conn.execute(text(
            "SELECT column_name, privilege_type FROM information_schema.column_privileges "
            "WHERE grantee='authenticated' AND table_name='provas' AND privilege_type='UPDATE' "
            "ORDER BY column_name"
        ))).all()
        for r in rows:
            print(f"   provas.{r.column_name:16} {r.privilege_type}")

        print("\n== TABLE-LEVEL GRANTS to authenticated on provas (must NOT include DELETE; UPDATE only via columns) ==")
        rows = (await conn.execute(text(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            "WHERE grantee='authenticated' AND table_name='provas' ORDER BY privilege_type"
        ))).all()
        print("   table-level:", [r.privilege_type for r in rows])

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
