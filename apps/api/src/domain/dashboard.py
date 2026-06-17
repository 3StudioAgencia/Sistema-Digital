"""Dominio do Dashboard (W4-C16) — RF-015, RN-008, RNF-011.

Camada interna (CLAUDE.md §5.2): apenas stdlib + o glossario de estados. Concentra
o que e DECISAO de negocio e precisa de code review:

1. O MAPEAMENTO contador -> status (DP-2). O design (DP-1: "seguir o design exato")
   mostra 5 contadores; aqui ficam os subconjuntos de ``status_prova_enum`` de cada
   um — a fonte unica que o repositorio injeta na consulta de agregacao.
2. A JANELA COMERCIAL de "Atrasada" (RN-008/RNF-011) como constantes de REFERENCIA
   (documentacao): o calculo executavel vive em ``private.instante_limite_atraso``
   (migration 0020) — uma ida so ao banco (DP/minimo de requisicoes). Mantenha as
   duas em sincronia.

NAO ha contadores de "Reprovadas" nem do bloco "Em Transito" (RF-015 os pede, mas
o dono optou por seguir o design exato — DP-1/ADR; desvio consciente registrado em
DECISIONS.md). Adiciona-los depois e so estender o mapeamento e a query.
"""

from dataclasses import dataclass

from src.domain.provas import EstadoProva

# ---------------------------------------------------------------------------
# Mapeamento contador -> status (DP-2) — fonte unica da agregacao
# ---------------------------------------------------------------------------
# "Com Vendedor": prova na POSSE do vendedor aguardando a decisao dele (Aprovar/
# Reprovar), nas duas portas das 4 rotas — Matriz/Lam.Matriz retiram, Filial/
# Lam.Filial recebem encaminhada. Apos decidir, sai para aprovada/reprovada
# (contadas a parte).
STATUS_COM_VENDEDOR: tuple[EstadoProva, ...] = (
    EstadoProva.RETIRADA_VENDEDOR,
    EstadoProva.ENCAMINHADA_PARA_VENDEDOR,
)
# "Aprovadas": aprovadas pelo vendedor (estado atual).
STATUS_APROVADAS: tuple[EstadoProva, ...] = (EstadoProva.APROVADA_VENDEDOR,)
# "Na clicheria": recebida pela clicheria — terminal = "Concluidas" do RF-015
# (o rotulo do design "Na clicheria" coincide com o rotulo de ``recebida_clicheria``).
STATUS_NA_CLICHERIA: tuple[EstadoProva, ...] = (EstadoProva.RECEBIDA_CLICHERIA,)

# ---------------------------------------------------------------------------
# Janela comercial de "Atrasada" (REFERENCIA — executavel em SQL na 0020)
# ---------------------------------------------------------------------------
FUSO_COMERCIAL = "America/Sao_Paulo"
HORA_INICIO_COMERCIAL = 7  # 07:00
HORA_FIM_COMERCIAL = 18  # 18:00 (11h uteis/dia, seg-sex)


@dataclass(frozen=True)
class AtrasadaVendedor:
    """Uma linha do breakdown de "Atrasadas" por vendedor (RF-015/DP-4).

    ``vendedor_nome`` e resolvido por ``private.nomes_de_vendedores`` (escopado),
    ``None`` no caso degenerado de o vendedor sumir do projetor."""

    vendedor_id: str
    vendedor_nome: str | None
    total: int


@dataclass(frozen=True)
class ContadoresDashboard:
    """Os contadores do Dashboard (W4-C16) — todos ESCOPADOS pela RLS de ``provas``
    (cada perfil ve so os seus numeros — Matriz §7). Saida de UMA consulta unica
    (sem N+1 — RNF-022); a lista de atrasadas ja vem ordenada por contagem desc."""

    criadas_hoje: int
    com_vendedor: int
    aprovadas: int
    na_clicheria: int
    atrasadas_total: int
    atrasadas_por_vendedor: tuple[AtrasadaVendedor, ...]


__all__ = [
    "FUSO_COMERCIAL",
    "HORA_FIM_COMERCIAL",
    "HORA_INICIO_COMERCIAL",
    "STATUS_APROVADAS",
    "STATUS_COM_VENDEDOR",
    "STATUS_NA_CLICHERIA",
    "AtrasadaVendedor",
    "ContadoresDashboard",
]
