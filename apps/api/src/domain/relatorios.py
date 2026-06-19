"""Dominio dos Relatorios gerenciais (W5-C17) — RF-016 (Should), US-014.

Camada interna (CLAUDE.md §5.2): apenas stdlib + o glossario de estados/rotas e os
grupos de status do Dashboard (reuso, sem drift). Concentra o que e DECISAO DE
NEGOCIO e precisa de code review — a parte mais importante deste componente
(prompt §"Lembrete final": uma metrica com a formula errada e pior que metrica
nenhuma). As FORMULAS confirmadas (DP-3) vivem aqui como a fonte unica que o
repositorio traduz em SQL.

POPULACAO BASE (decisao de engenharia, documentada — ADR): o filtro de PERIODO
(De/Ate) recorta as provas por ``created_at`` (provas CRIADAS na janela); os
demais filtros (status/rota/vendedor/busca) compoem com ele. TODA metrica de cada
aba e calculada sobre essa MESMA populacao — uma definicao unica e consistente
(o criterio §6.3 "distribuicao por rota soma 100% no periodo" e satisfeito: a
distribuicao soma o total da base). Eventos (reinicios/cancelamentos/devolvidas)
sao contados sobre as movimentacoes DAS provas da base.

BASE TEMPORAL: HORAS UTEIS (seg-sex 07-18, America/Sao_Paulo — RNF-011), a MESMA
do C16 (consistencia — criterio §6.5). O calculo executavel vive em
``private.horas_uteis_entre`` (duracao, migration 0021) e ``private.instante_limite_atraso``
(predicado de atraso, 0020, reusado verbatim). FORMULAS (DP-3):

- Tempo medio de aprovacao (geral e por vendedor): horas uteis entre a CHEGADA AO
  VENDEDOR (transicao para ``retirada_vendedor``/``encaminhada_para_vendedor``) e a
  APROVACAO (``acao=aprovar`` -> ``aprovada_vendedor``). Mede a resposta do vendedor.
- Taxa de reprovacao: ``reprovadas / (aprovadas + reprovadas)`` (eventos no periodo);
  geral e por vendedor. Denominador = decisoes do vendedor (corroborado pelo design:
  Aprov% + Reprov% = 100%).
- Atrasadas: MESMA regra do C16 (``private.instante_limite_atraso`` + delay do C09);
  o ATRASO exibido e em horas uteis desde o ultimo evento (DP-3: unidade = horas).
- Tempo ate 1a mov (3Studio): horas uteis de ``created_at`` ate a 1a movimentacao.
- Devolvidas (3Studio): contagem de eventos ``acao=reprovar`` no periodo (DP-3).
- Tempo medio aguardando (Clicheria): horas uteis do ENVIO a clicheria (transicao
  para ``com_motorista_entrega_final``) ate o RECEBIMENTO (``recebida_clicheria``).
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from src.domain.dashboard import FUSO_COMERCIAL, STATUS_COM_VENDEDOR
from src.domain.provas import EstadoProva, Rota

__all__ = [
    "FUSO_COMERCIAL",
    "ROTAS_ORDEM",
    "STATUS_AGUARDANDO_VENDEDOR",
    "STATUS_EM_TRANSITO_CLICHERIA",
    "STATUS_RECEBIDA_CLICHERIA",
    "STATUS_REPROVADA",
    "AbaRelatorio",
    "FatiaRota",
    "FiltrosRelatorio",
    "MetricaVendedor",
    "MotivoCancelamento",
    "PontoVolume",
    "ProvaAtrasada",
    "RelatorioClicheria",
    "RelatorioGeral",
    "RelatorioStudio",
    "RelatorioVendedores",
]


class AbaRelatorio(StrEnum):
    """As quatro abas do design (§0.2) — cada uma e uma agregacao server-side
    independente, computada SO quando a aba esta ativa (lazy — RNF-022/DP-6)."""

    GERAL = "geral"
    STUDIO = "studio"
    VENDEDORES = "vendedores"
    CLICHERIA = "clicheria"


# ---------------------------------------------------------------------------
# Grupos de status (DP-3) — fonte unica do mapeamento metrica->status
# ---------------------------------------------------------------------------
# Donut "Provas Ativas" (Geral) — 2 segmentos (DP-3, bate com a legenda do design):
# "Aguardando vendedor" = posse do vendedor (reuso do C16, sem drift); "Reprovada".
STATUS_AGUARDANDO_VENDEDOR: tuple[EstadoProva, ...] = STATUS_COM_VENDEDOR
STATUS_REPROVADA: tuple[EstadoProva, ...] = (EstadoProva.REPROVADA_VENDEDOR,)

# Clicheria (DP-3 — perspectiva "rumo a clicheria"): em transito = a caminho da
# clicheria; recebimento = terminal recebida_clicheria.
STATUS_EM_TRANSITO_CLICHERIA: tuple[EstadoProva, ...] = (EstadoProva.COM_MOTORISTA_ENTREGA_FINAL,)
STATUS_RECEBIDA_CLICHERIA: tuple[EstadoProva, ...] = (EstadoProva.RECEBIDA_CLICHERIA,)

# As 4 rotas em ordem canonica — a distribuicao SEMPRE traz as quatro (zero-fill),
# somando o total da base (criterio §6.3: soma 100% no periodo filtrado).
ROTAS_ORDEM: tuple[Rota, ...] = (Rota.MATRIZ, Rota.LAM_MATRIZ, Rota.FILIAL, Rota.LAM_FILIAL)


# ---------------------------------------------------------------------------
# Filtros compartilhados (DP-4)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FiltrosRelatorio:
    """Estado da barra de filtros (compartilhado por todas as abas — DP-4).

    ``de``/``ate`` recortam a populacao por ``created_at`` (dia inclusivo nos dois
    extremos). ``rotas`` e MULTI-VALOR (o toggle 2-vias do design agrupa
    Matriz->{matriz, lam_matriz} / Filial->{filial, lam_filial}; vazio = todas).
    ``status`` tambem e multi-valor (vazio = todos). ``busca`` casa nome OU
    requerimento (RF-013, igual ao C07)."""

    de: date | None = None
    ate: date | None = None
    status: tuple[EstadoProva, ...] = ()
    rotas: tuple[Rota, ...] = ()
    busca: str | None = None
    vendedor_id: str | None = None


# ---------------------------------------------------------------------------
# Estruturas compartilhadas entre abas
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PontoVolume:
    """Um dia do grafico de volume (Geral) — provas criadas naquele dia."""

    dia: date
    total: int


@dataclass(frozen=True)
class FatiaRota:
    """Uma fatia da distribuicao por rota (sempre as 4; o front calcula o %)."""

    rota: Rota
    total: int


@dataclass(frozen=True)
class MetricaVendedor:
    """Uma linha das tabelas por vendedor (Geral "Metricas por Vendedor" e
    Vendedores "Detalhamento"). Tudo sobre a populacao filtrada.

    ``taxa_reprovacao``/``tempo_medio_horas`` sao ``None`` quando nao ha base
    (sem decisoes / sem aprovacoes) — a UI mostra "—" em vez de 0% enganoso. O
    front deriva "Ranking por volume", "Tempo medio por vendedor" e "Vendedor com
    mais artes" reordenando esta MESMA lista (sem ida extra ao banco)."""

    vendedor_id: str
    vendedor_nome: str | None
    localizacao: str | None
    volume: int
    aprovadas: int
    reprovadas: int
    taxa_reprovacao: float | None
    tempo_medio_horas: float | None
    atrasadas: int


