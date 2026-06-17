"""Unidade dos Relatorios (W5-C17) — logica PURA offline (sem Postgres).

Cobre a parte que nao depende do banco: a montagem do CSV (DP-5 — preserva os
campos exibidos, BOM + ``;`` para Excel pt-BR) e os helpers de dominio (dias do
periodo, taxa de reprovacao, zero-fill das 4 rotas). A agregacao SQL e exercida
nos testes @db (``test_relatorios_endpoints``).
"""

from datetime import date

import pytest
from src.adapters.outbound.db.relatorios_repository import _taxa, _zerar_rotas
from src.application.ports.relatorios_repository import RelatoriosRepositoryPort
from src.application.relatorios import RelatoriosService
from src.domain.provas import EstadoProva, Rota
from src.domain.relatorios import (
    AbaRelatorio,
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


# ---------------------------------------------------------------------------
# Helpers de dominio
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("de", "ate", "esperado"),
    [
        (date(2026, 6, 1), date(2026, 6, 30), 30),  # inclusivo nos dois extremos
        (date(2026, 6, 17), date(2026, 6, 17), 1),  # um unico dia
        (None, None, 30),  # sem periodo -> janela padrao do design
        (date(2026, 6, 30), date(2026, 6, 1), 30),  # invertido -> fallback
    ],
)
def test_dias_no_periodo(de: date | None, ate: date | None, esperado: int) -> None:
    assert dias_no_periodo(de, ate) == esperado


def test_taxa_reprovacao_formula() -> None:
    assert _taxa(0, 0) is None  # sem decisoes -> "—" na UI
    assert _taxa(10, 0) == 0.0
    assert _taxa(0, 5) == 100.0
    assert _taxa(3, 1) == 25.0  # 1 / (3+1)


def test_zerar_rotas_traz_sempre_as_quatro() -> None:
    fatias = _zerar_rotas({"matriz": 7, "filial": 3})
    assert [f.rota for f in fatias] == [Rota.MATRIZ, Rota.LAM_MATRIZ, Rota.FILIAL, Rota.LAM_FILIAL]
    assert [f.total for f in fatias] == [7, 0, 3, 0]


# ---------------------------------------------------------------------------
# CSV (DP-5) — fake repo com dados conhecidos
# ---------------------------------------------------------------------------
class _FakeRepo(RelatoriosRepositoryPort):
    async def geral(self, filtros: FiltrosRelatorio) -> RelatorioGeral:
        return RelatorioGeral(
            total_geral=10,
            volume=(PontoVolume(dia=date(2026, 6, 10), total=10),),
            tempo_medio_aprovacao_horas=12.5,
            taxa_reprovacao=20.0,
            distribuicao_rota=(
                FatiaRota(rota=Rota.MATRIZ, total=4),
                FatiaRota(rota=Rota.LAM_MATRIZ, total=0),
                FatiaRota(rota=Rota.FILIAL, total=6),
                FatiaRota(rota=Rota.LAM_FILIAL, total=0),
            ),
            ativas_aguardando_vendedor=3,
            ativas_reprovadas=1,
            metricas_por_vendedor=(
                MetricaVendedor(
                    vendedor_id="v1",
                    vendedor_nome="Mário Souza",
                    localizacao="filial",
                    volume=6,
                    aprovadas=4,
                    reprovadas=1,
                    taxa_reprovacao=20.0,
                    tempo_medio_horas=12.5,
                    atrasadas=2,
                ),
            ),
            provas_atrasadas=(
                ProvaAtrasada(
                    id="p1",
                    nome="Ricota fresca",
                    requerimento="150150",
                    cliente="Laticínios Artvac",
                    vendedor_id="v1",
                    vendedor_nome="Mário Souza",
                    status=EstadoProva.RETIRADA_VENDEDOR,
                    atraso_horas=1655.2,
                ),
            ),
        )

    async def studio(self, filtros: FiltrosRelatorio) -> RelatorioStudio:
        return RelatorioStudio(
            provas_criadas=2,
            media_diaria=0.07,
            reinicios_ciclo=0,
            devolvidas=1,
            cancelamentos=1,
            reprovadas_aguardando=1,
            tempo_ate_primeira_mov_horas=0.1,
            top_motivos_cancelamento=(MotivoCancelamento(motivo="Apenas Teste", total=1),),
        )

    async def vendedores(self, filtros: FiltrosRelatorio) -> RelatorioVendedores:
        return RelatorioVendedores(
            vendedores_filial=1,
            vendedores_matriz=0,
            vendedores_ativos=2,
            atrasadas_total=2,
            por_vendedor=(
                MetricaVendedor(
                    vendedor_id="v1",
                    vendedor_nome="André Bento",
                    localizacao="matriz",
                    volume=0,
                    aprovadas=0,
                    reprovadas=0,
                    taxa_reprovacao=None,
                    tempo_medio_horas=None,
                    atrasadas=0,
                ),
            ),
        )

    async def clicheria(self, filtros: FiltrosRelatorio) -> RelatorioClicheria:
        return RelatorioClicheria(
            tempo_medio_aguardando_horas=None,
            recebidas_no_periodo=0,
            em_transito_agora=0,
            origens=0,
            distribuicao_origem=(
                FatiaRota(rota=Rota.MATRIZ, total=0),
                FatiaRota(rota=Rota.LAM_MATRIZ, total=0),
                FatiaRota(rota=Rota.FILIAL, total=0),
                FatiaRota(rota=Rota.LAM_FILIAL, total=0),
            ),
        )


