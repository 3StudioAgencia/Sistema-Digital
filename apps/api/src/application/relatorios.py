"""Casos de uso dos Relatorios gerenciais (W5-C17) — RF-016/US-014.

Fachada fina sobre o ``RelatoriosRepositoryPort`` (uma agregacao por aba — DP-6) +
a geracao do CSV (DP-5). Uma instancia por requisicao; a sessao por tras do repo
DEVE vir de ``abrir_sessao_rls``. Sem logica de negocio extra: as formulas vivem
no dominio/SQL — aqui so se orquestra a leitura e se SERIALIZA o que a aba mostra.

CSV (DP-5): exporta o dataset da ABA ativa preservando TODOS os campos exibidos e
respeitando os filtros ativos (o mesmo ``FiltrosRelatorio`` da agregacao). Formato
**UTF-8 com BOM + separador ``;``** (abre direto no Excel pt-BR, acentuacao e
colunas corretas — decisao DP-5). Numeros decimais com virgula (pt-BR). Os rotulos
de status/rota espelham os do front (``status-labels.ts``/``rota-labels.ts``) para
o CSV refletir o que esta na tela.
"""

import csv
import io
from collections.abc import Sequence
from datetime import date

from src.application.ports.relatorios_repository import RelatoriosRepositoryPort
from src.domain.provas import EstadoProva, Rota
from src.domain.relatorios import (
    AbaRelatorio,
    FatiaRota,
    FiltrosRelatorio,
    MetricaVendedor,
    RelatorioClicheria,
    RelatorioGeral,
    RelatorioStudio,
    RelatorioVendedores,
)

# Rotulos de UI (espelham apps/web/src/lib/provas/{status-labels,rota-labels}.ts) —
# o CSV reflete o texto exibido na tela (criterio §6.4 "preserva campos exibidos").
ROTULOS_STATUS: dict[EstadoProva, str] = {
    EstadoProva.CRIADA: "Criada",
    EstadoProva.ENCAMINHADA_PARA_LAMINACAO: "Encaminhada p/ laminação",
    EstadoProva.COM_MOTORISTA_IDA_LAMINACAO: "Com motorista — ida laminação",
    EstadoProva.LAMINACAO_CONCLUIDA: "Laminação concluída",
    EstadoProva.COM_MOTORISTA_VOLTA_LAMINACAO: "Com motorista — volta laminação",
    EstadoProva.DE_VOLTA_STUDIO_POS_LAMINACAO: "Na 3Studio (pós-laminação)",
    EstadoProva.RETIRADA_VENDEDOR: "Retirada",
    EstadoProva.ENCAMINHADA_PARA_VENDEDOR: "Encaminhada ao vendedor",
    EstadoProva.APROVADA_VENDEDOR: "Aprovada",
    EstadoProva.REPROVADA_VENDEDOR: "Reprovada",
    EstadoProva.DE_VOLTA_STUDIO: "Na 3Studio",
    EstadoProva.COM_MOTORISTA_ENTREGA_FINAL: "Com motorista — entrega final",
    EstadoProva.RECEBIDA_CLICHERIA: "Na clicheria",
    EstadoProva.CANCELADA: "Cancelada",
}
ROTULOS_ROTA: dict[Rota, str] = {
    Rota.MATRIZ: "Matriz",
    Rota.LAM_MATRIZ: "Lam. Matriz",
    Rota.FILIAL: "Filial",
    Rota.LAM_FILIAL: "Lam. Filial",
}
ROTULOS_LOCAL = {"matriz": "Matriz", "filial": "Filial"}


def _dec(valor: float | None) -> str:
    """Decimal pt-BR (virgula) ou "—" quando a metrica nao tem base."""
    if valor is None:
        return "—"
    return f"{valor:.1f}".replace(".", ",")


def _pct_de_total(parte: int, total: int) -> str:
    if total == 0:
        return "0,0%"
    return f"{100.0 * parte / total:.1f}".replace(".", ",") + "%"


def _periodo(filtros: FiltrosRelatorio) -> str:
    def fmt(d: date) -> str:
        return d.strftime("%d/%m/%Y")

    if filtros.de is not None and filtros.ate is not None:
        return f"{fmt(filtros.de)} a {fmt(filtros.ate)}"
    if filtros.de is not None:
        return f"a partir de {fmt(filtros.de)}"
    if filtros.ate is not None:
        return f"até {fmt(filtros.ate)}"
    return "Todo o período"


def _linhas_vendedores(metricas: Sequence[MetricaVendedor]) -> list[list[str]]:
    linhas = [
        [
            "Vendedor",
            "Local",
            "Volume",
            "Aprovadas",
            "Reprovadas",
            "Taxa reprov. (%)",
            "Tempo médio (h)",
            "Atrasadas",
        ]
    ]
    for m in metricas:
        linhas.append(
            [
                m.vendedor_nome or "—",
                ROTULOS_LOCAL.get(m.localizacao or "", "—"),
                str(m.volume),
                str(m.aprovadas),
                str(m.reprovadas),
                _dec(m.taxa_reprovacao),
                _dec(m.tempo_medio_horas),
                str(m.atrasadas),
            ]
        )
    return linhas


def _linhas_distribuicao(fatias: Sequence[FatiaRota], total: int) -> list[list[str]]:
    linhas = [["Rota", "Total", "Percentual"]]
    for f in fatias:
        linhas.append([ROTULOS_ROTA[f.rota], str(f.total), _pct_de_total(f.total, total)])
    return linhas


