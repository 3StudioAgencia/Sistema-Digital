"""nomes_de_usuarios: projecao de nomes de QUALQUER ator (W3-C13 / DP-2b)

A Timeline (C13) mostra o RESPONSAVEL de cada movimentacao — e o ator pode ser de
QUALQUER setor (3Studio encaminha, Motorista transporta, Clicheria recebe,
Vendedor aprova). A RLS de ``usuarios`` (C05) so deixa admin/self lerem outras
linhas, entao um Vendedor vendo a propria prova nao resolveria o NOME do 3Studio/
Motorista/Clicheria que a movimentou (viria NULL num JOIN sob a propria sessao).

``private.nomes_de_usuarios(uuid[]) -> (id, nome)`` resolve o nome SEM ampliar a
Matriz §7: projeta o MINIMO (apenas id+nome) e SO de atores que aparecem em
movimentacoes de provas VISIVEIS ao chamador — re-aplicando o escopo das policies
``provas_select_*`` (defesa em profundidade). Generaliza ``nomes_de_vendedores``
(0010/0011) para qualquer setor; nasce direto no schema ``private`` (NAO exposto
pela Data API/PostgREST — sem vetor de RPC; advisors 0028/0029 limpos), com
``SET search_path = ''`` + corpo schema-qualificado (blindagem W1-A-004).
``authenticated`` recebe USAGE no schema (ja concedido pela 0011) + EXECUTE na
funcao; ``anon`` nada.

O conjunto de status do Motorista espelha ``ESTADOS_ESCOPO_MOTORISTA`` /
``provas_select_motorista`` AMPLIADA pela 0015 (origens das transicoes + Em
Transito) — assim um Motorista que enxerga a prova tambem resolve os nomes dos
atores dela. (Drift: este predicado acompanha a RLS de ``provas`` — mantenha-os em
sincronia, como o ``nomes_de_vendedores``.)

Espelho versionado 1:1 em ``migrations/rls/nomes_de_usuarios.sql`` (DAT §2;
reaplicar apos recriacao). Instrucoes SEPARADAS (asyncpg nao aceita multiplos
comandos por instrucao preparada — mesmo motivo do 0010/0011).

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- funcao de projecao de nomes de ator (espelho: nomes_de_usuarios.sql) -----
_FUNCAO = """
CREATE OR REPLACE FUNCTION private.nomes_de_usuarios(p_ids uuid[])
RETURNS TABLE (id uuid, nome text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.id, u.nome
    FROM public.usuarios u
    WHERE u.id = ANY(p_ids)
      -- So nomes de atores em provas VISIVEIS ao chamador: re-aplica o escopo das
      -- policies provas_select_* (via os helpers app_*, que leem request.jwt.claims),
      -- sobre as movimentacoes em que o usuario foi o ator.
      AND EXISTS (
          SELECT 1
          FROM public.movimentacoes m
          JOIN public.provas p ON p.id = m.prova_id
          WHERE m.ator_id = u.id AND (
              public.app_is_admin()
              OR public.app_setor() IN ('studio', 'clicheria')
              OR (public.app_setor() = 'vendedor'
                  AND p.vendedor_id = public.app_current_user_id())
              OR (public.app_setor() = 'motorista' AND p.status IN (
                  'encaminhada_para_laminacao',
                  'laminacao_concluida',
                  'de_volta_studio',
                  'com_motorista_ida_laminacao',
                  'com_motorista_volta_laminacao',
                  'com_motorista_entrega_final'))
          )
      );
$$
"""
_FUNCAO_REVOKE = "REVOKE ALL ON FUNCTION private.nomes_de_usuarios(uuid[]) FROM PUBLIC"
_FUNCAO_GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION private.nomes_de_usuarios(uuid[]) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        -- USAGE no schema private ja foi concedido pela 0011; reidempotente aqui.
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.nomes_de_usuarios(uuid[]) TO authenticated;
    END IF;
END
$$
"""


def upgrade() -> None:
    # O schema ``private`` ja existe (criado pela 0011); a guarda mantem a
    # migration robusta a aplicacao isolada.
    op.execute("CREATE SCHEMA IF NOT EXISTS private")
    op.execute(_FUNCAO)
    op.execute(_FUNCAO_REVOKE)
    op.execute(_FUNCAO_GRANT)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS private.nomes_de_usuarios(uuid[])")
