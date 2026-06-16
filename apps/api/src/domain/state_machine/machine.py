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
    "MotivoObrigatorioError",
    "TransicaoInvalidaError",
    "TransicaoNaoAutorizadaError",
    "autoriza",
    "avaliar_transicao",
    "transicoes_de",
]
