"""Repositorio SQLAlchemy do Dashboard (W4-C16) — a CONSULTA UNICA de agregacao.

UMA ida ao banco (minimo de requisicoes — RNF-020/022) entrega TODOS os contadores
do painel + o breakdown de "Atrasadas" por vendedor + total. Roda na sessao
``abrir_sessao_rls`` (claims propagados): a RLS de ``provas``/``movimentacoes``
escopa cada subconsulta por perfil (Matriz §7) — vendedor so os seus numeros,
3Studio/Clicheria todas. NUNCA faz commit (leitura pura).

Tudo numa so consulta: o delay (C09) e lido inline do ``system_settings``, o
instante-limite de atraso vem de ``private.instante_limite_atraso`` (0020) e os
nomes do breakdown saem de ``private.nomes_de_vendedores`` (escopado — DP-7),
ordenado por contagem desc. Os subconjuntos de status (DP-2) vem do dominio
(``src/domain/dashboard.py``) — fonte unica revisavel do mapeamento contador->status.
"""

import json
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.db.atraso_sql import SQL_PREDICADO_ATRASADA
from src.application.ports.dashboard_repository import DashboardRepositoryPort
from src.domain.dashboard import (
    FUSO_COMERCIAL,
    STATUS_APROVADAS,
    STATUS_COM_VENDEDOR,
    STATUS_NA_CLICHERIA,
    AtrasadaVendedor,
    ContadoresDashboard,
)
from src.domain.provas import EstadoProva


def _in_sql(estados: Iterable[EstadoProva]) -> str:
    """Lista SQL de valores de status (enum -> literal). Seguro: valores de enum,
    nunca entrada do usuario."""
    return ", ".join(f"'{e.value}'" for e in estados)


# Consulta UNICA (RNF-022). Os IN-lists e o predicado de atraso sao montados de
# constantes de dominio (enum) — sem interpolacao de entrada do usuario. O unico
# parametro ligado e o fuso (``:tz``), reusado nas duas bordas do dia.
_SQL_CONTADORES = f"""WITH bordas AS (
    SELECT
        ((now() AT TIME ZONE :tz)::date::timestamp AT TIME ZONE :tz) AS dia_ini,
        (((now() AT TIME ZONE :tz)::date + 1)::timestamp AT TIME ZONE :tz) AS dia_fim
),
atrasadas AS (
    SELECT provas.vendedor_id AS vendedor_id, count(*) AS total
    FROM provas
    WHERE {SQL_PREDICADO_ATRASADA}
    GROUP BY provas.vendedor_id
),
nomes AS (
    SELECT id, nome
    FROM private.nomes_de_vendedores(ARRAY(SELECT vendedor_id FROM atrasadas)::uuid[])
)
SELECT
    (SELECT count(*) FROM provas, bordas
       WHERE provas.created_at >= bordas.dia_ini AND provas.created_at < bordas.dia_fim)
        AS criadas_hoje,
    (SELECT count(*) FROM provas WHERE provas.status IN ({_in_sql(STATUS_COM_VENDEDOR)}))
        AS com_vendedor,
    (SELECT count(*) FROM provas WHERE provas.status IN ({_in_sql(STATUS_APROVADAS)}))
        AS aprovadas,
    (SELECT count(*) FROM provas WHERE provas.status IN ({_in_sql(STATUS_NA_CLICHERIA)}))
        AS na_clicheria,
    COALESCE((SELECT sum(total) FROM atrasadas), 0) AS atrasadas_total,
    COALESCE((
        SELECT json_agg(
            json_build_object(
                'vendedor_id', a.vendedor_id,
                'vendedor_nome', n.nome,
                'total', a.total
            ) ORDER BY a.total DESC, n.nome ASC NULLS LAST
        )
        FROM atrasadas a
        LEFT JOIN nomes n ON n.id = a.vendedor_id
    ), '[]'::json) AS atrasadas_por_vendedor
"""  # noqa: S608 — interpolação só de constantes de enum do domínio (sem entrada do usuário)


class SqlAlchemyDashboardRepository(DashboardRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def contadores(self) -> ContadoresDashboard:
        stmt = text(_SQL_CONTADORES).bindparams(tz=FUSO_COMERCIAL)
        row = (await self._session.execute(stmt)).one()
        # asyncpg devolve json como texto cru — desserializa de forma defensiva.
        breakdown_raw = row.atrasadas_por_vendedor
        breakdown = json.loads(breakdown_raw) if isinstance(breakdown_raw, str) else breakdown_raw
        atrasadas = tuple(
            AtrasadaVendedor(
                vendedor_id=str(item["vendedor_id"]),
                vendedor_nome=item.get("vendedor_nome"),
                total=int(item["total"]),
            )
            for item in breakdown
        )
        return ContadoresDashboard(
            criadas_hoje=int(row.criadas_hoje),
            com_vendedor=int(row.com_vendedor),
            aprovadas=int(row.aprovadas),
            na_clicheria=int(row.na_clicheria),
            atrasadas_total=int(row.atrasadas_total),
            atrasadas_por_vendedor=atrasadas,
        )


__all__ = ["SqlAlchemyDashboardRepository"]
