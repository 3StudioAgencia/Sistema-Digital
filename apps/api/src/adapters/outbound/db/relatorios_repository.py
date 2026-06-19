"""Repositorio SQLAlchemy dos Relatorios (W5-C17) — agregacao server-side por aba.

Uma agregacao por ABA (DP-6), cada uma em POUCAS consultas SET-BASED (sem N+1 —
RNF-022), sob a sessao ``abrir_sessao_rls``. Relatorios e "Exclusivo 3Studio"
(flag admin) e o admin enxerga tudo (Matriz §7), entao a RLS de ``provas``/
``usuarios`` nao restringe na pratica — mas a sessao escopada e mantida por
consistencia/defesa em profundidade, e o JOIN direto a ``usuarios`` (nome/
localizacao) e seguro porque o ator e sempre admin.

Reuso (nao reinventa — restricao §3.1):
- "Atrasada" reusa ``SQL_PREDICADO_ATRASADA``/``SQL_ULTIMO_EVENTO`` do C16 VERBATIM
  (consistencia com o Dashboard — criterio §6.5);
- tempos em HORAS UTEIS via ``private.horas_uteis_entre`` (0021) + ``instante_limite_atraso``
  (0020) — janela comercial unica (RNF-011).

Seguranca do SQL: os fragmentos de filtro interpolam SO valores de enum VALIDADOS
(status/rota — FastAPI ja os converteu a ``EstadoProva``/``Rota``) e nunca entrada
crua; busca/datas/uuid do usuario entram como BIND params (``:busca`` etc.). Por
isso o ``# noqa: S608``: a f-string nao concatena entrada do usuario.
"""

from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.db.atraso_sql import SQL_PREDICADO_ATRASADA, SQL_ULTIMO_EVENTO
from src.application.ports.relatorios_repository import RelatoriosRepositoryPort
from src.domain.provas import EstadoProva, Rota
from src.domain.relatorios import (
    ROTAS_ORDEM,
    FatiaRota,
    FiltrosRelatorio,
    MetricaVendedor,
    MotivoCancelamento,
    PontoVolume,
    ProvaAtrasada,
    RelatorioClicheria,
    RelatorioGeral,
    RelatorioStudio,
    RelatorioVendedores,
    dias_no_periodo,
)

# Estados de "chegada ao vendedor" (ancora do tempo medio de aprovacao — DP-3).
_CHEGADA_VENDEDOR = "('retirada_vendedor', 'encaminhada_para_vendedor')"

# Horas uteis da chegada ao vendedor (a chegada mais recente <= a aprovacao —
# cobre reinicios de ciclo) ate a aprovacao ``m``; NULL se nao houver chegada
# registrada (a media ignora NULLs). String LITERAL (sem f-string): nao concatena
# entrada do usuario, so a tabela FIXA de estados — por isso nao dispara S608.
_HORAS_APROVACAO = (
    "private.horas_uteis_entre("
    "(SELECT max(c.created_at) FROM movimentacoes c "
    "WHERE c.prova_id = m.prova_id "
    "AND c.estado_destino IN ('retirada_vendedor', 'encaminhada_para_vendedor') "
    "AND c.created_at <= m.created_at), m.created_at)"
)

_LIMITE_TOP_MOTIVOS = 10


def _escapar_like(termo: str) -> str:
    r"""Escapa curingas do LIKE — busca por texto literal (igual ao C07)."""
    return termo.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def _enum_in(valores: Iterable[EstadoProva | Rota]) -> str:
    """Lista SQL de valores de enum (validados pelo FastAPI) — nunca entrada crua."""
    return ", ".join(f"'{v.value}'" for v in valores)


def _num(valor: object) -> float | None:
    """Converte um numeric/Decimal do Postgres em float arredondado (1 casa), ou
    ``None`` quando a media nao tem base (sem aprovacoes/decisoes)."""
    if valor is None:
        return None
    if isinstance(valor, Decimal | float | int):
        return round(float(valor), 1)
    return None


