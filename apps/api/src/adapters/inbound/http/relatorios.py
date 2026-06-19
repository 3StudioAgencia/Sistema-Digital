"""Endpoints de Relatórios gerenciais (W5-C17) — RF-016/US-014.

Exclusivo do 3Studio (flag ``administrador`` — Matriz §7/§7 "Relatórios" ●○○○):
TODOS os endpoints (4 abas + export CSV) passam por ``get_relatorios_service``, que
gateia por ``Recurso.RELATORIOS`` → 403 ao não-admin (camada inferior; a superior é
o ``proxy.ts`` + sidebar — DP-7). Prefixo real ``/relatorios`` (SEM ``/api``).

Cada aba é uma agregação server-side independente, computada SÓ quando pedida
(lazy — o front busca uma aba por vez; DP-6). A barra de filtros é compartilhada
(``filtros_relatorio`` — DP-4): período (De/Até por ``created_at``), status (multi),
rota (multi — o toggle 2-vias do front expande Matriz→{matriz, lam_matriz} /
Filial→{filial, lam_filial}), busca (nome/requerimento) e vendedor. SEM Realtime
(snapshot do período — §2): a tela recomputa na troca de filtro/aba.
"""

import uuid
from datetime import date
from typing import Annotated, Self

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from src.adapters.inbound.http.dependencies import get_relatorios_service
from src.application.relatorios import RelatoriosService
from src.domain.provas import EstadoProva, Rota
from src.domain.relatorios import (
    AbaRelatorio,
    FatiaRota,
    FiltrosRelatorio,
    MetricaVendedor,
    ProvaAtrasada,
    RelatorioClicheria,
    RelatorioGeral,
    RelatorioStudio,
    RelatorioVendedores,
)

router = APIRouter(prefix="/relatorios", tags=["relatorios"])


def filtros_relatorio(
    de: date | None = None,
    ate: date | None = None,
    status_filtro: Annotated[list[EstadoProva] | None, Query(alias="status")] = None,
    rota: Annotated[list[Rota] | None, Query()] = None,
    busca: Annotated[str | None, Query(max_length=200)] = None,
    vendedor_id: uuid.UUID | None = None,
) -> FiltrosRelatorio:
    """Barra de filtros compartilhada (DP-4) → ``FiltrosRelatorio``.

    ``status`` e ``rota`` aceitam MÚLTIPLOS valores (``?status=a&status=b``); o front
    manda as rotas agrupadas pelo toggle 2-vias. Período por dia (De/Até)."""
    return FiltrosRelatorio(
        de=de,
        ate=ate,
        status=tuple(status_filtro) if status_filtro else (),
        rotas=tuple(rota) if rota else (),
        busca=busca,
        vendedor_id=str(vendedor_id) if vendedor_id is not None else None,
    )


Filtros = Annotated[FiltrosRelatorio, Depends(filtros_relatorio)]
Service = Annotated[RelatoriosService, Depends(get_relatorios_service)]


# ---------------------------------------------------------------------------
# Schemas (espelham os dataclasses do domínio)
# ---------------------------------------------------------------------------
class FatiaRotaOut(BaseModel):
    rota: Rota
    total: int

    @classmethod
    def de_dominio(cls, f: FatiaRota) -> Self:
        return cls(rota=f.rota, total=f.total)


class PontoVolumeOut(BaseModel):
    dia: date
    total: int


class MetricaVendedorOut(BaseModel):
    vendedor_id: str
    vendedor_nome: str | None
    localizacao: str | None
    volume: int
    aprovadas: int
    reprovadas: int
    taxa_reprovacao: float | None
    tempo_medio_horas: float | None
    atrasadas: int

    @classmethod
    def de_dominio(cls, m: MetricaVendedor) -> Self:
        return cls(
            vendedor_id=m.vendedor_id,
            vendedor_nome=m.vendedor_nome,
            localizacao=m.localizacao,
            volume=m.volume,
            aprovadas=m.aprovadas,
            reprovadas=m.reprovadas,
            taxa_reprovacao=m.taxa_reprovacao,
            tempo_medio_horas=m.tempo_medio_horas,
            atrasadas=m.atrasadas,
        )


class ProvaAtrasadaOut(BaseModel):
    id: str
    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    vendedor_nome: str | None
    status: EstadoProva
    atraso_horas: float

    @classmethod
    def de_dominio(cls, p: ProvaAtrasada) -> Self:
        return cls(
            id=p.id,
            nome=p.nome,
            requerimento=p.requerimento,
            cliente=p.cliente,
            vendedor_id=p.vendedor_id,
            vendedor_nome=p.vendedor_nome,
            status=p.status,
            atraso_horas=p.atraso_horas,
        )


class MotivoCancelamentoOut(BaseModel):
    motivo: str
    total: int


class RelatorioGeralOut(BaseModel):
    total_geral: int
    volume: list[PontoVolumeOut]
    tempo_medio_aprovacao_horas: float | None
    taxa_reprovacao: float | None
    distribuicao_rota: list[FatiaRotaOut]
    ativas_aguardando_vendedor: int
    ativas_reprovadas: int
    metricas_por_vendedor: list[MetricaVendedorOut]
    provas_atrasadas: list[ProvaAtrasadaOut]

    @classmethod
    def de_dominio(cls, r: RelatorioGeral) -> Self:
        return cls(
            total_geral=r.total_geral,
            volume=[PontoVolumeOut(dia=p.dia, total=p.total) for p in r.volume],
            tempo_medio_aprovacao_horas=r.tempo_medio_aprovacao_horas,
            taxa_reprovacao=r.taxa_reprovacao,
            distribuicao_rota=[FatiaRotaOut.de_dominio(f) for f in r.distribuicao_rota],
            ativas_aguardando_vendedor=r.ativas_aguardando_vendedor,
            ativas_reprovadas=r.ativas_reprovadas,
            metricas_por_vendedor=[
                MetricaVendedorOut.de_dominio(m) for m in r.metricas_por_vendedor
            ],
            provas_atrasadas=[ProvaAtrasadaOut.de_dominio(p) for p in r.provas_atrasadas],
        )


