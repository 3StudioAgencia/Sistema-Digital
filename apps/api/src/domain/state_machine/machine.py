"""Motor de validação de transições (W3-C11) — função PURA, sem IO.

``avaliar_transicao`` é o ``transition(prova, ator, acao)`` do DAT §4.1: consulta
``TRANSITION_RULES`` e decide, na ordem que respeita o anti-enumeração da DP-7:

1. ``(rota, estado, ação)`` não está na tabela  → ``TransicaoInvalidaError`` (422).
2. está, mas o perfil do ator não é o autorizado → ``TransicaoNaoAutorizadaError`` (403,
   mensagem genérica que NÃO revela qual setor poderia — RN-014/Backlog C12).
3. a ação exige motivo e ele não veio          → ``MotivoObrigatorioError`` (422).

A camada de DADO (a prova existir/estar no escopo do ator) é resolvida ANTES,
pela RLS (404 genérico — anti-enumeração); aqui já se sabe a ``rota`` e o
``estado_atual`` reais da prova. Nenhum efeito colateral: persistência,
atomicidade e idempotência são do caso de uso (``application/transicoes.py``).
"""

from src.domain.provas import EstadoProva, Rota
from src.domain.state_machine.enums import Acao, Autorizacao, Setor
from src.domain.state_machine.rules import TRANSITION_RULES, Transicao
from src.domain.usuarios import ErroDeDominio


class TransicaoInvalidaError(ErroDeDominio):
    """Transição não definida na §6 para ``(rota, estado, ação)`` — incl. estado
    terminal e ação inaplicável. Mapeada a 422 (default do domínio). Mensagem
    genérica: não revela o estado atual (menos superfície)."""

    codigo = "transicao_invalida"

    def __init__(self) -> None:
        super().__init__("Esta ação não é válida para a prova no estado atual.")


class TransicaoNaoAutorizadaError(ErroDeDominio):
    """Rota e estado válidos, ação definida, mas o PERFIL do ator não é o
    autorizado (Backlog C11: 403, "mesmo com rota e estado válidos"). Mapeada a
    403. Mensagem genérica que NÃO revela qual setor poderia agir (RN-014 /
    Backlog C12: "sem revelar quem é") — a prova já está no escopo do ator (ele a
    enxerga), então isto não vaza existência, só não nomeia o próximo ator."""

    codigo = "transicao_nao_autorizada"

    def __init__(self) -> None:
        super().__init__("Seu perfil não pode realizar esta ação nesta prova agora.")


class MotivoObrigatorioError(ErroDeDominio):
    """Ação que exige justificativa (Reprovar — RF-008; Cancelar — §6.6) sem
    motivo. Mapeada a 422 (default)."""

    codigo = "motivo_obrigatorio"

    def __init__(self) -> None:
        super().__init__("Informe o motivo para concluir esta ação.")


def autoriza(perfil_exigido: Autorizacao, setor: Setor, administrador: bool) -> bool:
    """Decide se um ator (``setor`` + flag ``administrador``) satisfaz o perfil
    exigido por uma transição.

    Normal-flow (Vendedor/3Studio/Motorista/Clicheria) chaveia pelo SETOR
    operacional (RN-004). As ações "Exclusivo 3Studio" (Cancelar/Reiniciar)
    chaveiam pela flag ``administrador`` (ADR-023) — qualquer setor, desde que
    admin —, consistente com o gate de página/ação de ``domain/rbac.py``.
    """
    if perfil_exigido is Autorizacao.ADMIN:
        return administrador
    return perfil_exigido.value == setor.value


def transicoes_de(rota: Rota, estado: EstadoProva) -> tuple[Transicao, ...]:
    """Transições válidas a partir de ``(rota, estado)`` — tupla vazia se nenhuma
    (estado terminal ou par inexistente naquela rota)."""
    return TRANSITION_RULES.get((rota, estado), ())


# Ações que AVANÇAM o fluxo NORMAL (sem desvios). A sequência canônica de uma
# rota é o caminho por estas ações, de ``CRIADA`` até o terminal; ``REPROVAR``,
# ``CANCELAR`` e ``REINICIAR_CICLO`` são desvios (não entram no caminho linear
# esperado — a Timeline do C13 os representa como eventos, não como etapas).
ACOES_AVANCO: frozenset[Acao] = frozenset({Acao.IDENTIFICAR_E_ASSINAR, Acao.APROVAR})