def _clausula_base(filtros: FiltrosRelatorio) -> tuple[str, dict[str, object]]:
    """WHERE compartilhado (DP-4), referenciando a tabela ``provas`` SEM alias.

    Periodo recorta por ``created_at`` (dia UTC inclusivo nos dois extremos —
    mesma convencao do C07). ``status``/``rotas`` interpolam enum VALIDADO; busca/
    datas/uuid entram como bind. Devolve ("TRUE", {}) quando nao ha filtro."""
    conds: list[str] = []
    params: dict[str, object] = {}
    if filtros.busca:
        conds.append(
            "(provas.nome ILIKE :busca ESCAPE '\\' OR provas.requerimento ILIKE :busca ESCAPE '\\')"
        )
        params["busca"] = f"%{_escapar_like(filtros.busca)}%"
    if filtros.status:
        conds.append(f"provas.status IN ({_enum_in(filtros.status)})")
    if filtros.rotas:
        conds.append(f"provas.rota IN ({_enum_in(filtros.rotas)})")
    if filtros.vendedor_id:
        # CAST(... AS ...) em vez de ``:param::tipo``: o ``::`` logo apos um bind
        # confunde o parser de ``text()`` (ele leria ``:de`` + um 2o bind ``:date``).
        conds.append("provas.vendedor_id = CAST(:vendedor_id AS uuid)")
        params["vendedor_id"] = filtros.vendedor_id
    if filtros.de is not None:
        conds.append("provas.created_at >= CAST(:de AS date)")
        params["de"] = filtros.de
    if filtros.ate is not None:
        conds.append("provas.created_at < (CAST(:ate AS date) + INTERVAL '1 day')")
        params["ate"] = filtros.ate
    return (" AND ".join(conds) if conds else "TRUE"), params


def _zerar_rotas(contagens: dict[str, int]) -> tuple[FatiaRota, ...]:
    """Distribuicao com as 4 rotas SEMPRE presentes (zero-fill) — a soma fecha o
    total da base (criterio §6.3: 100% no periodo)."""
    return tuple(FatiaRota(rota=r, total=contagens.get(r.value, 0)) for r in ROTAS_ORDEM)