def _csv_texto(conteudo: bytes) -> str:
    # utf-8-sig: o BOM e consumido na decodificacao; valida que ele existe.
    assert conteudo.startswith(b"\xef\xbb\xbf"), "CSV deve comecar com BOM (Excel pt-BR)"
    return conteudo.decode("utf-8-sig")


async def test_csv_geral_preserva_campos_e_acentuacao() -> None:
    svc = RelatoriosService(_FakeRepo())
    conteudo = await svc.exportar_csv(AbaRelatorio.GERAL, FiltrosRelatorio())
    texto = _csv_texto(conteudo)
    # Separador ';' (Excel pt-BR) e \r\n.
    assert ";" in texto
    assert "\r\n" in texto
    # Escalares + acentuacao preservada.
    assert "Total geral;10" in texto
    assert "Tempo médio de aprovação (h);12,5" in texto  # decimal pt-BR (virgula)
    assert "Taxa de reprovação (%);20,0" in texto
    # Distribuicao por rota com percentuais (4 + 6 = 10 -> 40% / 60%).
    assert "Matriz;4;40,0%" in texto
    assert "Filial;6;60,0%" in texto
    # Tabela de vendedores (rotulo de status na tabela de atrasadas).
    assert "Mário Souza" in texto
    assert "Retirada" in texto  # rotulo de UI, nao "retirada_vendedor"
    assert "1655,2" in texto


async def test_csv_3studio_top_motivos() -> None:
    svc = RelatoriosService(_FakeRepo())
    texto = _csv_texto(await svc.exportar_csv(AbaRelatorio.STUDIO, FiltrosRelatorio()))
    assert "Relatório;3Studio" in texto
    assert "Devolvidas (reprovações);1" in texto
    assert "Apenas Teste;1" in texto


async def test_csv_vendedores_taxa_vazia_vira_traco() -> None:
    svc = RelatoriosService(_FakeRepo())
    texto = _csv_texto(await svc.exportar_csv(AbaRelatorio.VENDEDORES, FiltrosRelatorio()))
    assert "André Bento" in texto
    # Sem decisoes -> taxa e tempo como "—" (nao 0% enganoso).
    linha = next(line for line in texto.splitlines() if line.startswith("André Bento"))
    assert "—" in linha


async def test_csv_periodo_no_cabecalho() -> None:
    svc = RelatoriosService(_FakeRepo())
    filtros = FiltrosRelatorio(de=date(2026, 5, 18), ate=date(2026, 6, 17))
    texto = _csv_texto(await svc.exportar_csv(AbaRelatorio.CLICHERIA, filtros))
    assert "Período;18/05/2026 a 17/06/2026" in texto
