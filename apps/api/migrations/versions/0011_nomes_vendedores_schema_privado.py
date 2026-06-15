"""nomes_de_vendedores: move para schema privado nao-exposto (W2-C07, pos-deploy)

Os advisors de seguranca do Supabase (lint 0028/0029) sinalizam
``public.nomes_de_vendedores`` como funcao SECURITY DEFINER chamavel via RPC do
PostgREST (`/rest/v1/rpc/...`) por ``anon`` e ``authenticated`` — porque as
DEFAULT PRIVILEGES do Supabase concedem EXECUTE as roles de API para funcoes do
schema ``public`` (o ``REVOKE ... FROM PUBLIC`` da 0010 nao remove esses grants
explicitos). A funcao NAO e um RPC publico: e um resolvedor INTERNO de nomes
chamado pelo backend (ADR-045).

Correcao (remediacao do advisor): move a funcao para o schema ``private`` (NAO
exposto pela Data API — PostgREST so publica ``public``/``graphql_public``),
eliminando o vetor de RPC e limpando os advisors. ``authenticated`` recebe USAGE
no schema + EXECUTE na funcao (privilegio minimo; ``anon`` nao recebe nada). O
predicado de escopo do chamador no corpo (0010) permanece como defesa em
profundidade. O backend passa a chamar ``private.nomes_de_vendedores``.

Espelho atualizado em ``migrations/rls/nomes_de_vendedores.sql``.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CRIA_SCHEMA = "CREATE SCHEMA IF NOT EXISTS private"
_REVOGA_SCHEMA_PUBLIC = "REVOKE ALL ON SCHEMA private FROM PUBLIC"
_MOVE = "ALTER FUNCTION public.nomes_de_vendedores(uuid[]) SET SCHEMA private"
# Privilegio minimo, deterministico (nao depende das default privileges): revoga
# tudo de PUBLIC e de anon, concede USAGE+EXECUTE so a authenticated.
_REVOGA_FUNCAO_PUBLIC = "REVOKE ALL ON FUNCTION private.nomes_de_vendedores(uuid[]) FROM PUBLIC"
_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION private.nomes_de_vendedores(uuid[]) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.nomes_de_vendedores(uuid[]) TO authenticated;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.execute(_CRIA_SCHEMA)
    op.execute(_REVOGA_SCHEMA_PUBLIC)
    op.execute(_MOVE)
    op.execute(_REVOGA_FUNCAO_PUBLIC)
    op.execute(_GRANTS)


def downgrade() -> None:
    # Volta a funcao para public (estado da 0010); o schema private fica (vazio,
    # inofensivo). Reconcede EXECUTE a authenticated no schema public.
    op.execute("ALTER FUNCTION private.nomes_de_vendedores(uuid[]) SET SCHEMA public")
    op.execute("REVOKE ALL ON FUNCTION public.nomes_de_vendedores(uuid[]) FROM PUBLIC")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                GRANT EXECUTE ON FUNCTION public.nomes_de_vendedores(uuid[]) TO authenticated;
            END IF;
        END
        $$
        """
    )