class SqlAlchemyRelatoriosRepository(RelatoriosRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- por vendedor (reusado por Geral "Metricas" e Vendedores "Detalhamento")
    async def _metricas_por_vendedor(
        self, where: str, params: dict[str, object]
    ) -> tuple[MetricaVendedor, ...]:
        sql = f"""WITH vol AS (
            SELECT provas.vendedor_id AS vid, count(*) AS volume
            FROM provas WHERE ({where}) GROUP BY provas.vendedor_id
        ),
        ev AS (
            SELECT provas.vendedor_id AS vid,
                count(*) FILTER (WHERE m.acao = 'aprovar') AS aprovadas,
                count(*) FILTER (WHERE m.acao = 'reprovar') AS reprovadas,
                avg(CASE WHEN m.acao = 'aprovar' THEN {_HORAS_APROVACAO} END) AS tempo_medio
            FROM movimentacoes m JOIN provas ON provas.id = m.prova_id
            WHERE ({where}) AND m.acao IN ('aprovar', 'reprovar')
            GROUP BY provas.vendedor_id
        ),
        atr AS (
            SELECT provas.vendedor_id AS vid, count(*) AS atrasadas
            FROM provas WHERE ({where}) AND ({SQL_PREDICADO_ATRASADA})
            GROUP BY provas.vendedor_id
        )
        SELECT vol.vid, u.nome AS nome, u.localizacao AS localizacao, vol.volume,
               COALESCE(ev.aprovadas, 0) AS aprovadas,
               COALESCE(ev.reprovadas, 0) AS reprovadas,
               ev.tempo_medio AS tempo_medio,
               COALESCE(atr.atrasadas, 0) AS atrasadas
        FROM vol
        LEFT JOIN ev ON ev.vid = vol.vid
        LEFT JOIN atr ON atr.vid = vol.vid
        LEFT JOIN usuarios u ON u.id = vol.vid
        ORDER BY vol.volume DESC, u.nome ASC NULLS LAST"""  # noqa: S608
        rows = (await self._session.execute(text(sql), params)).all()
        return tuple(
            MetricaVendedor(
                vendedor_id=str(r.vid),
                vendedor_nome=r.nome,
                localizacao=r.localizacao,
                volume=int(r.volume),
                aprovadas=int(r.aprovadas),
                reprovadas=int(r.reprovadas),
                taxa_reprovacao=_taxa(int(r.aprovadas), int(r.reprovadas)),
                tempo_medio_horas=_num(r.tempo_medio),
                atrasadas=int(r.atrasadas),
            )
            for r in rows
        )

    async def geral(self, filtros: FiltrosRelatorio) -> RelatorioGeral:
        where, params = _clausula_base(filtros)

        escalares = f"""SELECT
            (SELECT count(*) FROM provas WHERE ({where})) AS total_geral,
            (SELECT count(*) FROM provas WHERE ({where})
                AND provas.status IN {_CHEGADA_VENDEDOR}) AS aguardando,
            (SELECT count(*) FROM provas WHERE ({where})
                AND provas.status = 'reprovada_vendedor') AS reprovadas_ativas,
            (SELECT count(*) FROM provas WHERE ({where}) AND provas.rota = 'matriz') AS r_matriz,
            (SELECT count(*) FROM provas WHERE ({where})
                AND provas.rota = 'lam_matriz') AS r_lam_matriz,
            (SELECT count(*) FROM provas WHERE ({where}) AND provas.rota = 'filial') AS r_filial,
            (SELECT count(*) FROM provas WHERE ({where})
                AND provas.rota = 'lam_filial') AS r_lam_filial,
            (SELECT count(*) FROM movimentacoes m JOIN provas ON provas.id = m.prova_id
                WHERE ({where}) AND m.acao = 'aprovar') AS ev_aprovadas,
            (SELECT count(*) FROM movimentacoes m JOIN provas ON provas.id = m.prova_id
                WHERE ({where}) AND m.acao = 'reprovar') AS ev_reprovadas,
            (SELECT avg({_HORAS_APROVACAO})
                FROM movimentacoes m JOIN provas ON provas.id = m.prova_id
                WHERE ({where}) AND m.acao = 'aprovar') AS tempo_medio"""  # noqa: S608
        e = (await self._session.execute(text(escalares), params)).one()

        volume_sql = (
            "SELECT provas.created_at::date AS dia, count(*) AS total "  # noqa: S608
            f"FROM provas WHERE ({where}) GROUP BY 1 ORDER BY 1"
        )
        vol_rows = (await self._session.execute(text(volume_sql), params)).all()

        atrasadas_sql = f"""SELECT provas.id, provas.nome, provas.requerimento, provas.cliente,
            provas.vendedor_id, u.nome AS vendedor_nome, provas.status,
            private.horas_uteis_entre({SQL_ULTIMO_EVENTO}, now()) AS atraso_horas
        FROM provas LEFT JOIN usuarios u ON u.id = provas.vendedor_id
        WHERE ({where}) AND ({SQL_PREDICADO_ATRASADA})
        ORDER BY atraso_horas DESC, provas.created_at ASC"""  # noqa: S608
        atr_rows = (await self._session.execute(text(atrasadas_sql), params)).all()

        por_vendedor = await self._metricas_por_vendedor(where, params)

        return RelatorioGeral(
            total_geral=int(e.total_geral),
            volume=tuple(PontoVolume(dia=r.dia, total=int(r.total)) for r in vol_rows),
            tempo_medio_aprovacao_horas=_num(e.tempo_medio),
            taxa_reprovacao=_taxa(int(e.ev_aprovadas), int(e.ev_reprovadas)),
            distribuicao_rota=_zerar_rotas(
                {
                    Rota.MATRIZ.value: int(e.r_matriz),
                    Rota.LAM_MATRIZ.value: int(e.r_lam_matriz),
                    Rota.FILIAL.value: int(e.r_filial),
                    Rota.LAM_FILIAL.value: int(e.r_lam_filial),
                }
            ),
            ativas_aguardando_vendedor=int(e.aguardando),
            ativas_reprovadas=int(e.reprovadas_ativas),
            metricas_por_vendedor=por_vendedor,
            provas_atrasadas=tuple(
                ProvaAtrasada(
                    id=str(r.id),
                    nome=r.nome,
                    requerimento=r.requerimento,
                    cliente=r.cliente,
                    vendedor_id=str(r.vendedor_id),
                    vendedor_nome=r.vendedor_nome,
                    status=EstadoProva(r.status),
                    atraso_horas=round(float(r.atraso_horas), 1),
                )
                for r in atr_rows
            ),
        )

    async def studio(self, filtros: FiltrosRelatorio) -> RelatorioStudio:
        where, params = _clausula_base(filtros)
        escalares = f"""SELECT
            (SELECT count(*) FROM provas WHERE ({where})) AS provas_criadas,
            (SELECT count(*) FROM movimentacoes m JOIN provas ON provas.id = m.prova_id
                WHERE ({where}) AND m.acao = 'reiniciar_ciclo') AS reinicios,
            (SELECT count(*) FROM movimentacoes m JOIN provas ON provas.id = m.prova_id
                WHERE ({where}) AND m.acao = 'reprovar') AS devolvidas,
            (SELECT count(*) FROM movimentacoes m JOIN provas ON provas.id = m.prova_id
                WHERE ({where}) AND m.acao = 'cancelar') AS cancelamentos,
            (SELECT count(*) FROM provas WHERE ({where})
                AND provas.status = 'reprovada_vendedor') AS reprovadas_aguardando,
            (SELECT avg(private.horas_uteis_entre(provas.created_at,
                    (SELECT min(m.created_at) FROM movimentacoes m WHERE m.prova_id = provas.id)))
                FROM provas WHERE ({where})
                AND EXISTS (SELECT 1 FROM movimentacoes m WHERE m.prova_id = provas.id)
            ) AS tempo_1a_mov"""  # noqa: S608
        e = (await self._session.execute(text(escalares), params)).one()

        motivos_sql = f"""SELECT m.motivo AS motivo, count(*) AS total
            FROM movimentacoes m JOIN provas ON provas.id = m.prova_id
            WHERE ({where}) AND m.acao = 'cancelar'
                AND m.motivo IS NOT NULL AND btrim(m.motivo) <> ''
            GROUP BY m.motivo ORDER BY total DESC, m.motivo ASC
            LIMIT {_LIMITE_TOP_MOTIVOS}"""  # noqa: S608
        mot_rows = (await self._session.execute(text(motivos_sql), params)).all()

        # Serie diaria de provas criadas (grafico de barras do card "Provas Criadas").
        volume_sql = (
            "SELECT provas.created_at::date AS dia, count(*) AS total "  # noqa: S608
            f"FROM provas WHERE ({where}) GROUP BY 1 ORDER BY 1"
        )
        vol_rows = (await self._session.execute(text(volume_sql), params)).all()

        return RelatorioStudio(
            provas_criadas=int(e.provas_criadas),
            media_diaria=round(int(e.provas_criadas) / dias_no_periodo(filtros.de, filtros.ate), 2),
            reinicios_ciclo=int(e.reinicios),
            devolvidas=int(e.devolvidas),
            cancelamentos=int(e.cancelamentos),
            reprovadas_aguardando=int(e.reprovadas_aguardando),
            tempo_ate_primeira_mov_horas=_num(e.tempo_1a_mov),
            top_motivos_cancelamento=tuple(
                MotivoCancelamento(motivo=r.motivo, total=int(r.total)) for r in mot_rows
            ),
            volume=tuple(PontoVolume(dia=r.dia, total=int(r.total)) for r in vol_rows),
        )

    async def vendedores(self, filtros: FiltrosRelatorio) -> RelatorioVendedores:
        where, params = _clausula_base(filtros)
        cadastro = """SELECT
            count(*) FILTER (WHERE localizacao = 'filial') AS filial,
            count(*) FILTER (WHERE localizacao = 'matriz') AS matriz
            FROM usuarios WHERE setor = 'vendedor' AND ativo"""
        c = (await self._session.execute(text(cadastro))).one()

        agregados = f"""SELECT
            (SELECT count(*) FROM provas WHERE ({where})) AS provas_criadas,
            (SELECT count(DISTINCT provas.vendedor_id) FROM provas WHERE ({where})) AS ativos,
            (SELECT count(*) FROM provas WHERE ({where})
                AND ({SQL_PREDICADO_ATRASADA})) AS atrasadas_total"""  # noqa: S608
        a = (await self._session.execute(text(agregados), params)).one()

        volume_sql = (
            "SELECT provas.created_at::date AS dia, count(*) AS total "  # noqa: S608
            f"FROM provas WHERE ({where}) GROUP BY 1 ORDER BY 1"
        )
        vol_rows = (await self._session.execute(text(volume_sql), params)).all()

        por_vendedor = await self._metricas_por_vendedor(where, params)
        return RelatorioVendedores(
            vendedores_filial=int(c.filial),
            vendedores_matriz=int(c.matriz),
            vendedores_ativos=int(a.ativos),
            atrasadas_total=int(a.atrasadas_total),
            por_vendedor=por_vendedor,
            provas_criadas=int(a.provas_criadas),
            volume=tuple(PontoVolume(dia=r.dia, total=int(r.total)) for r in vol_rows),
        )

    async def clicheria(self, filtros: FiltrosRelatorio) -> RelatorioClicheria:
        where, params = _clausula_base(filtros)
        escalares = f"""SELECT
            (SELECT count(*) FROM provas WHERE ({where})
                AND provas.status = 'recebida_clicheria') AS recebidas,
            (SELECT count(*) FROM provas WHERE ({where})
                AND provas.status = 'com_motorista_entrega_final') AS em_transito,
            (SELECT count(DISTINCT provas.rota) FROM provas WHERE ({where})
                AND provas.status = 'recebida_clicheria') AS origens,
            (SELECT avg(private.horas_uteis_entre(
                    (SELECT max(m.created_at) FROM movimentacoes m
                        WHERE m.prova_id = provas.id
                        AND m.estado_destino = 'com_motorista_entrega_final'),
                    (SELECT max(m2.created_at) FROM movimentacoes m2
                        WHERE m2.prova_id = provas.id
                        AND m2.estado_destino = 'recebida_clicheria')))
                FROM provas WHERE ({where}) AND provas.status = 'recebida_clicheria'
                AND EXISTS (SELECT 1 FROM movimentacoes m WHERE m.prova_id = provas.id
                    AND m.estado_destino = 'com_motorista_entrega_final')
            ) AS tempo_aguardando"""  # noqa: S608
        e = (await self._session.execute(text(escalares), params)).one()

        origem_sql = (
            "SELECT provas.rota AS rota, count(*) AS total FROM provas "  # noqa: S608
            f"WHERE ({where}) AND provas.status = 'recebida_clicheria' GROUP BY provas.rota"
        )
        o_rows = (await self._session.execute(text(origem_sql), params)).all()

        volume_sql = (
            "SELECT provas.created_at::date AS dia, count(*) AS total "  # noqa: S608
            f"FROM provas WHERE ({where}) GROUP BY 1 ORDER BY 1"
        )
        vol_rows = (await self._session.execute(text(volume_sql), params)).all()

        return RelatorioClicheria(
            tempo_medio_aguardando_horas=_num(e.tempo_aguardando),
            recebidas_no_periodo=int(e.recebidas),
            em_transito_agora=int(e.em_transito),
            origens=int(e.origens),
            distribuicao_origem=_zerar_rotas({str(r.rota): int(r.total) for r in o_rows}),
            volume=tuple(PontoVolume(dia=r.dia, total=int(r.total)) for r in vol_rows),
        )


def _taxa(aprovadas: int, reprovadas: int) -> float | None:
    """Taxa de reprovacao = reprovadas / (aprovadas + reprovadas) (DP-3) em %, 1
    casa. ``None`` quando nao houve decisao (denominador 0 — a UI mostra "—")."""
    denom = aprovadas + reprovadas
    if denom == 0:
        return None
    return round(100.0 * reprovadas / denom, 1)


__all__ = ["SqlAlchemyRelatoriosRepository"]
