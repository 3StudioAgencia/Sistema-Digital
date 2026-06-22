"""audit_log — log imutavel de TODAS as acoes do sistema + chain de integridade (W6-C20)

A interface de Auditoria (C20) e a janela read-only deste log (3Studio-only). O
design pede MAIS do que o ``movimentacoes`` (C11): eventos que nao sao movimentacao
(``criou_prova`` C06, ``escaneou_qr`` C10), ENDERECO IP, ORIGEM (navegador) e um
HASH DE INTEGRIDADE encadeado. Isso expande o RNF-006 (DP-1=C, ADR-100): nasce uma
tabela propria ``audit_log`` (append-only) — SEM tocar ``movimentacoes`` (a Timeline
do C13 segue lendo de la). Cria:

1. ``audit_evento_enum`` (7 tipos — sincronizado com src/domain/auditoria.py
   ``EventoAuditoria``; regra de sync Python<->banco do DAT §4.5).
2. ``audit_log`` — APPEND-ONLY: campos de prova/ator DENORMALIZADOS (auto-contido,
   pesquisavel sem JOIN; registra o que era verdade no instante) + ``ip``/``origem``
   (best-effort, do middleware) + um CHAIN: ``seq`` monotonico, ``prev_hash`` e
   ``hash`` (SHA-256 de prev_hash || campos). Imutabilidade em DUAS camadas: trigger
   ``trg_audit_log_append_only`` (bloqueia UPDATE/DELETE ate para o owner) + ausencia
   de GRANT UPDATE/DELETE.
3. ``private.audit_log_hash`` — funcao IMMUTABLE pura (fonte UNICA do calculo do
   hash; usada pelo append E pelo verificar — sem drift de canonicalizacao). Usa
   ``extract(epoch ...)`` no timestamp (independe do timezone da sessao).
4. ``private.audit_log_append`` — SECURITY DEFINER: a UNICA forma de escrever no log
   (INSERT direto e REVOGADO de ``authenticated``). Forca ``ator_id``/``ator_setor``
   das claims (anti-forja), serializa o chain por ``pg_advisory_xact_lock`` e calcula
   ``seq``/``prev_hash``/``hash`` sob o lock. Atomica com a transacao do chamador.
5. ``private.audit_log_verificar`` — SECURITY INVOKER (admin le tudo pela RLS):
   recomputa o chain e devolve a 1a linha divergente (tamper-evidence — DP-4).
6. RLS: SELECT ``audit_log_select_admin`` = ``app_is_admin()`` (Matriz §7 "Log de
   Auditoria" ●○○○ — flag administrador, igual a Relatorios/Config). SEM policy de
   INSERT (escrita so via a funcao DEFINER). ``authenticated`` recebe so SELECT na
   tabela + EXECUTE nas 3 funcoes; ``anon`` nada.

Espelhos 1:1 em ``migrations/rls/audit_log_*.sql`` (DAT §2; reaplicar apos DROP).
Instrucoes SEPARADas (asyncpg nao aceita multiplos comandos por instrucao — mesmo
motivo do 0015/0017). ``sha256``/``encode``/``convert_to`` sao builtins do
``pg_catalog`` (PG11+), seguros com ``search_path=''``.

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Sincronizado com src/domain/auditoria.py (EventoAuditoria) — CLAUDE.md §6/§9.
EVENTOS = (
    "criou_prova",
    "escaneou_qr",
    "mudou_status",
    "aprovou_prova",
    "reprovou_prova",
    "reiniciou_ciclo",
    "cancelou_prova",
)

# Lock advisory global do chain (constante 8423712001, inlined nas funcoes abaixo e
# no espelho audit_log_functions.sql): serializa os appends (um por vez) para que
# dois eventos concorrentes nunca leiam o mesmo head e bifurquem o encadeamento. E o
# ULTIMO lock adquirido em todos os caminhos (criacao/transicao/escaneamento), entao
# nao ha ciclo de deadlock. Volume desta app e baixo (rastreio de provas) — o
# serializar e aceitavel; documentado em docs/auditoria.md.

# --- imutabilidade: trigger append-only (espelha o padrao do 0015) ----------
_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION public.audit_log_append_only()
RETURNS trigger LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
    RAISE EXCEPTION 'audit_log e append-only (RNF-006): % nao e permitido', TG_OP
        USING ERRCODE = 'check_violation';
END;
$$
"""
_TRIGGER = """
CREATE TRIGGER trg_audit_log_append_only
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION public.audit_log_append_only()
"""

