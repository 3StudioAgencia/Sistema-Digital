-- instante_limite_atraso.sql — funcao de HORAS UTEIS do Dashboard (W4-C16 / DP-4)
--
-- "Atrasada" (RN-008): prova ATIVA parada no mesmo status por mais que o delay
-- configurado (C09 ``delay_horas_uteis``, padrao 48), medido em HORAS UTEIS na
-- janela comercial FIXA seg-sex 07:00-18:00 (RNF-011), fuso America/Sao_Paulo,
-- feriados FORA de escopo. Como o decorrido e MONOTONICO no instante do ultimo
-- evento, basta um instante-limite L (recuar ``horas`` uteis a partir de ``agora``):
-- ``ultimo_evento <= L`` <=> atrasada. O Dashboard e o filtro "atrasada" do C07
-- chamam a funcao UMA vez por query (minimo de idas ao banco — RNF-020/022).
--
-- Funcao PURA (nao toca tabelas): STABLE, SECURITY INVOKER, SET search_path=''
-- (blindagem W1-A-004; so built-ins do pg_catalog). Schema ``private`` (NAO
-- exposto pela Data API/PostgREST). So ``authenticated`` recebe EXECUTE.
--
-- Idempotente. Espelho 1:1 da migration 0020 (reaplicar apos DROP). A janela
-- comercial e documentada em src/domain/dashboard.py — mantenha-as em sincronia.

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC;

CREATE OR REPLACE FUNCTION private.instante_limite_atraso(p_agora timestamptz, p_horas integer)
RETURNS timestamptz
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    tz        CONSTANT text := 'America/Sao_Paulo';
    hora_ini  CONSTANT int  := 7;
    hora_fim  CONSTANT int  := 18;
    restante  numeric := p_horas;
    cursor_l  timestamp;
    dia       date;
    dow       int;
    janela_i  timestamp;
    janela_f  timestamp;
    disp      numeric;
BEGIN
    IF p_horas IS NULL OR p_horas <= 0 THEN
        RETURN p_agora;
    END IF;

    cursor_l := (p_agora AT TIME ZONE tz);
    LOOP
        dia := cursor_l::date;
        dow := EXTRACT(ISODOW FROM dia);
        IF dow <= 5 THEN
            janela_i := dia + make_interval(hours => hora_ini);
            janela_f := dia + make_interval(hours => hora_fim);
            IF cursor_l <= janela_i THEN
                disp := 0;
            ELSIF cursor_l >= janela_f THEN
                disp := hora_fim - hora_ini;
                cursor_l := janela_f;
            ELSE
                disp := EXTRACT(EPOCH FROM (cursor_l - janela_i)) / 3600.0;
            END IF;

            IF disp >= restante THEN
                RETURN ((cursor_l - make_interval(secs => (restante * 3600.0)::double precision))
                        AT TIME ZONE tz);
            END IF;
            restante := restante - disp;
        END IF;
        cursor_l := (dia - 1) + make_interval(hours => hora_fim);
    END LOOP;
END;
$$;

REVOKE ALL ON FUNCTION private.instante_limite_atraso(timestamptz, integer) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION private.instante_limite_atraso(timestamptz, integer) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.instante_limite_atraso(timestamptz, integer)
            TO authenticated;
    END IF;
END
$$;
