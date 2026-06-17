"""horas_uteis_entre: horas UTEIS decorridas entre dois instantes (W5-C17)

Os Relatorios (C17) medem tempos em HORAS UTEIS — janela comercial FIXA seg-sex
07:00-18:00 (RNF-011), fuso America/Sao_Paulo, feriados FORA de escopo (igual ao
C16/DP-4). Onde o C16 inverteu o problema (``instante_limite_atraso`` recua um
limite a partir de "agora", para o predicado de "Atrasada"), o C17 precisa do
DURADO direto entre duas movimentacoes (chegada ao vendedor -> aprovacao;
criacao -> 1a mov; envio a clicheria -> recebimento). ``horas_uteis_entre(ini,
fim)`` soma a intersecao de ``[ini, fim]`` com cada janela comercial dos dias do
intervalo. Complementa a 0020 sem substitui-la — o predicado de atraso do C16
segue sendo reusado verbatim (consistencia — criterio §6.5).

Funcao PURA (nao toca tabelas): ``STABLE``, ``SECURITY INVOKER``, ``SET
search_path = ''`` (blindagem W1-A-004; so built-ins do pg_catalog). Vive no
schema ``private`` (NAO exposto pela Data API/PostgREST — advisors 0028/0029
limpos), como ``instante_limite_atraso`` (0020) e os resolvedores de nomes
(0011/0017). So ``authenticated`` recebe EXECUTE (privilegio minimo; ``anon`` nada).

Espelho 1:1 em ``migrations/rls/horas_uteis_entre.sql`` (DAT §2; reaplicar apos
DROP). A janela comercial (07-18, seg-sex, America/Sao_Paulo) e a MESMA da 0020
e das constantes de referencia em ``src/domain/dashboard.py`` — manter em sincronia.

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- funcao de horas uteis decorridas (espelho: horas_uteis_entre.sql) --------
_FUNCAO = """
CREATE OR REPLACE FUNCTION private.horas_uteis_entre(p_inicio timestamptz, p_fim timestamptz)
RETURNS numeric
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    -- Janela comercial FIXA (RNF-011 / DP-4); espelhada na 0020 e em domain/dashboard.py.
    tz        CONSTANT text := 'America/Sao_Paulo';
    hora_ini  CONSTANT int  := 7;
    hora_fim  CONSTANT int  := 18;
    ini_l     timestamp;              -- inicio em horario LOCAL (sem tz)
    fim_l     timestamp;              -- fim em horario LOCAL
    total     numeric := 0;           -- horas uteis acumuladas
    dia       date;
    dow       int;
    janela_i  timestamp;
    janela_f  timestamp;
    seg_i     timestamp;              -- inicio da intersecao do dia com a janela
    seg_f     timestamp;              -- fim da intersecao do dia com a janela
BEGIN
    -- Intervalo nulo/invertido: zero horas uteis (defensivo — nunca negativo).
    IF p_inicio IS NULL OR p_fim IS NULL OR p_fim <= p_inicio THEN
        RETURN 0;
    END IF;

    ini_l := (p_inicio AT TIME ZONE tz);  -- timestamptz -> timestamp local
    fim_l := (p_fim AT TIME ZONE tz);
    dia := ini_l::date;
    WHILE dia <= fim_l::date LOOP
        dow := EXTRACT(ISODOW FROM dia);     -- 1=Seg .. 7=Dom
        IF dow <= 5 THEN                     -- dia util
            janela_i := dia + make_interval(hours => hora_ini);  -- 07:00 local
            janela_f := dia + make_interval(hours => hora_fim);  -- 18:00 local
            -- intersecao de [ini_l, fim_l] com [janela_i, janela_f]
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
$$
"""
_REVOKE = "REVOKE ALL ON FUNCTION private.horas_uteis_entre(timestamptz, timestamptz) FROM PUBLIC"
_GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION private.horas_uteis_entre(timestamptz, timestamptz) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        -- USAGE no schema private ja foi concedido pela 0011; reidempotente aqui.
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.horas_uteis_entre(timestamptz, timestamptz)
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
    op.execute("DROP FUNCTION IF EXISTS private.horas_uteis_entre(timestamptz, timestamptz)")