# --- hash do chain: fonte UNICA do calculo (append + verificar) -------------
# Concatena prev_hash || todos os campos imutaveis, separados por '|', e aplica
# SHA-256 (hex). ``extract(epoch ...)`` no created_at: representacao do instante
# INDEPENDENTE do timezone da sessao (um ``::text`` de timestamptz dependeria do
# GUC ``timezone`` e quebraria a verificacao entre sessoes). coalesce(...,'') para
# todos os opcionais. IMMUTABLE: depende so dos argumentos (nao le tabela/GUC).
# ``SET lc_numeric = 'C'``: o ``numeric_out`` do Postgres ja e locale-independente
# (so ``to_char``/``money`` leem lc_numeric), mas fixamos explicitamente o GUC para
# blindar o determinismo do hash (belt-and-suspenders numa primitiva de
# tamper-evidence; sem mudar o valor em locale C/UTF-8) — revisao adversarial C20.
_FN_HASH = """
CREATE OR REPLACE FUNCTION private.audit_log_hash(
    p_prev_hash text, p_seq bigint, p_evento text, p_ator_id uuid, p_ator_setor text,
    p_prova_id uuid, p_prova_codigo text, p_prova_cliente text, p_prova_requerimento text,
    p_acao text, p_estado_origem text, p_estado_destino text, p_ciclo integer, p_motivo text,
    p_ip text, p_origem_user_agent text, p_origem_rotulo text, p_request_id text,
    p_created_at timestamptz
) RETURNS text
LANGUAGE sql
IMMUTABLE
SET search_path = ''
SET lc_numeric = 'C'
AS $$
    SELECT pg_catalog.encode(
        pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.concat_ws('|',
                coalesce(p_prev_hash, ''),
                p_seq::text,
                coalesce(p_evento, ''),
                coalesce(p_ator_id::text, ''),
                coalesce(p_ator_setor, ''),
                coalesce(p_prova_id::text, ''),
                coalesce(p_prova_codigo, ''),
                coalesce(p_prova_cliente, ''),
                coalesce(p_prova_requerimento, ''),
                coalesce(p_acao, ''),
                coalesce(p_estado_origem, ''),
                coalesce(p_estado_destino, ''),
                coalesce(p_ciclo::text, ''),
                coalesce(p_motivo, ''),
                coalesce(p_ip, ''),
                coalesce(p_origem_user_agent, ''),
                coalesce(p_origem_rotulo, ''),
                coalesce(p_request_id, ''),
                coalesce(extract(epoch from p_created_at)::text, '')
            ), 'UTF8')
        ), 'hex');
$$
"""

# --- append: UNICA porta de escrita (SECURITY DEFINER) ----------------------
_FN_APPEND = """
CREATE OR REPLACE FUNCTION private.audit_log_append(
    p_evento text, p_prova_id uuid, p_prova_codigo text, p_prova_cliente text,
    p_prova_requerimento text, p_acao text, p_estado_origem text, p_estado_destino text,
    p_ciclo integer, p_motivo text, p_ip text, p_origem_user_agent text,
    p_origem_rotulo text, p_request_id text
) RETURNS public.audit_log
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_ator_id uuid := public.app_current_user_id();
    v_ator_setor text := public.app_setor();
    v_seq bigint;
    v_prev_hash text;
    v_now timestamptz := pg_catalog.now();
    v_hash text;
    v_row public.audit_log;
BEGIN
    -- Fail-closed: sem ator (claims sem user_id) nao ha o que auditar.
    IF v_ator_id IS NULL THEN
        RAISE EXCEPTION 'audit_log_append: ator ausente (claims sem user_id)'
            USING ERRCODE = 'check_violation';
    END IF;
    -- Serializa o chain (ultimo lock do caminho — sem ciclo de deadlock).
    PERFORM pg_catalog.pg_advisory_xact_lock(8423712001);
    SELECT a.seq, a.hash INTO v_seq, v_prev_hash
    FROM public.audit_log a ORDER BY a.seq DESC LIMIT 1;
    v_seq := coalesce(v_seq, 0) + 1;
    v_prev_hash := coalesce(v_prev_hash, '');
    v_hash := private.audit_log_hash(
        v_prev_hash, v_seq, p_evento, v_ator_id, v_ator_setor, p_prova_id,
        p_prova_codigo, p_prova_cliente, p_prova_requerimento, p_acao,
        p_estado_origem, p_estado_destino, p_ciclo, p_motivo, p_ip,
        p_origem_user_agent, p_origem_rotulo, p_request_id, v_now);
    INSERT INTO public.audit_log (
        seq, evento, ator_id, ator_setor, prova_id, prova_codigo, prova_cliente,
        prova_requerimento, acao, estado_origem, estado_destino, ciclo, motivo,
        ip, origem_user_agent, origem_rotulo, request_id, prev_hash, hash, created_at
    ) VALUES (
        v_seq, p_evento::public.audit_evento_enum, v_ator_id,
        v_ator_setor::public.setor_enum, p_prova_id, p_prova_codigo, p_prova_cliente,
        p_prova_requerimento, p_acao::public.acao_enum,
        p_estado_origem::public.status_prova_enum, p_estado_destino::public.status_prova_enum,
        p_ciclo, p_motivo, p_ip, p_origem_user_agent, p_origem_rotulo, p_request_id,
        v_prev_hash, v_hash, v_now
    ) RETURNING * INTO v_row;
    RETURN v_row;
END;
$$
"""
# v_ator_setor vem de app_setor() (text); o INSERT usa o forcado das claims acima,
# nao o param — por isso ``p_ator_setor`` nao existe como argumento.

