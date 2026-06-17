"""nomes_de_vendedores: alinha o escopo do Motorista a ESTADOS_ESCOPO_MOTORISTA (W3 remediacao M-02)

Remediacao do achado M-02 da auditoria da Wave 3. O resolvedor
``private.nomes_de_vendedores`` (W2-C07, 0010/0011) re-aplica o escopo do chamador
num ``EXISTS`` para nao ampliar a Matriz §7. Quando o C11 (0015) AMPLIOU a RLS
``provas_select_motorista`` para o escopo operacional (origens das transicoes + Em
Transito = ``ESTADOS_ESCOPO_MOTORISTA``, 6 estados), o resolvedor IRMAO
``private.nomes_de_usuarios`` (C13/0017) acompanhou, mas ``nomes_de_vendedores``
ficou no escopo ANTIGO e estreito (so os 3 "Em Transito"). Os dois resolvedores
DIVERGIAM — o proprio cabecalho do arquivo avisa "mantenha-os em sincronia".

Efeito do drift: um Motorista que ve uma prova num estado de ORIGEM na listagem
(C07) veria o NOME do vendedor em branco/NULL (o ``EXISTS`` falhava). Restritivo,
nao vaza dado — mas e drift de comportamento. Esta migration realinha o ramo
``motorista`` aos 6 estados de ``ESTADOS_ESCOPO_MOTORISTA`` (mesma fonte da §6 que
``provas_select_motorista`` e ``nomes_de_usuarios``). Sem logica de rota (§11).

Espelho 1:1 em ``migrations/rls/nomes_de_vendedores.sql`` (DAT §2; reaplicar apos
recriacao). O harness offline ``test_equivalencia_rls_provas`` passou a travar
TAMBEM este resolvedor contra ``ESTADOS_ESCOPO_MOTORISTA`` (a lacuna que deixou o
drift passar — achado M-03).

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- escopo do Motorista ALINHADO (6 estados) — espelho: nomes_de_vendedores.sql -
_FUNCAO_NOVA = """
CREATE OR REPLACE FUNCTION private.nomes_de_vendedores(p_ids uuid[])
RETURNS TABLE (id uuid, nome text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.id, u.nome
    FROM public.usuarios u
    WHERE u.setor = 'vendedor'
      AND u.id = ANY(p_ids)
      AND EXISTS (
          SELECT 1 FROM public.provas p
          WHERE p.vendedor_id = u.id AND (
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

# --- escopo ANTIGO e estreito (3 "Em Transito") — restaurado no downgrade --------
_FUNCAO_ANTIGA = """
CREATE OR REPLACE FUNCTION private.nomes_de_vendedores(p_ids uuid[])
RETURNS TABLE (id uuid, nome text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.id, u.nome
    FROM public.usuarios u
    WHERE u.setor = 'vendedor'
      AND u.id = ANY(p_ids)
      AND EXISTS (
          SELECT 1 FROM public.provas p
          WHERE p.vendedor_id = u.id AND (
              public.app_is_admin()
              OR public.app_setor() IN ('studio', 'clicheria')
              OR (public.app_setor() = 'vendedor'
                  AND p.vendedor_id = public.app_current_user_id())
              OR (public.app_setor() = 'motorista' AND p.status IN (
                  'com_motorista_ida_laminacao',
                  'com_motorista_volta_laminacao',
                  'com_motorista_entrega_final'))
          )
      );
$$
"""

# A funcao ja existe (0010/0011); CREATE OR REPLACE preserva grants e nao mexe na
# assinatura — nada a re-conceder. O schema `private` ja existe (0011).


def upgrade() -> None:
    op.execute(_FUNCAO_NOVA)


def downgrade() -> None:
    op.execute(_FUNCAO_ANTIGA)
