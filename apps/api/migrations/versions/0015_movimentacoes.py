"""movimentacoes — log imutavel de transicoes + UPDATE RLS de provas (W3-C11)

Coracao da persistencia da maquina de estados (CLAUDE.md §5.3). Cria:

1. ``acao_enum`` (5 acoes de transicao — sincronizado com src/domain/state_machine
   /enums.py ``Acao``; regra de sync Python<->banco do DAT §4.5).
2. ``movimentacoes`` — APPEND-ONLY (RNF-006/DP-3): UMA linha por transicao bem
   sucedida. E o log de auditoria imutavel (nao ha ``audit_log`` separado — a
   divergencia DAT §2/Backlog C05 esta registrada em DECISIONS.md). Imutabilidade
   garantida em DUAS camadas: trigger ``movimentacoes_append_only`` (bloqueia
   UPDATE/DELETE ate para o owner) + ausencia de GRANT UPDATE/DELETE. RLS:
   - SELECT: quem enxerga a prova (espelha o escopo de ``provas`` via EXISTS) —
     habilita a Timeline do C13 para perfis em escopo; o "log completo" so e
     visivel a quem ve TODAS as provas (3Studio/Clicheria/Admin), satisfazendo
     RNF-006 (a pagina Log de Auditoria do C20 e gateada 3Studio-only na rota).
   - INSERT: WITH CHECK ``ator_id = app_current_user_id()`` (nao forja autor de
     outro) E a prova no escopo do ator (EXISTS). A validade da transicao em si e
     do motor no app (§11: regra de transicao NAO vive no banco).
   - ``idempotency_key`` UNIQUE: reenvio da MESMA transicao converge, nao duplica
     (RNF-015/DP-2).
3. ``provas`` UPDATE (a superficie que o C06 deixou para o C11 — privilegio
   minimo): GRANT UPDATE so das colunas ``status``/``finalizada_em``/``updated_at``
   (defesa em profundidade: o runtime nunca muda codigo/nome/rota/vendedor_id) +
   uma policy de UPDATE por perfil, espelhando o escopo de SELECT. O trigger de
   rota imutavel (0007) ja barra mudanca de rota.
4. ``provas_select_motorista`` AMPLIADA (W3-C11/decisao Motorista): alem dos 3
   "Em Transito", inclui os 3 estados de ORIGEM das transicoes do Motorista
   (``encaminhada_para_laminacao``, ``laminacao_concluida``, ``de_volta_studio``)
   — senao o Motorista recebe 404 ao escanear a prova que precisa pegar e nunca
   inicia a travessia (§6.3/§6.5). Conjunto de status, sem logica de rota (§11).
   Divergencia da Matriz §7 (listagem do Motorista) registrada em DECISIONS.md.

Espelhos 1:1 em ``migrations/rls/movimentacoes_*.sql`` e ``provas_update_*.sql``;
``provas_select_motorista.sql`` e ``provas_grants.sql`` foram atualizados.
Instrucoes SEPARADAS (asyncpg nao aceita multiplos comandos por instrucao —
mesmo motivo do 0008/0013/0014).

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Sincronizado com src/domain/state_machine/enums.py (Acao) — CLAUDE.md §6/§9.
ACOES = ("identificar_e_assinar", "aprovar", "reprovar", "reiniciar_ciclo", "cancelar")

# --- imutabilidade: trigger append-only (espelha o padrao do 0007) ----------
_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION public.movimentacoes_append_only()
RETURNS trigger LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
    RAISE EXCEPTION 'movimentacoes e append-only (RNF-006): % nao e permitido', TG_OP
        USING ERRCODE = 'check_violation';
END;
$$
"""
_TRIGGER = """
CREATE TRIGGER trg_movimentacoes_append_only
BEFORE UPDATE OR DELETE ON movimentacoes
FOR EACH ROW EXECUTE FUNCTION public.movimentacoes_append_only()
"""

# --- movimentacoes: RLS (espelhos: movimentacoes_*.sql) ---------------------
_MOV_RLS_ENABLE = "ALTER TABLE movimentacoes ENABLE ROW LEVEL SECURITY"
_MOV_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE movimentacoes FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE movimentacoes FROM authenticated;
        GRANT SELECT, INSERT ON TABLE movimentacoes TO authenticated;
    END IF;
