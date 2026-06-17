"""instante_limite_atraso: funcao de HORAS UTEIS para o Dashboard (W4-C16)

O Dashboard (C16) computa "Atrasada" (RN-008): uma prova ATIVA parada no mesmo
status por mais que o tempo configurado (C09 ``delay_horas_uteis``, padrao 48),
medido em HORAS UTEIS — janela comercial FIXA seg-sex 07:00-18:00 (RNF-011), fuso
America/Sao_Paulo, feriados FORA de escopo (DP-4).

Em vez de medir "horas uteis decorridas" por linha (caro), invertemos: como o
decorrido e MONOTONICO no instante do ultimo evento, existe UM instante-limite L
tal que ``ultimo_evento <= L`` <=> atrasada. ``private.instante_limite_atraso(agora,
horas)`` devolve esse L recuando ``horas`` uteis a partir de ``agora`` pela janela
comercial. O Dashboard e o filtro "atrasada" do C07 chamam a funcao UMA vez por
query (minimo de idas ao banco — DP/RNF-020/022): a query le o delay do
``system_settings``, computa L e conta/filtra numa unica consulta RLS-escopada.

Funcao PURA (nao toca tabelas): ``STABLE``, ``SECURITY INVOKER``, ``SET
search_path = ''`` (blindagem W1-A-004; so usa built-ins do pg_catalog, sempre no
path). Vive no schema ``private`` (NAO exposto pela Data API/PostgREST — sem vetor
de RPC; advisors 0028/0029 limpos), como os resolvedores de nomes (0011/0017). So
``authenticated`` recebe EXECUTE (privilegio minimo; ``anon`` nada).

Espelho 1:1 em ``migrations/rls/instante_limite_atraso.sql`` (DAT §2; reaplicar
apos DROP). A janela comercial (07-18, seg-sex, America/Sao_Paulo) e documentada em
``src/domain/dashboard.py`` (constantes de referencia) — mantenha-as em sincronia.

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- funcao de horas uteis (espelho: instante_limite_atraso.sql) --------------
_FUNCAO = """
CREATE OR REPLACE FUNCTION private.instante_limite_atraso(p_agora timestamptz, p_horas integer)
RETURNS timestamptz
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    -- Janela comercial FIXA (RNF-011 / DP-4); espelhada em domain/dashboard.py.
    tz        CONSTANT text := 'America/Sao_Paulo';
    hora_ini  CONSTANT int  := 7;
    hora_fim  CONSTANT int  := 18;
    restante  numeric := p_horas;     -- horas uteis ainda a recuar
    cursor_l  timestamp;              -- "agora" em horario LOCAL (sem tz)
    dia       date;
    dow       int;
    janela_i  timestamp;
    janela_f  timestamp;
    disp      numeric;                -- horas uteis disponiveis no dia ate o cursor
BEGIN
    -- Delay nulo/zero: nada a recuar (nada nunca "atrasa"; o cursor e o proprio agora).
    IF p_horas IS NULL OR p_horas <= 0 THEN
        RETURN p_agora;
    END IF;

    cursor_l := (p_agora AT TIME ZONE tz);  -- timestamptz -> timestamp local
    LOOP
        dia := cursor_l::date;
        dow := EXTRACT(ISODOW FROM dia);     -- 1=Seg .. 7=Dom
        IF dow <= 5 THEN                     -- dia util
            janela_i := dia + make_interval(hours => hora_ini);  -- 07:00 local
            janela_f := dia + make_interval(hours => hora_fim);  -- 18:00 local
            IF cursor_l <= janela_i THEN
                disp := 0;                   -- cursor antes do expediente: dia nao contribui
            ELSIF cursor_l >= janela_f THEN
                disp := hora_fim - hora_ini; -- dia cheio (11h); colapsa o cursor ao fim
                cursor_l := janela_f;
            ELSE
                disp := EXTRACT(EPOCH FROM (cursor_l - janela_i)) / 3600.0;
            END IF;

            IF disp >= restante THEN
                -- O limite cai DENTRO da janela de hoje: recua o que falta a partir do cursor.
                RETURN ((cursor_l - make_interval(secs => (restante * 3600.0)::double precision))
                        AT TIME ZONE tz);
            END IF;
            restante := restante - disp;
        END IF;
        -- Recua ao fim (18:00) do dia anterior; fins de semana sao pulados na proxima volta.
        cursor_l := (dia - 1) + make_interval(hours => hora_fim);
    END LOOP;
END;
$$
"""
_REVOKE = "REVOKE ALL ON FUNCTION private.instante_limite_atraso(timestamptz, integer) FROM PUBLIC"
_GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION private.instante_limite_atraso(timestamptz, integer) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        -- USAGE no schema private ja foi concedido pela 0011; reidempotente aqui.
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.instante_limite_atraso(timestamptz, integer)
            TO authenticated;
    END IF;
END
$$
"""


def upgrade() -> None:
    # O schema ``private`` ja existe (criado pela 0011); a guarda mantem a
    # migration robusta a aplicacao isolada.
    op.execute("CREATE SCHEMA IF NOT EXISTS private")
    op.execute(_FUNCAO)
    op.execute(_REVOKE)
    op.execute(_GRANT)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS private.instante_limite_atraso(timestamptz, integer)")