@dataclass(frozen=True)
class ProvaAtrasada:
    """Uma linha da tabela "Provas Atrasadas / Aguardando acao" (Geral).

    ``atraso_horas`` em HORAS UTEIS desde o ultimo evento (DP-3: unidade = horas,
    fiel ao design). Ordenada por atraso desc."""

    id: str
    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    vendedor_nome: str | None
    status: EstadoProva
    atraso_horas: float


@dataclass(frozen=True)
class MotivoCancelamento:
    """Uma linha de "Top motivos de cancelamento" (3Studio) — motivo + contagem."""

    motivo: str
    total: int


# ---------------------------------------------------------------------------
# Saidas por aba
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RelatorioGeral:
    """Aba Geral (§0.2): cobre o piso do RF-016 (total, tempo medio, taxa,
    distribuicao por rota, atrasadas, por vendedor) + os extras do design."""

    total_geral: int
    volume: tuple[PontoVolume, ...]
    tempo_medio_aprovacao_horas: float | None
    taxa_reprovacao: float | None
    distribuicao_rota: tuple[FatiaRota, ...]
    ativas_aguardando_vendedor: int
    ativas_reprovadas: int
    metricas_por_vendedor: tuple[MetricaVendedor, ...]
    provas_atrasadas: tuple[ProvaAtrasada, ...]


@dataclass(frozen=True)
class RelatorioStudio:
    """Aba 3Studio (§0.2) — diagnostico da operacao do studio no periodo.

    ``volume`` e a serie diaria de provas criadas (alimenta o grafico de barras do
    card "Provas Criadas", igual ao Total geral da aba Geral)."""

    provas_criadas: int
    media_diaria: float
    reinicios_ciclo: int
    devolvidas: int
    cancelamentos: int
    reprovadas_aguardando: int
    tempo_ate_primeira_mov_horas: float | None
    top_motivos_cancelamento: tuple[MotivoCancelamento, ...]
    volume: tuple[PontoVolume, ...] = ()


@dataclass(frozen=True)
class RelatorioVendedores:
    """Aba Vendedores (§0.2) — ranking e detalhamento por vendedor.

    ``vendedores_filial``/``vendedores_matriz`` contam os USUARIOS do setor
    Vendedor por localizacao (cadastro — independem do periodo); ``ativos`` =
    vendedores com ao menos uma prova na populacao filtrada.

    ``provas_criadas``/``volume`` alimentam o card "Provas Criadas" (preto, com
    grafico de barras — igual ao Total geral da Geral e ao Provas Criadas do
    3Studio)."""

    vendedores_filial: int
    vendedores_matriz: int
    vendedores_ativos: int
    atrasadas_total: int
    por_vendedor: tuple[MetricaVendedor, ...]
    provas_criadas: int = 0
    volume: tuple[PontoVolume, ...] = ()


@dataclass(frozen=True)
class RelatorioClicheria:
    """Aba Clicheria (§0.2 — perspectiva "rumo a clicheria", DP-3).

    ``origens`` = nº de rotas distintas (das 4) entre as provas recebidas no
    periodo; ``distribuicao_origem`` detalha-as por rota. ``volume`` alimenta o
    grafico do card "Tempo Medio Aguardando" (atividade diaria — provas/dia da
    base, mesma serie das demais abas)."""

    tempo_medio_aguardando_horas: float | None
    recebidas_no_periodo: int
    em_transito_agora: int
    origens: int
    distribuicao_origem: tuple[FatiaRota, ...]
    volume: tuple[PontoVolume, ...] = ()


# Conversao de date (dia inclusivo) -> intervalo usado nas constantes da query.
def dias_no_periodo(de: date | None, ate: date | None) -> int:
    """Dias do periodo (inclusivo nos dois extremos) para a media diaria do
    3Studio. Sem periodo definido, cai em 30 (a janela padrao do design)."""
    if de is None or ate is None or ate < de:
        return 30
    return (ate - de).days + 1
