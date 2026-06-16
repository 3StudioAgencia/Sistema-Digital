"""Enums da máquina de estados (W3-C11) — sincronizados com o PostgreSQL.

Glossário canônico (CLAUDE.md §6): membro Python em MAIÚSCULA, valor em
``snake_case``/lowercase. ``Acao`` espelha o tipo PG ``acao_enum`` (migration
0015 — regra de sincronização Python↔banco do DAT §4.5).

``Rota`` e ``EstadoProva`` já existem em ``domain/provas.py`` (criados no C06);
reexportados aqui por conveniência do módulo (DAT §4.1: ``enums.py`` agrega os
enums do fluxo). ``Setor`` (escopo operacional) vem de ``domain/usuarios.py``.
"""

from enum import StrEnum

from src.domain.provas import EstadoProva, Rota
from src.domain.usuarios import Setor


class Acao(StrEnum):
    """Ações de transição (§6) — sincronizadas com ``acao_enum``.

    ``IDENTIFICAR_E_ASSINAR`` é o mecanismo padrão de avanço (§6: identificar →
    assinar → confirmar). ``APROVAR``/``REPROVAR`` são a escolha do vendedor nos
    estados de posse (RF-008). ``REINICIAR_CICLO``/``CANCELAR`` são as ações
    administrativas transversais (§6.6).
    """

    IDENTIFICAR_E_ASSINAR = "identificar_e_assinar"
    APROVAR = "aprovar"
    REPROVAR = "reprovar"
    REINICIAR_CICLO = "reiniciar_ciclo"
    CANCELAR = "cancelar"


class Autorizacao(StrEnum):
    """Quem pode acionar uma transição — a coluna "Ator" da §6.

    Os quatro primeiros membros espelham ``Setor`` (escopo operacional — RN-004:
    "apenas o usuário do setor autorizado para a próxima etapa"). ``ADMIN`` é o
    caso das ações "Exclusivo 3Studio" da Matriz §7 (Cancelar/Reiniciar): pela
    ADR-023, essas linhas chaveiam pela flag ``administrador`` (ORTOGONAL ao
    setor — um Vendedor-admin pode cancelar; um 3Studio não-admin, não), e não
    pelo setor ``studio``. O motor (``machine.autoriza``) resolve a diferença.
    """

    STUDIO = "studio"
    VENDEDOR = "vendedor"
    MOTORISTA = "motorista"
    CLICHERIA = "clicheria"
    ADMIN = "admin"


__all__ = [
    "Acao",
    "Autorizacao",
    "EstadoProva",
    "Rota",
    "Setor",
]
