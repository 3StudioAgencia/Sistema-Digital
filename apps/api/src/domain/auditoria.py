"""Domínio do Log de Auditoria (W6-C20) — RNF-006 + a visão do design (DP-1=C).

O log do design é um superconjunto do ``movimentacoes`` (C11): além das transições
da máquina de estados, registra **eventos-chave que não são movimentações** —
``criou_prova`` (C06) e ``escaneou_qr`` (C10) — e metadados de **IP/origem** e um
**hash de integridade encadeado**. Tudo isso vive numa tabela própria ``audit_log``
(append-only) para NÃO acoplar o histórico por-prova (Timeline/C13, que segue lendo
``movimentacoes``) e para ser auto-contida e pesquisável sem JOIN.

Este módulo é o núcleo PURO (sem framework, sem ORM — CLAUDE.md §5.2):
- ``EventoAuditoria`` — os 7 tipos de evento, 1:1 com os pontos coloridos do design;
- ``EVENTO_POR_ACAO`` — projeção das 5 ``Acao`` da §6 nos eventos de transição
  (fonte única; o C11/C14/C15 não decidem a categoria do log);
- ``NovoEventoAuditoria`` — o comando de captura (campos de negócio); IP/origem/
  request_id e o hash são preenchidos pelo adapter (contexto da requisição + SQL);
- ``RegistroAuditoria``/``PaginaAuditoria``/``FiltrosAuditoria``/``AtorRef``/
  ``ResultadoIntegridade`` — leitura (a UI master-detail do C20);
- ``rotulo_origem`` — heurística leve de User-Agent → "Aplicação Web · Chrome"
  (sem dependência nova — custo R$ 0).
"""

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from src.domain.provas import EstadoProva, Rota  # noqa: F401  (Rota: reexport semântico)
from src.domain.state_machine.enums import Acao
from src.domain.usuarios import Setor


class EventoAuditoria(StrEnum):
    """Tipos de evento do log (``audit_evento_enum`` — sincronizado com a migration).

    Membro em MAIÚSCULA, valor ``snake_case`` (igual ao PG — CLAUDE.md §6). Os 5
    últimos são as transições da §6 (projetadas de ``Acao`` por ``EVENTO_POR_ACAO``);
    os 2 primeiros são os eventos não-movimentação que o design pede (DP-1=C).
    """

    CRIOU_PROVA = "criou_prova"
    ESCANEOU_QR = "escaneou_qr"
    MUDOU_STATUS = "mudou_status"
    APROVOU_PROVA = "aprovou_prova"
    REPROVOU_PROVA = "reprovou_prova"
    REINICIOU_CICLO = "reiniciou_ciclo"
    CANCELOU_PROVA = "cancelou_prova"


# Projeção das ações da §6 nos eventos de transição (fonte única — DP-3). A
# ``identificar_e_assinar`` cobre TODAS as travessias de motorista + a confirmação
# de assinatura: a categoria do log é "mudou status" e o detalhe traz origem→destino.
EVENTO_POR_ACAO: dict[Acao, EventoAuditoria] = {
    Acao.IDENTIFICAR_E_ASSINAR: EventoAuditoria.MUDOU_STATUS,
    Acao.APROVAR: EventoAuditoria.APROVOU_PROVA,
    Acao.REPROVAR: EventoAuditoria.REPROVOU_PROVA,
    Acao.REINICIAR_CICLO: EventoAuditoria.REINICIOU_CICLO,
    Acao.CANCELAR: EventoAuditoria.CANCELOU_PROVA,
}

# Defaults/limites de paginação (a opção "Linhas" do design controla o page_size).
PAGE_SIZE_PADRAO = 50
PAGE_SIZE_MAXIMO = 200

Ordem = Literal["recentes", "antigos"]


def rotulo_origem(user_agent: str | None) -> str | None:
    """User-Agent → rótulo legível de origem ("Aplicação Web · Chrome").

    Heurística mínima (sem lib de parsing — R$ 0): identifica o navegador pela
    ordem de especificidade (Edge/Opera contêm "Chrome" no UA; Chrome contém
    "Safari"). Sem UA → ``None`` (a UI não inventa origem). UA presente mas
    desconhecido → "Aplicação Web" (a plataforma é sempre web nesta versão)."""
    if not user_agent:
        return None
    ua = user_agent
    navegador: str | None = None
    if "Edg/" in ua or "Edge/" in ua:
        navegador = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        navegador = "Opera"
    elif "Firefox/" in ua:
        navegador = "Firefox"
    elif "Chrome/" in ua:
        navegador = "Chrome"
    elif "Safari/" in ua:
        navegador = "Safari"
    return f"Aplicação Web · {navegador}" if navegador else "Aplicação Web"


