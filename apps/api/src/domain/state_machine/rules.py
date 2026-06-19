"""Tabela de transições válidas (W3-C11) — a Requisitos v1.0 §6 INTEIRA como dados.

CLAUDE.md §5.3 / DAT §4: ``TRANSITION_RULES`` vive AQUI, em código versionado e
revisável por code review, NUNCA no banco. Indexada por ``(rota, estado_atual)``
→ tupla de ``Transicao`` válidas. Sem wildcard nem fallback: ``(rota, estado,
ação)`` não listada é rejeitada (422 — ``machine.avaliar_transicao``).

Especificação canônica: §6.2—6.6 dos Requisitos, reproduzida e conferida célula
a célula (revisor adversarial: idêntica). Em QUALQUER divergência, a §6 do
documento de Requisitos prevalece — registre a divergência em ``DECISIONS.md``.

Construção (auditável):
1. ``_FLUXOS`` declara LITERALMENTE, por rota, os avanços normais (§6.2—6.5), a
   reprovação e o reinício de ciclo (§6.6) — exatamente como a tabela da §6.
2. O CANCELAR transversal (§6.6: "qualquer estado ativo → Cancelada") é
   adicionado programaticamente a TODO estado ativo de cada rota. NÃO é um
   wildcard de runtime: o dict final é totalmente materializado e a consulta é
   sempre exata; o laço só evita 30+ linhas idênticas e propensas a erro.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from src.domain.provas import EstadoProva, Rota
from src.domain.state_machine.enums import Acao, Autorizacao

# Aliases locais para a tabela caber legível (escopo do módulo).
_E = EstadoProva
_A = Autorizacao


@dataclass(frozen=True)
class Transicao:
    """Uma aresta válida da máquina: ação + perfil autorizado + estado destino.

    ``exige_motivo`` marca as ações que pedem justificativa obrigatória (RF-008
    reprovar; §6.6 cancelar) — validada no domínio (``machine``); sem motivo →
    rejeitada (422).
    """

    acao: Acao
    perfil_autorizado: Autorizacao
    estado_destino: EstadoProva
    exige_motivo: bool = False


# Estados TERMINAIS — sem transição de saída (§6.1). Qualquer ação a partir
# deles (incl. Cancelar) não está na tabela → 422.
ESTADOS_TERMINAIS: Final[frozenset[EstadoProva]] = frozenset({_E.RECEBIDA_CLICHERIA, _E.CANCELADA})


def _avanco(perfil: Autorizacao, destino: EstadoProva) -> Transicao:
    """Avanço normal do fluxo: ação ``IDENTIFICAR_E_ASSINAR`` (§6: identificar →
    assinar → confirmar). Sem motivo."""
    return Transicao(Acao.IDENTIFICAR_E_ASSINAR, perfil, destino)


# Cancelamento transversal (§6.6): 3Studio (flag admin — ADR-023), motivo
# obrigatório, de qualquer estado ativo → Cancelada.
_CANCELAR = Transicao(Acao.CANCELAR, _A.ADMIN, _E.CANCELADA, exige_motivo=True)
# Reinício de ciclo (§6.6 / RN-006): 3Studio (flag admin), de "Reprovada pelo
# Vendedor" → "Criada (novo ciclo)". Rota e histórico preservados (efeito de
# ciclo/``ciclo_atual`` é do C15, que invoca este motor).
_REINICIAR = Transicao(Acao.REINICIAR_CICLO, _A.ADMIN, _E.CRIADA)


# ---------------------------------------------------------------------------
# §6.2—6.6 LITERAL — avanços + reprovação + reinício, por rota (sem o Cancelar,
# adicionado a todo estado ativo logo abaixo).
# ---------------------------------------------------------------------------
def _reprovar() -> Transicao:
    return Transicao(Acao.REPROVAR, _A.VENDEDOR, _E.REPROVADA_VENDEDOR, exige_motivo=True)


def _aprovar() -> Transicao:
    return Transicao(Acao.APROVAR, _A.VENDEDOR, _E.APROVADA_VENDEDOR)


_FLUXOS: dict[Rota, dict[EstadoProva, list[Transicao]]] = {
    # §6.2 — Rota Matriz (sem laminação): 3Studio → Vendedor → 3Studio → Motorista → Clicheria.
    Rota.MATRIZ: {
        _E.CRIADA: [_avanco(_A.VENDEDOR, _E.RETIRADA_VENDEDOR)],
        _E.RETIRADA_VENDEDOR: [_aprovar(), _reprovar()],
        _E.APROVADA_VENDEDOR: [_avanco(_A.STUDIO, _E.DE_VOLTA_STUDIO)],
        _E.DE_VOLTA_STUDIO: [_avanco(_A.MOTORISTA, _E.COM_MOTORISTA_ENTREGA_FINAL)],
        _E.COM_MOTORISTA_ENTREGA_FINAL: [_avanco(_A.CLICHERIA, _E.RECEBIDA_CLICHERIA)],
        _E.REPROVADA_VENDEDOR: [_REINICIAR],
    },
    # §6.3 — Rota Lam. Matriz (com laminação; Vendedor na Matriz): ida/volta de
    # laminação pelo Motorista, depois o fluxo da Matriz.
    Rota.LAM_MATRIZ: {
        _E.CRIADA: [_avanco(_A.STUDIO, _E.ENCAMINHADA_PARA_LAMINACAO)],
        _E.ENCAMINHADA_PARA_LAMINACAO: [_avanco(_A.MOTORISTA, _E.COM_MOTORISTA_IDA_LAMINACAO)],
        _E.COM_MOTORISTA_IDA_LAMINACAO: [_avanco(_A.CLICHERIA, _E.LAMINACAO_CONCLUIDA)],
        _E.LAMINACAO_CONCLUIDA: [_avanco(_A.MOTORISTA, _E.COM_MOTORISTA_VOLTA_LAMINACAO)],
        _E.COM_MOTORISTA_VOLTA_LAMINACAO: [_avanco(_A.STUDIO, _E.DE_VOLTA_STUDIO_POS_LAMINACAO)],
        _E.DE_VOLTA_STUDIO_POS_LAMINACAO: [_avanco(_A.VENDEDOR, _E.RETIRADA_VENDEDOR)],
        _E.RETIRADA_VENDEDOR: [_aprovar(), _reprovar()],
        _E.APROVADA_VENDEDOR: [_avanco(_A.STUDIO, _E.DE_VOLTA_STUDIO)],
        _E.DE_VOLTA_STUDIO: [_avanco(_A.MOTORISTA, _E.COM_MOTORISTA_ENTREGA_FINAL)],
        _E.COM_MOTORISTA_ENTREGA_FINAL: [_avanco(_A.CLICHERIA, _E.RECEBIDA_CLICHERIA)],
        _E.REPROVADA_VENDEDOR: [_REINICIAR],
    },
    # §6.4 — Rota Filial (sem laminação; Vendedor na Filial): direto 3Studio →
    # Vendedor → Clicheria, sem Motorista.
    Rota.FILIAL: {
        _E.CRIADA: [_avanco(_A.VENDEDOR, _E.ENCAMINHADA_PARA_VENDEDOR)],
        _E.ENCAMINHADA_PARA_VENDEDOR: [_aprovar(), _reprovar()],
        _E.APROVADA_VENDEDOR: [_avanco(_A.CLICHERIA, _E.RECEBIDA_CLICHERIA)],
        _E.REPROVADA_VENDEDOR: [_REINICIAR],
    },
    # §6.5 — Rota Lam. Filial (com laminação; Vendedor na Filial): ida de
    # laminação pelo Motorista; o retorno NÃO usa Motorista (Vendedor e Clicheria
    # ambos na Filial). "Laminação Concluída" → Vendedor (≠ Lam. Matriz → Motorista).
    Rota.LAM_FILIAL: {
        _E.CRIADA: [_avanco(_A.STUDIO, _E.ENCAMINHADA_PARA_LAMINACAO)],
        _E.ENCAMINHADA_PARA_LAMINACAO: [_avanco(_A.MOTORISTA, _E.COM_MOTORISTA_IDA_LAMINACAO)],
        _E.COM_MOTORISTA_IDA_LAMINACAO: [_avanco(_A.CLICHERIA, _E.LAMINACAO_CONCLUIDA)],
        _E.LAMINACAO_CONCLUIDA: [_avanco(_A.VENDEDOR, _E.ENCAMINHADA_PARA_VENDEDOR)],
        _E.ENCAMINHADA_PARA_VENDEDOR: [_aprovar(), _reprovar()],
        _E.APROVADA_VENDEDOR: [_avanco(_A.CLICHERIA, _E.RECEBIDA_CLICHERIA)],
        _E.REPROVADA_VENDEDOR: [_REINICIAR],
    },
}


def _construir_regras() -> MappingProxyType[tuple[Rota, EstadoProva], tuple[Transicao, ...]]:
    """Materializa ``TRANSITION_RULES`` a partir de ``_FLUXOS`` + o Cancelar
    transversal em todo estado ativo. Dict imutável (``MappingProxyType``) de
    tuplas — nenhuma mutação acidental em runtime.

    Todo estado ATIVO de cada rota é uma chave (origem) em ``_FLUXOS`` (nenhum
    estado terminal aparece como origem); por isso adicionar Cancelar a cada
    chave cobre exatamente os estados ativos (§6.6) — terminais ficam de fora e
    qualquer ação a partir deles cai no 422.
    """
    regras: dict[tuple[Rota, EstadoProva], tuple[Transicao, ...]] = {}
    for rota, por_estado in _FLUXOS.items():
        for estado, transicoes in por_estado.items():
            if estado in ESTADOS_TERMINAIS:  # pragma: no cover - invariante de construção (§6.1)
                raise ValueError(f"estado terminal {estado} não pode ser origem de transição")
            regras[(rota, estado)] = (*transicoes, _CANCELAR)
    return MappingProxyType(regras)


TRANSITION_RULES: Final[MappingProxyType[tuple[Rota, EstadoProva], tuple[Transicao, ...]]] = (
    _construir_regras()
)


def _escopo_operacional_motorista() -> frozenset[EstadoProva]:
    """Estados que o Motorista PRECISA enxergar (RLS — W3-C11), DERIVADOS da §6:

    - ORIGENS das suas transições (onde ele é o próximo ator: pega a prova para a
      travessia) — senão receberia 404 ao escanear e nunca iniciaria; e
    - DESTINOS dessas transições (os "Com Motorista" = "Em Trânsito" que ele
      carrega).

    Fonte ÚNICA do conjunto: a RLS ``provas_select_motorista`` (e a de UPDATE)
    espelha estes valores em SQL, e o harness de equivalência trava o drift.
    """
    origens = {
        estado
        for (_rota, estado), transicoes in TRANSITION_RULES.items()
        for t in transicoes
        if t.perfil_autorizado is Autorizacao.MOTORISTA
    }
    destinos = {
        t.estado_destino
        for transicoes in TRANSITION_RULES.values()
        for t in transicoes
        if t.perfil_autorizado is Autorizacao.MOTORISTA
    }
    return frozenset(origens | destinos)


# Escopo de dado do Motorista (W3-C11): origens das transições do Motorista +
# Em Trânsito. Espelhado nos `provas_select_motorista.sql`/`provas_update_motorista.sql`.
ESTADOS_ESCOPO_MOTORISTA: Final[frozenset[EstadoProva]] = _escopo_operacional_motorista()


__all__ = [
    "ESTADOS_ESCOPO_MOTORISTA",
    "ESTADOS_TERMINAIS",
    "TRANSITION_RULES",
    "Transicao",
]
