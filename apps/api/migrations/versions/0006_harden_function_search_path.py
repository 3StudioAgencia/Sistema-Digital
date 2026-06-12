"""Fixa search_path nas 5 funcoes de seguranca (W1-A-004)

O hook (0004) e os 4 helpers de RLS (0005) nasceram SEM ``SET search_path``
(``proconfig=NULL``) — o advisor ``function_search_path_mutable`` do Supabase
sinaliza isso como risco de hardening (sequestro por objeto homonimo num schema
mutavel). Os corpos so usam built-ins de ``pg_catalog`` (implicito) e chamadas ja
schema-qualificadas (``public.*``), entao ``SET search_path = ''`` (vazio) e
SEGURO — nao quebra nenhuma resolucao de nome.

As definicoes inline de 0004/0005 e o espelho ``migrations/rls/_helpers.sql`` ja
foram atualizados para criar as funcoes endurecidas em bancos novos. Esta
migration existe porque editar migrations ja aplicadas NAO as reexecuta no
projeto real (Supabase) — o ``ALTER FUNCTION`` abaixo leva o endurecimento ao
banco que ja esta em 0005. Em banco novo e idempotente (o atributo ja estara
setado pela criacao).

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (assinatura completa — necessaria para identificar a funcao)
_FUNCOES = (
    "public.custom_access_token_hook(jsonb)",
    "public.app_current_claims()",
    "public.app_setor()",
    "public.app_is_admin()",
    "public.app_current_user_id()",
)


def upgrade() -> None:
    for fn in _FUNCOES:
        op.execute(f"ALTER FUNCTION {fn} SET search_path = ''")


def downgrade() -> None:
    # Reverte ao search_path mutavel (proconfig=NULL) — postura anterior.
    for fn in _FUNCOES:
        op.execute(f"ALTER FUNCTION {fn} RESET search_path")