END
$$
"""
_MOV_SELECT_NOME = "movimentacoes_select_por_prova_visivel"
_MOV_SELECT = (
    "CREATE POLICY movimentacoes_select_por_prova_visivel ON movimentacoes FOR SELECT "
    "TO authenticated "
    "USING (EXISTS (SELECT 1 FROM provas p WHERE p.id = movimentacoes.prova_id))"
)
_MOV_INSERT_NOME = "movimentacoes_insert_ator_em_escopo"
_MOV_INSERT = (
    "CREATE POLICY movimentacoes_insert_ator_em_escopo ON movimentacoes FOR INSERT "
    "TO authenticated "
    "WITH CHECK ("
    "  ator_id = public.app_current_user_id()"
    "  AND EXISTS (SELECT 1 FROM provas p WHERE p.id = movimentacoes.prova_id)"
    ")"
)

# --- provas: UPDATE grant (so 3 colunas) + policies por perfil --------------
_PROVAS_UPDATE_GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT UPDATE (status, finalizada_em, updated_at) ON TABLE provas TO authenticated;
    END IF;
END
$$
"""
# Espelham o escopo de SELECT (provas_select_*.sql). USING valida a linha ANTIGA
# (origem), WITH CHECK a NOVA (destino). Para o Motorista, ambas caem no conjunto
# operacional ampliado (origens + Em Transito); todos os destinos do Motorista
# sao "Com Motorista" (Em Transito), entao o WITH CHECK passa.
_MOTORISTA_SCOPE = (
    "public.app_setor() = 'motorista' AND status IN ("
    "'encaminhada_para_laminacao','laminacao_concluida','de_volta_studio',"
    "'com_motorista_ida_laminacao','com_motorista_volta_laminacao','com_motorista_entrega_final'"
    ")"
)
# Nome do CREATE POLICY LITERAL (nao interpolado) — o harness de equivalencia
# (test_equivalencia_rls_provas) casa os nomes 1:1 entre migration e os .sql por
# regex sobre o texto-fonte. So o escopo do Motorista vem de constante.
_PROVAS_UPDATE_POLICIES: tuple[tuple[str, str], ...] = (
    (
        "provas_update_studio",
        "CREATE POLICY provas_update_studio ON provas FOR UPDATE TO authenticated "
        "USING (public.app_setor() = 'studio') WITH CHECK (public.app_setor() = 'studio')",
    ),
    (
        "provas_update_clicheria",
        "CREATE POLICY provas_update_clicheria ON provas FOR UPDATE TO authenticated "
        "USING (public.app_setor() = 'clicheria') WITH CHECK (public.app_setor() = 'clicheria')",
    ),
    (
        "provas_update_admin",
        "CREATE POLICY provas_update_admin ON provas FOR UPDATE TO authenticated "
        "USING (public.app_is_admin()) WITH CHECK (public.app_is_admin())",
    ),
    (
        "provas_update_vendedor",
        "CREATE POLICY provas_update_vendedor ON provas FOR UPDATE TO authenticated "
        "USING (public.app_setor() = 'vendedor' AND vendedor_id = public.app_current_user_id()) "
        "WITH CHECK (public.app_setor() = 'vendedor' "
        "AND vendedor_id = public.app_current_user_id())",
    ),
    (
        "provas_update_motorista",
        f"CREATE POLICY provas_update_motorista ON provas FOR UPDATE TO authenticated "
        f"USING ({_MOTORISTA_SCOPE}) WITH CHECK ({_MOTORISTA_SCOPE})",
    ),
)