# Ações ADMINISTRATIVAS transversais ("Exclusivo 3Studio" — §6.6): Cancelar (C14)
# e Reiniciar Ciclo (C15). Duas propriedades as distinguem do fluxo operacional:
# (1) autorizadas pela FLAG ``administrador`` (``Autorizacao.ADMIN``), não pelo
# setor (ADR-064); (2) NÃO capturam assinatura desenhada — a §6.6 define o
# cancelamento como "Ação administrativa: Cancelar Prova. Motivo obrigatório.",
# SEM o passo "Assinar" (ao contrário de Reprovar). Por isso a coluna
# ``movimentacoes.assinatura_ref`` nasceu nullable (ADR-066): essas ações gravam
# a movimentação SEM comprovante desenhado. São exatamente as transições da §6
# cujo perfil exigido é ``Autorizacao.ADMIN`` (consistência travada por teste).
ACOES_ADMINISTRATIVAS: frozenset[Acao] = frozenset({Acao.CANCELAR, Acao.REINICIAR_CICLO})


def exige_assinatura(acao: Acao) -> bool:
    """RN-003 vs. §6.6: toda movimentação OPERACIONAL (identificar/aprovar/
    reprovar) é comprovada pela assinatura DESENHADA (W3-C12); as ações
    ADMINISTRATIVAS (Cancelar/Reiniciar — §6.6) são a exceção autorizada e gravam
    a movimentação sem traço (``assinatura_ref`` NULL — ADR-066). Fonte única do
    "quem assina" para o serviço de transição (W3-C14)."""
    return acao not in ACOES_ADMINISTRATIVAS


def sequencia_canonica(rota: Rota) -> tuple[EstadoProva, ...]:
    """Sequência ordenada de estados do caminho NORMAL de uma rota (W3-C13/DP-1).

    DERIVADA de ``TRANSITION_RULES`` (fonte ÚNICA — a §6 NÃO é duplicada): caminha
    de ``CRIADA`` seguindo a única transição de avanço (``ACOES_AVANCO``) de cada
    estado até o terminal. Determinística: na §6, todo estado ATIVO tem
    exatamente UMA transição de avanço (os estados de decisão do Vendedor têm
    Aprovar como avanço e Reprovar como desvio). A Timeline a usa como o
    "esqueleto" da rota (etapas percorridas/atual/futuras); os rótulos são do
    frontend (C07/C08). Pura, sem IO — coberta como o resto da máquina (≥95%).

    O guarda ``visitados`` corta qualquer ciclo acidental (a §6 é acíclica no
    avanço — o reinício é desvio), mantendo a função total.
    """
    sequencia: list[EstadoProva] = [EstadoProva.CRIADA]
    visitados: set[EstadoProva] = {EstadoProva.CRIADA}
    atual = EstadoProva.CRIADA
    while True:
        proxima = next((t for t in transicoes_de(rota, atual) if t.acao in ACOES_AVANCO), None)
        if proxima is None or proxima.estado_destino in visitados:
            break
        sequencia.append(proxima.estado_destino)
        visitados.add(proxima.estado_destino)
        atual = proxima.estado_destino
    return tuple(sequencia)


def avaliar_transicao(
    rota: Rota,
    estado_atual: EstadoProva,
    acao: Acao,
    *,
    setor: Setor,
    administrador: bool,
    motivo: str | None,
) -> Transicao:
    """Valida a transição e devolve a ``Transicao`` (com o estado destino) — ou
    levanta o erro de domínio correspondente (422/403). Função pura."""
    candidata = next((t for t in transicoes_de(rota, estado_atual) if t.acao is acao), None)
    if candidata is None:
        raise TransicaoInvalidaError()
    if not autoriza(candidata.perfil_autorizado, setor, administrador):
        raise TransicaoNaoAutorizadaError()
    if candidata.exige_motivo and not (motivo and motivo.strip()):
        raise MotivoObrigatorioError()
    return candidata


__all__ = [
    "ACOES_ADMINISTRATIVAS",
    "ACOES_AVANCO",
    "MotivoObrigatorioError",
    "TransicaoInvalidaError",
    "TransicaoNaoAutorizadaError",
    "autoriza",
    "avaliar_transicao",
    "exige_assinatura",
    "sequencia_canonica",
    "transicoes_de",
]