# --- verificar: recomputa o chain e localiza a 1a quebra (SECURITY INVOKER) --
_FN_VERIFICAR = """
CREATE OR REPLACE FUNCTION private.audit_log_verificar()
RETURNS TABLE (intacto boolean, total bigint, quebrou_em bigint)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    r public.audit_log;
    v_prev text := '';
    v_calc text;
    v_total bigint := 0;
    v_break bigint := NULL;
BEGIN
    -- Ordem do chain = seq asc. Sob RLS o chamador admin ve TODAS as linhas
    -- (o endpoint e 3Studio-only); um nao-admin veria 0 linhas e "intacto" vazio.
    FOR r IN SELECT * FROM public.audit_log ORDER BY seq ASC LOOP
        v_total := v_total + 1;
        v_calc := private.audit_log_hash(
            v_prev, r.seq, r.evento::text, r.ator_id, r.ator_setor::text, r.prova_id,
            r.prova_codigo, r.prova_cliente, r.prova_requerimento, r.acao::text,
            r.estado_origem::text, r.estado_destino::text, r.ciclo, r.motivo, r.ip,
            r.origem_user_agent, r.origem_rotulo, r.request_id, r.created_at);
        IF v_break IS NULL
           AND (r.prev_hash IS DISTINCT FROM v_prev OR r.hash IS DISTINCT FROM v_calc) THEN
            v_break := r.seq;
        END IF;
        -- Avanca pelo hash ARMAZENADO: localiza a 1a divergencia sem propagar erro
        -- (alterar a linha N quebra so em N; N+1 segue ligada ao hash armazenado de N).
        v_prev := r.hash;
    END LOOP;
    RETURN QUERY SELECT (v_break IS NULL), v_total, v_break;
END;
$$
"""

# --- RLS + grants (espelhos: audit_log_*.sql) -------------------------------
_RLS_ENABLE = "ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY"
_SELECT_NOME = "audit_log_select_admin"
_SELECT = (
    "CREATE POLICY audit_log_select_admin ON audit_log FOR SELECT "
    "TO authenticated "
    "USING (public.app_is_admin())"
)
_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE audit_log FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE audit_log FROM authenticated;
        -- So SELECT: a escrita e EXCLUSIVAMENTE pela funcao DEFINER (append),
        -- nunca INSERT direto (anti-forja do chain). UPDATE/DELETE jamais.
        GRANT SELECT ON TABLE audit_log TO authenticated;
    END IF;
