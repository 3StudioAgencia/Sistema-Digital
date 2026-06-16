"""Domínio do log de movimentações (W3-C11) — o registro imutável de auditoria.

Cada transição de estado bem-sucedida grava UMA ``Movimentacao`` (append-only,
RNF-006): é o "log de auditoria completo e imutável de todas as movimentações"
(incl. reprovações, reinícios e cancelamentos). DP-3: esta É a tabela de
auditoria — não há um ``audit_log`` separado (divergência DAT §2/Backlog C05
registrada em DECISIONS.md). A Timeline (C13) e a tela de Log de Auditoria (C20)
LEEM daqui; o C11 só ESCREVE.

Camada interna (CLAUDE.md §5.2): apenas stdlib + enums de domínio.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.provas import EstadoProva
from src.domain.state_machine.enums import Acao
from src.domain.usuarios import ErroDeDominio


class TransicaoIdempotenciaConflitoError(ErroDeDominio):
    """A mesma ``idempotency_key`` chegou para uma OPERAÇÃO diferente (outra prova
    ou outra ação) da já registrada — reenvio legítimo converge; chave reusada
    para algo diferente é erro do cliente (409), nunca duplicata nem sobrescrita
    (RNF-015). Espelha a ``CriacaoDivergenteError`` da criação (C06)."""

    codigo = "idempotencia_conflito"

    def __init__(self) -> None:
        super().__init__(
            "Esta operação já foi registrada com dados diferentes. "
            "Gere uma nova tentativa e tente de novo."
        )


@dataclass
class Movimentacao:
    """Uma transição registrada (append-only — sem update/delete; RNF-006).

    ``idempotency_key`` é a chave de idempotência por operação (RNF-015): o
    reenvio da MESMA transição reusa a chave e converge para a movimentação já
    gravada (UNIQUE no banco), sem duplicar. ``assinatura_ref`` aponta para a
    assinatura digital (RN-003) — o C12 fornece a referência real (e a FK à
    tabela ``signatures``); no C11 é um stub (coluna nullable — DP-1). ``ciclo``
    é o ``ciclo_atual`` da prova no instante da movimentação (preserva o
    histórico por ciclo — RN-006; o incremento do ciclo é do C15).
    """

    id: str
    prova_id: str
    estado_origem: EstadoProva
    estado_destino: EstadoProva
    acao: Acao
    ator_id: str
    idempotency_key: str
    ciclo: int = 1
    motivo: str | None = None
    assinatura_ref: str | None = None
    created_at: datetime | None = field(default=None, compare=False)


__all__ = ["Movimentacao", "TransicaoIdempotenciaConflitoError"]