# --- provas_select_motorista AMPLIADA (espelho: provas_select_motorista.sql) -
_PROVAS_SELECT_MOTORISTA_NOME = "provas_select_motorista"
_PROVAS_SELECT_MOTORISTA_NOVA = (
    "CREATE POLICY provas_select_motorista ON provas FOR SELECT TO authenticated "
    f"USING ({_MOTORISTA_SCOPE})"
)
# Versao estreita do C06 (so Em Transito) — restaurada no downgrade.
_PROVAS_SELECT_MOTORISTA_ANTIGA = (
    "CREATE POLICY provas_select_motorista ON provas FOR SELECT TO authenticated "
    "USING (public.app_setor() = 'motorista' AND status IN ("
    "'com_motorista_ida_laminacao','com_motorista_volta_laminacao','com_motorista_entrega_final'))"
)


def upgrade() -> None:
    acao_enum = postgresql.ENUM(*ACOES, name="acao_enum", create_type=False)
    acao_enum.create(op.get_bind(), checkfirst=True)
    status_enum = postgresql.ENUM(name="status_prova_enum", create_type=False)

    op.create_table(
        "movimentacoes",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "prova_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("provas.id", name="fk_movimentacoes_prova_id_provas"),
            nullable=False,
        ),
        sa.Column("estado_origem", status_enum, nullable=False),
        sa.Column("estado_destino", status_enum, nullable=False),
        sa.Column("acao", acao_enum, nullable=False),
        # Ator da transicao (= sub/user_id do JWT). Sem FK para usuarios (mesma
        # filosofia do system_settings.updated_by: usuarios nunca e deletado).
        sa.Column("ator_id", sa.Uuid(as_uuid=False), nullable=False),
        # Ciclo de revisao no instante da movimentacao (RN-006: historico por
        # ciclo). O incremento de ciclo_atual e do C15.
        sa.Column("ciclo", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("motivo", sa.Text(), nullable=True),
        # Referencia da assinatura digital (RN-003). Nullable agora (DP-1): o C12
        # cria a tabela ``signatures`` e a FK; aqui o servico exige um stub.
        sa.Column("assinatura_ref", sa.Uuid(as_uuid=False), nullable=True),
        # Chave de idempotencia por operacao (RNF-015/DP-2): UNIQUE — reenvio da
        # mesma transicao converge, nao duplica.
        sa.Column("idempotency_key", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_movimentacoes_idempotency_key"),
    )
    # Timeline (C13): historico de UMA prova em ordem cronologica — indice composto.
    op.create_index(
        "ix_movimentacoes_prova_id_created_at",
        "movimentacoes",
        ["prova_id", "created_at"],
    )

    op.execute(_TRIGGER_FUNCTION)
    op.execute(_TRIGGER)

    op.execute(_MOV_RLS_ENABLE)
    op.execute(_MOV_GRANTS)
    op.execute(f"DROP POLICY IF EXISTS {_MOV_SELECT_NOME} ON movimentacoes")
    op.execute(_MOV_SELECT)
    op.execute(f"DROP POLICY IF EXISTS {_MOV_INSERT_NOME} ON movimentacoes")
    op.execute(_MOV_INSERT)

    # provas: superficie de UPDATE do C11.
    op.execute(_PROVAS_UPDATE_GRANT)
    for nome, create_sql in _PROVAS_UPDATE_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {nome} ON provas")
        op.execute(create_sql)
    # Amplia o escopo de leitura do Motorista (origens das transicoes).
    op.execute(f"DROP POLICY IF EXISTS {_PROVAS_SELECT_MOTORISTA_NOME} ON provas")
    op.execute(_PROVAS_SELECT_MOTORISTA_NOVA)


def downgrade() -> None:
    # Restaura o escopo estreito do Motorista (so Em Transito).
    op.execute(f"DROP POLICY IF EXISTS {_PROVAS_SELECT_MOTORISTA_NOME} ON provas")
    op.execute(_PROVAS_SELECT_MOTORISTA_ANTIGA)
    for nome, _escopo in _PROVAS_UPDATE_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {nome} ON provas")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN "
        "REVOKE UPDATE (status, finalizada_em, updated_at) ON TABLE provas FROM authenticated; "
        "END IF; END $$"
    )
    op.drop_table("movimentacoes")  # indice, trigger e RLS caem junto
    op.execute("DROP FUNCTION IF EXISTS public.movimentacoes_append_only()")
    op.execute("DROP TYPE IF EXISTS acao_enum")