@dataclass(frozen=True)
class NovoEventoAuditoria:
    """Comando de captura de UM evento (campos de NEGÓCIO — RNF-006).

    O ator (id + setor) é forçado no banco a partir das claims (anti-forja); IP,
    User-Agent, origem, request_id e o hash encadeado são preenchidos pelo adapter.
    Os campos de prova são DENORMALIZADOS no instante do evento (o log registra o
    que era verdade então; busca sem JOIN). Os campos de transição (``acao`` e
    ``estado_*``/``ciclo``) só existem para os eventos de movimentação.
    """

    evento: EventoAuditoria
    prova_id: str | None = None
    prova_codigo: str | None = None
    prova_cliente: str | None = None
    prova_requerimento: str | None = None
    acao: Acao | None = None
    estado_origem: EstadoProva | None = None
    estado_destino: EstadoProva | None = None
    ciclo: int | None = None
    motivo: str | None = None


@dataclass(frozen=True)
class RegistroAuditoria:
    """Uma linha do log, como a UI master-detail a exibe (W6-C20).

    ``ator_nome`` é resolvido na leitura (JOIN ``usuarios`` — admin enxerga todos);
    ``ator_setor`` vem denormalizado do evento. ``origem`` é o rótulo já formatado
    (não o UA cru). ``hash`` é o elo do encadeamento (exibido como ``sha256:…``).
    """

    id: str
    seq: int
    evento: EventoAuditoria
    ator_id: str
    ator_nome: str | None
    ator_setor: Setor | None
    prova_id: str | None
    prova_codigo: str | None
    prova_cliente: str | None
    prova_requerimento: str | None
    acao: Acao | None
    estado_origem: EstadoProva | None
    estado_destino: EstadoProva | None
    ciclo: int | None
    motivo: str | None
    ip: str | None
    origem: str | None
    created_at: datetime
    hash: str


@dataclass(frozen=True)
class FiltrosAuditoria:
    """Filtros da barra do design (DP-2) — server-side, estado na URL.

    ``eventos`` aceita múltiplos (o dropdown manda 1, mas o contrato suporta IN);
    período por ``created_at`` (dia, inclusivo nos dois extremos — convenção do C07);
    ``ordem`` espelha o dropdown "Ordem: Recentes/Antigos" (por ``seq``).
    """

    eventos: tuple[EventoAuditoria, ...] = ()
    ator_id: str | None = None
    busca: str | None = None
    de: date | None = None
    ate: date | None = None
    ordem: Ordem = "recentes"
    page: int = 1
    page_size: int = PAGE_SIZE_PADRAO

    def saneados(self) -> "FiltrosAuditoria":
        """Normaliza page/page_size para limites seguros (teto = mínimo de requisições)."""
        page = self.page if self.page >= 1 else 1
        size = self.page_size
        if size < 1:
            size = PAGE_SIZE_PADRAO
        elif size > PAGE_SIZE_MAXIMO:
            size = PAGE_SIZE_MAXIMO
        return replace(self, page=page, page_size=size)


@dataclass(frozen=True)
class PaginaAuditoria:
    items: list[RegistroAuditoria]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class AtorRef:
    """Ator distinto do log (id + nome) — popula o dropdown "Ator"."""

    id: str
    nome: str | None


@dataclass(frozen=True)
class ResultadoIntegridade:
    """Veredito da verificação do encadeamento (DP-4).

    ``intacto`` = o chain recomputado bate com o armazenado; ``quebrou_em`` é o
    ``seq`` da PRIMEIRA linha divergente (``None`` quando íntegro)."""

    intacto: bool
    total: int
    quebrou_em: int | None


__all__ = [
    "EVENTO_POR_ACAO",
    "PAGE_SIZE_MAXIMO",
    "PAGE_SIZE_PADRAO",
    "AtorRef",
    "EventoAuditoria",
    "FiltrosAuditoria",
    "NovoEventoAuditoria",
    "Ordem",
    "PaginaAuditoria",
    "RegistroAuditoria",
    "ResultadoIntegridade",
    "rotulo_origem",
]
