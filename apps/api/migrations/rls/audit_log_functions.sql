-- audit_log_functions.sql — chain de integridade do log (W6-C20)
--
-- Espelho 1:1 das funcoes da migration 0022 (DAT §2; reaplicar apos DROP). Tres
-- funcoes no schema `private` (NAO exposto pela Data API):
--   * audit_log_hash    — IMMUTABLE, fonte UNICA do calculo (append + verificar);
--   * audit_log_append  — SECURITY DEFINER, a UNICA porta de escrita (INSERT direto
--                         e revogado); forca ator das claims e serializa o chain;
--   * audit_log_verificar — SECURITY INVOKER, recomputa o chain (admin le tudo) e
--                         localiza a 1a linha divergente (tamper-evidence).
-- `sha256`/`encode`/`convert_to`/`concat_ws` sao builtins do pg_catalog (PG11+),
-- seguros com `search_path=''`. `extract(epoch ...)` torna o hash independente do
-- timezone da sessao. Idempotente.

CREATE SCHEMA IF NOT EXISTS private;

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
$$;

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
    IF v_ator_id IS NULL THEN
        RAISE EXCEPTION 'audit_log_append: ator ausente (claims sem user_id)'
            USING ERRCODE = 'check_violation';
    END IF;
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
$$;

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
        v_prev := r.hash;
    END LOOP;
    RETURN QUERY SELECT (v_break IS NULL), v_total, v_break;
END;
$$;

REVOKE ALL ON FUNCTION private.audit_log_hash(
    text, bigint, text, uuid, text, uuid, text, text, text, text, text, text,
    integer, text, text, text, text, text, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION private.audit_log_append(
    text, uuid, text, text, text, text, text, text, integer, text, text, text,
    text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION private.audit_log_verificar() FROM PUBLIC;

DO $$
BEGIN
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
        GRANT EXECUTE ON FUNCTION private.audit_log_hash(
            text, bigint, text, uuid, text, uuid, text, text, text, text, text, text,
            integer, text, text, text, text, text, timestamptz) TO authenticated;
        GRANT EXECUTE ON FUNCTION private.audit_log_append(
            text, uuid, text, text, text, text, text, text, integer, text, text, text,
            text, text) TO authenticated;
        GRANT EXECUTE ON FUNCTION private.audit_log_verificar() TO authenticated;
    END IF;
END
$$;