def _csv_geral(r: RelatorioGeral, filtros: FiltrosRelatorio) -> list[list[str]]:
    linhas: list[list[str]] = [
        ["Relatório", "Geral"],
        ["Período", _periodo(filtros)],
        ["Total geral", str(r.total_geral)],
        ["Tempo médio de aprovação (h)", _dec(r.tempo_medio_aprovacao_horas)],
        ["Taxa de reprovação (%)", _dec(r.taxa_reprovacao)],
        ["Ativas — aguardando vendedor", str(r.ativas_aguardando_vendedor)],
        ["Ativas — reprovadas", str(r.ativas_reprovadas)],
        [],
        ["Distribuição por rota"],
        *_linhas_distribuicao(r.distribuicao_rota, r.total_geral),
        [],
        ["Métricas por vendedor"],
        *_linhas_vendedores(r.metricas_por_vendedor),
        [],
        ["Provas atrasadas"],
        ["Requerimento", "Nome", "Cliente", "Vendedor", "Status", "Atraso (h)"],
    ]
    for p in r.provas_atrasadas:
        linhas.append(
            [
                p.requerimento,
                p.nome,
                p.cliente,
                p.vendedor_nome or "—",
                ROTULOS_STATUS.get(p.status, p.status.value),
                _dec(p.atraso_horas),
            ]
        )
    return linhas


def _csv_studio(r: RelatorioStudio, filtros: FiltrosRelatorio) -> list[list[str]]:
    linhas: list[list[str]] = [
        ["Relatório", "3Studio"],
        ["Período", _periodo(filtros)],
        ["Provas criadas", str(r.provas_criadas)],
        ["Média diária", _dec(r.media_diaria)],
        ["Reinícios de ciclo", str(r.reinicios_ciclo)],
        ["Devolvidas (reprovações)", str(r.devolvidas)],
        ["Cancelamentos", str(r.cancelamentos)],
        ["Reprovadas aguardando", str(r.reprovadas_aguardando)],
        ["Tempo até 1ª mov. (h)", _dec(r.tempo_ate_primeira_mov_horas)],
        [],
        ["Top motivos de cancelamento"],
        ["Motivo", "Total"],
    ]
    for mot in r.top_motivos_cancelamento:
        linhas.append([mot.motivo, str(mot.total)])
    return linhas


def _csv_vendedores(r: RelatorioVendedores, filtros: FiltrosRelatorio) -> list[list[str]]:
    return [
        ["Relatório", "Vendedores"],
        ["Período", _periodo(filtros)],
        ["Vendedores Filial", str(r.vendedores_filial)],
        ["Vendedores Matriz", str(r.vendedores_matriz)],
        ["Vendedores ativos no período", str(r.vendedores_ativos)],
        ["Provas atrasadas", str(r.atrasadas_total)],
        [],
        ["Detalhamento por vendedor"],
        *_linhas_vendedores(r.por_vendedor),
    ]


def _csv_clicheria(r: RelatorioClicheria, filtros: FiltrosRelatorio) -> list[list[str]]:
    total_recebidas = sum(f.total for f in r.distribuicao_origem)
    return [
        ["Relatório", "Clicheria"],
        ["Período", _periodo(filtros)],
        ["Tempo médio aguardando (h)", _dec(r.tempo_medio_aguardando_horas)],
        ["Recebidas no período", str(r.recebidas_no_periodo)],
        ["Em trânsito agora", str(r.em_transito_agora)],
        ["Origens (rotas distintas)", str(r.origens)],
        [],
        ["Provas recebidas por rota de origem"],
        *_linhas_distribuicao(r.distribuicao_origem, total_recebidas),
    ]


class RelatoriosService:
    def __init__(self, repo: RelatoriosRepositoryPort) -> None:
        self._repo = repo

    async def geral(self, filtros: FiltrosRelatorio) -> RelatorioGeral:
        return await self._repo.geral(filtros)

    async def studio(self, filtros: FiltrosRelatorio) -> RelatorioStudio:
        return await self._repo.studio(filtros)

    async def vendedores(self, filtros: FiltrosRelatorio) -> RelatorioVendedores:
        return await self._repo.vendedores(filtros)

    async def clicheria(self, filtros: FiltrosRelatorio) -> RelatorioClicheria:
        return await self._repo.clicheria(filtros)

    async def exportar_csv(self, aba: AbaRelatorio, filtros: FiltrosRelatorio) -> bytes:
        """CSV da aba ativa (DP-5), respeitando os filtros, em UTF-8 com BOM + ``;``.

        Reusa a MESMA agregacao da tela (mesmos numeros que o usuario ve). O BOM
        (``utf-8-sig``) + ``;`` faz o Excel pt-BR abrir com acentuacao e colunas
        corretas; ``\\r\\n`` e o EOL esperado pelo Excel."""
        if aba is AbaRelatorio.GERAL:
            linhas = _csv_geral(await self._repo.geral(filtros), filtros)
        elif aba is AbaRelatorio.STUDIO:
            linhas = _csv_studio(await self._repo.studio(filtros), filtros)
        elif aba is AbaRelatorio.VENDEDORES:
            linhas = _csv_vendedores(await self._repo.vendedores(filtros), filtros)
        else:
            linhas = _csv_clicheria(await self._repo.clicheria(filtros), filtros)

        buffer = io.StringIO()
        escritor = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        escritor.writerows(linhas)
        return buffer.getvalue().encode("utf-8-sig")


__all__ = ["ROTULOS_ROTA", "ROTULOS_STATUS", "RelatoriosService"]