END
$$
"""
_FUNCS_GRANTS = """
DO $$
BEGIN
    REVOKE ALL ON FUNCTION private.audit_log_hash(
        text, bigint, text, uuid, text, uuid, text, text, text, text, text, text,
        integer, text, text, text, text, text, timestamptz) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.audit_log_append(
        text, uuid, text, text, text, text, text, text, integer, text, text, text,
        text, text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.audit_log_verificar() FROM PUBLIC;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION private.audit_log_hash(
            text, bigint, text, uuid, text, uuid, text, text, text, text, text, text,
            integer, text, text, text, text, text, timestamptz) FROM anon;
        REVOKE ALL ON FUNCTION private.audit_log_append(
            text, uuid, text, text, text, text, text, text, integer, text, text, text,
            text, text) FROM anon;
        REVOKE ALL ON FUNCTION private.audit_log_verificar() FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT USAGE ON SCHEMA private TO authenticated;
        -- DEFINER (append) roda como owner; INVOKER (verificar) roda como o chamador
        -- e chama o hash — por isso ``authenticated`` precisa de EXECUTE nas 3.
        GRANT EXECUTE ON FUNCTION private.audit_log_hash(
            text, bigint, text, uuid, text, uuid, text, text, text, text, text, text,
            integer, text, text, text, text, text, timestamptz) TO authenticated;
        GRANT EXECUTE ON FUNCTION private.audit_log_append(
            text, uuid, text, text, text, text, text, text, integer, text, text, text,
            text, text) TO authenticated;
        GRANT EXECUTE ON FUNCTION private.audit_log_verificar() TO authenticated;
    END IF;
END
$$
"""


def upgrade() -> None:
    evento_enum = postgresql.ENUM(*EVENTOS, name="audit_evento_enum", create_type=False)
    evento_enum.create(op.get_bind(), checkfirst=True)
    setor_enum = postgresql.ENUM(name="setor_enum", create_type=False)
    acao_enum = postgresql.ENUM(name="acao_enum", create_type=False)
    status_enum = postgresql.ENUM(name="status_prova_enum", create_type=False)

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Ordem do chain — monotonico, atribuido sob o advisory lock (sem serial:
        # rollback nao deixa buraco). UNIQUE protege contra duplicata.
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("evento", evento_enum, nullable=False),
        # Ator (= user_id do JWT). Forcado pela funcao DEFINER (anti-forja); sem FK
        # (mesma filosofia de movimentacoes.ator_id: usuarios nunca e deletado).
        sa.Column("ator_id", sa.Uuid(as_uuid=False), nullable=False),
        # Setor do ator NO INSTANTE (denormalizado das claims — o log e historico).
        sa.Column("ator_setor", setor_enum, nullable=True),
        # Prova DENORMALIZADA: auto-contido e pesquisavel sem JOIN (e sem acoplar a
        # RLS de provas na leitura admin). Sem FK (decoupled; eventos futuros podem
        # nao ter prova). Nullable para o mesmo motivo.
        sa.Column("prova_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("prova_codigo", sa.Text(), nullable=True),
        sa.Column("prova_cliente", sa.Text(), nullable=True),
        sa.Column("prova_requerimento", sa.Text(), nullable=True),
        # Campos de transicao — so para os eventos de movimentacao (NULL p/ criar/escanear).
        sa.Column("acao", acao_enum, nullable=True),
        sa.Column("estado_origem", status_enum, nullable=True),
        sa.Column("estado_destino", status_enum, nullable=True),
        sa.Column("ciclo", sa.Integer(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        # Metadados de origem (best-effort, do middleware). ``ip`` como TEXT (lenient
        # com IPv6/proxy/desconhecido); ``origem_rotulo`` ja formatado p/ a UI.
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("origem_user_agent", sa.Text(), nullable=True),
        sa.Column("origem_rotulo", sa.Text(), nullable=True),
        # Correlacao com os logs estruturados (RNF-024).
        sa.Column("request_id", sa.Text(), nullable=True),
        # Chain de integridade (tamper-evidence — DP-4). prev_hash = hash do anterior
        # ('' no genesis); hash = SHA-256(prev_hash || campos). UNIQUE no hash.
        sa.Column("prev_hash", sa.Text(), nullable=False),
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("seq", name="uq_audit_log_seq"),
        sa.UniqueConstraint("hash", name="uq_audit_log_hash"),
    )
    # Indices dos filtros da barra (RNF-019): periodo, tipo de evento e ator. A
    # ordenacao default (seq desc) e coberta pelo unique de ``seq``.
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_evento", "audit_log", ["evento"])
    op.create_index("ix_audit_log_ator_id", "audit_log", ["ator_id"])

    op.execute(_TRIGGER_FUNCTION)
    op.execute(_TRIGGER)

    # Schema private ja existe (0011); guarda mantem a migration robusta isolada.
    op.execute("CREATE SCHEMA IF NOT EXISTS private")
    op.execute(_FN_HASH)
    op.execute(_FN_APPEND)
    op.execute(_FN_VERIFICAR)

    op.execute(_RLS_ENABLE)
    op.execute(_GRANTS)
    op.execute(f"DROP POLICY IF EXISTS {_SELECT_NOME} ON audit_log")
    op.execute(_SELECT)
    op.execute(_FUNCS_GRANTS)


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS private.audit_log_append("
        "text, uuid, text, text, text, text, text, text, integer, text, text, text, text, text)"
    )
    op.execute("DROP FUNCTION IF EXISTS private.audit_log_verificar()")
    op.execute(
        "DROP FUNCTION IF EXISTS private.audit_log_hash("
        "text, bigint, text, uuid, text, uuid, text, text, text, text, text, text, "
        "integer, text, text, text, text, text, timestamptz)"
    )
    op.drop_table("audit_log")  # indices, trigger e RLS caem junto
    op.execute("DROP FUNCTION IF EXISTS public.audit_log_append_only()")
    op.execute("DROP TYPE IF EXISTS audit_evento_enum")
