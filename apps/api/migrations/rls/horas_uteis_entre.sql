-- horas_uteis_entre.sql — horas UTEIS decorridas entre dois instantes (W5-C17)
--
-- Os Relatorios (C17) medem tempos em HORAS UTEIS — janela comercial FIXA seg-sex
-- 07:00-18:00 (RNF-011), fuso America/Sao_Paulo, feriados FORA de escopo (igual
-- ao C16/DP-4). Onde a 0020 (instante_limite_atraso) recua um limite a partir de
-- "agora" (predicado de "Atrasada"), esta funcao soma o DURADO direto entre duas
-- movimentacoes (chegada ao vendedor -> aprovacao; criacao -> 1a mov; envio a
-- clicheria -> recebimento). Complementa o predicado de atraso, que segue reusado
-- verbatim (consistencia — criterio §6.5).
--
-- Funcao PURA (nao toca tabelas): STABLE, SECURITY INVOKER, SET search_path=''
-- (blindagem W1-A-004; so built-ins do pg_catalog). Schema ``private`` (NAO
-- exposto pela Data API/PostgREST). So ``authenticated`` recebe EXECUTE.
--
-- Idempotente. Espelho 1:1 da migration 0021 (reaplicar apos DROP). A janela
-- comercial e a MESMA da 0020 e de src/domain/dashboard.py — manter em sincronia.

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC;

CREATE OR REPLACE FUNCTION private.horas_uteis_entre(p_inicio timestamptz, p_fim timestamptz)
RETURNS numeric
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    tz        CONSTANT text := 'America/Sao_Paulo';
    hora_ini  CONSTANT int  := 7;
    hora_fim  CONSTANT int  := 18;
    ini_l     timestamp;
    fim_l     timestamp;
    total     numeric := 0;
    dia       date;
    dow       int;
    janela_i  timestamp;
    janela_f  timestamp;
    seg_i     timestamp;
    seg_f     timestamp;
BEGIN
    IF p_inicio IS NULL OR p_fim IS NULL OR p_fim <= p_inicio THEN
        RETURN 0;
    END IF;

    ini_l := (p_inicio AT TIME ZONE tz);
    fim_l := (p_fim AT TIME ZONE tz);
    dia := ini_l::date;
    WHILE dia <= fim_l::date LOOP
        dow := EXTRACT(ISODOW FROM dia);
        IF dow <= 5 THEN
            janela_i := dia + make_interval(hours => hora_ini);
            janela_f := dia + make_interval(hours => hora_fim);
            seg_i := GREATEST(ini_l, janela_i);
            seg_f := LEAST(fim_l, janela_f);
            IF seg_f > seg_i THEN
                total := total + EXTRACT(EPOCH FROM (seg_f - seg_i)) / 3600.0;
            END IF;
        END IF;
        dia := dia + 1;
    END LOOP;
    RETURN total;
END;
$$;

REVOKE ALL ON FUNCTION private.horas_uteis_entre(timestamptz, timestamptz) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION private.horas_uteis_entre(timestamptz, timestamptz) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.horas_uteis_entre(timestamptz, timestamptz)
            TO authenticated;
    END IF;
END
$$;