class RelatorioStudioOut(BaseModel):
    provas_criadas: int
    media_diaria: float
    reinicios_ciclo: int
    devolvidas: int
    cancelamentos: int
    reprovadas_aguardando: int
    tempo_ate_primeira_mov_horas: float | None
    top_motivos_cancelamento: list[MotivoCancelamentoOut]
    volume: list[PontoVolumeOut]

    @classmethod
    def de_dominio(cls, r: RelatorioStudio) -> Self:
        return cls(
            provas_criadas=r.provas_criadas,
            media_diaria=r.media_diaria,
            reinicios_ciclo=r.reinicios_ciclo,
            devolvidas=r.devolvidas,
            cancelamentos=r.cancelamentos,
            reprovadas_aguardando=r.reprovadas_aguardando,
            tempo_ate_primeira_mov_horas=r.tempo_ate_primeira_mov_horas,
            top_motivos_cancelamento=[
                MotivoCancelamentoOut(motivo=m.motivo, total=m.total)
                for m in r.top_motivos_cancelamento
            ],
            volume=[PontoVolumeOut(dia=p.dia, total=p.total) for p in r.volume],
        )


class RelatorioVendedoresOut(BaseModel):
    vendedores_filial: int
    vendedores_matriz: int
    vendedores_ativos: int
    atrasadas_total: int
    por_vendedor: list[MetricaVendedorOut]
    provas_criadas: int
    volume: list[PontoVolumeOut]

    @classmethod
    def de_dominio(cls, r: RelatorioVendedores) -> Self:
        return cls(
            vendedores_filial=r.vendedores_filial,
            vendedores_matriz=r.vendedores_matriz,
            vendedores_ativos=r.vendedores_ativos,
            atrasadas_total=r.atrasadas_total,
            por_vendedor=[MetricaVendedorOut.de_dominio(m) for m in r.por_vendedor],
            provas_criadas=r.provas_criadas,
            volume=[PontoVolumeOut(dia=p.dia, total=p.total) for p in r.volume],
        )


class RelatorioClicheriaOut(BaseModel):
    tempo_medio_aguardando_horas: float | None
    recebidas_no_periodo: int
    em_transito_agora: int
    origens: int
    distribuicao_origem: list[FatiaRotaOut]
    volume: list[PontoVolumeOut]

    @classmethod
    def de_dominio(cls, r: RelatorioClicheria) -> Self:
        return cls(
            tempo_medio_aguardando_horas=r.tempo_medio_aguardando_horas,
            recebidas_no_periodo=r.recebidas_no_periodo,
            em_transito_agora=r.em_transito_agora,
            origens=r.origens,
            distribuicao_origem=[FatiaRotaOut.de_dominio(f) for f in r.distribuicao_origem],
            volume=[PontoVolumeOut(dia=p.dia, total=p.total) for p in r.volume],
        )


# ---------------------------------------------------------------------------
# Endpoints — uma agregação por aba (lazy), todos 3Studio-only (gate no service)
# ---------------------------------------------------------------------------
@router.get("/geral", response_model=RelatorioGeralOut)
async def geral(service: Service, filtros: Filtros) -> RelatorioGeralOut:
    """Aba Geral (§0.2): RF-016 (total, tempo médio, taxa, distribuição por rota,
    atrasadas, por vendedor) + extras do design."""
    return RelatorioGeralOut.de_dominio(await service.geral(filtros))


@router.get("/studio", response_model=RelatorioStudioOut)
async def studio(service: Service, filtros: Filtros) -> RelatorioStudioOut:
    """Aba 3Studio (§0.2): diagnóstico da operação do studio no período."""
    return RelatorioStudioOut.de_dominio(await service.studio(filtros))


@router.get("/vendedores", response_model=RelatorioVendedoresOut)
async def vendedores(service: Service, filtros: Filtros) -> RelatorioVendedoresOut:
    """Aba Vendedores (§0.2): ranking e detalhamento por vendedor."""
    return RelatorioVendedoresOut.de_dominio(await service.vendedores(filtros))


@router.get("/clicheria", response_model=RelatorioClicheriaOut)
async def clicheria(service: Service, filtros: Filtros) -> RelatorioClicheriaOut:
    """Aba Clicheria (§0.2): ótica de quem recebe a prova no fim do fluxo."""
    return RelatorioClicheriaOut.de_dominio(await service.clicheria(filtros))


@router.get("/exportar")
async def exportar(
    service: Service,
    filtros: Filtros,
    aba: AbaRelatorio = AbaRelatorio.GERAL,
) -> Response:
    """Exporta o dataset da ABA ativa em CSV (DP-5), preservando todos os campos
    exibidos e respeitando os filtros ativos. Exclusivo 3Studio (gate no service).

    UTF-8 com BOM + separador ``;`` (Excel pt-BR). O caret do botão escolhe a aba
    (``?aba=geral|studio|vendedores|clicheria``)."""
    conteudo = await service.exportar_csv(aba, filtros)
    return Response(
        content=conteudo,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="relatorio-{aba.value}.csv"'},
    )


__all__ = ["router"]
