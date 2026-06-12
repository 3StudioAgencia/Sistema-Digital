"""custom_access_token_hook — claims de perfil no JWT (W1-C05)

Cria ``public.custom_access_token_hook(event jsonb) returns jsonb``, o Custom
Access Token Hook do Supabase Auth: roda ANTES de cada emissao de token (login E
refresh) e ELEVA para o nivel superior dos claims o que a RLS le
(``auth.jwt() ->> 'setor'`` / ``->> 'user_id'`` / ``->> 'administrador'`` —
DAT §7.2). A fonte e o ``app_metadata`` que o Supabase ja injeta no proprio
``event.claims`` (gravado no provisionamento — ADR-025/027): o hook NAO le a
tabela ``usuarios`` (DP-2 opcao B), entao e rapido, ``SECURITY INVOKER`` e nunca
quebra a autenticacao por causa de RLS/lock na tabela.

Claims elevados (CLAUDE.md §6 / ADR-029):
- ``user_id``  = ``sub`` (UUID de auth.users; a RLS de ``provas`` casa
  ``vendedor_id = (auth.jwt() ->> 'user_id')::uuid``);
- ``setor``    = ``app_metadata.setor`` (escopo operacional);
- ``administrador`` = ``app_metadata.administrador`` (flag ORTOGONAL — ADR-023;
  default ``false`` quando ausente).

O hook PRESERVA todos os claims obrigatorios (so adiciona chaves). Conta sem
``app_metadata`` (ex.: criada pelo dashboard, sem provisionamento) emite token
normalmente, apenas sem ``setor`` e com ``administrador=false`` — menor
privilegio, sem enumeracao.

Grants (§1.1.3): execute concedido SO a ``supabase_auth_admin`` (o role que o
GoTrue usa para invocar o hook) + usage no schema; execute revogado de
``authenticated``/``anon``/``public``. Tudo condicionado a existencia das roles
do Supabase — o Postgres local de dev/teste nao as tem (mesmo padrao do 0002).

Registro do hook no projeto: passo de dashboard/CLI (Auth → Hooks → Customize
Access Token), documentado em ``docs/rbac.md``. Esta migration cria APENAS a
funcao + grants; a criacao da funcao acontece em qualquer banco-alvo do Alembic.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Funcao do hook (uma unica instrucao — os ';' internos vivem dentro do corpo
# $$, entao asyncpg a aceita como comando unico). Espelho legivel em docs/rbac.md.
_HOOK_FN = """
CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    claims jsonb;
    meta jsonb;
BEGIN
    claims := event->'claims';
    -- Robustez (pilar "nunca quebra a auth"): evento malformado/sem 'claims'
    -- valido -> devolve intacto em vez de estourar em jsonb_set(NULL, ...).
    IF claims IS NULL OR jsonb_typeof(claims) <> 'object' THEN
        RETURN event;
    END IF;
    meta := COALESCE(claims->'app_metadata', '{}'::jsonb);

    -- user_id = sub (UUID de auth.users) — posicao lida pela RLS (DAT §7.2).
    claims := jsonb_set(claims, '{user_id}', COALESCE(claims->'sub', 'null'::jsonb));

    -- setor: eleva de app_metadata para o topo (so quando presente).
    IF meta ? 'setor' THEN
        claims := jsonb_set(claims, '{setor}', meta->'setor');
    END IF;

    -- administrador: flag ortogonal (ADR-023). Default false se ausente —
    -- nunca elevar privilegio por omissao.
    IF meta ? 'administrador' THEN
        claims := jsonb_set(claims, '{administrador}', meta->'administrador');
    ELSE
        claims := jsonb_set(claims, '{administrador}', 'false'::jsonb);
    END IF;

    event := jsonb_set(event, '{claims}', claims);
    RETURN event;
END;
$$;
"""

# Grants criticos. REVOKE de PUBLIC roda sempre (o pseudo-role public existe em
# qualquer Postgres); os grants/revokes das roles do Supabase sao condicionais.
_HOOK_REVOKE_PUBLIC = (
    "REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook(jsonb) FROM PUBLIC"
)
_HOOK_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_auth_admin') THEN
        GRANT USAGE ON SCHEMA public TO supabase_auth_admin;
        GRANT EXECUTE ON FUNCTION public.custom_access_token_hook(jsonb)
            TO supabase_auth_admin;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook(jsonb)
            FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook(jsonb) FROM anon;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.execute(_HOOK_FN)
    op.execute(_HOOK_REVOKE_PUBLIC)
    op.execute(_HOOK_GRANTS)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.custom_access_token_hook(jsonb)")
