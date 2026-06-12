"""Matriz de Acesso por Perfil — nível de PÁGINA/AÇÃO (W1-C05).

Espelho de domínio (puro) da Matriz §7 (Requisitos v1.0), reconciliada com o
modelo ortogonal ``setor`` x ``administrador`` (ADR-023): as linhas "Exclusivo
3Studio" chaveiam pelo **flag** ``administrador``; as universais valem para
qualquer autenticado (o ESCOPO de dado é da RLS — vendedor/motorista no C06).

Esta é a MESMA política expressa em ``apps/web/src/lib/access-matrix.ts``; o
harness de equivalência (``tests/integration/test_equivalencia_matriz.py``)
assere que os dois espelhos não divergem (regra do PR único — DAT §7.3).

Nível de DADO (linha) — vendedor vê as próprias provas, motorista as "Em
Trânsito" — NÃO mora aqui: é RLS sobre ``provas`` (C06), composta com os helpers
SQL desta wave. Para ``usuarios`` o escopo de dado é a RLS já entregue no C05.
"""

from enum import StrEnum

from src.domain.usuarios import Usuario


class Recurso(StrEnum):
    """Recursos da Matriz §7 (páginas e ações sensíveis)."""

    # Universais — qualquer autenticado acessa a página (dado por RLS/escopo).
    DASHBOARD = "dashboard"
    ESCANEAR = "escanear"
    PROVAS = "provas"  # listagem + detalhe + timeline (◐ vendedor/motorista)

    # Exclusivos do Administrador (flag) — "Exclusivo 3Studio" na Matriz §7.
    CRIAR_PROVA = "criar_prova"
    CADASTRO_USUARIOS = "cadastro_usuarios"
    RELATORIOS = "relatorios"
    CONFIGURACOES = "configuracoes"
    LOG_AUDITORIA = "log_auditoria"
    REINICIAR_CICLO = "reiniciar_ciclo"
    CANCELAR_PROVA = "cancelar_prova"


# Acessível a qualquer usuário autenticado (●/◐ na coluna de página).
RECURSOS_UNIVERSAIS: frozenset[Recurso] = frozenset(
    {Recurso.DASHBOARD, Recurso.ESCANEAR, Recurso.PROVAS}
)

# Exclusivos do administrador (○ para os demais perfis).
RECURSOS_ADMIN: frozenset[Recurso] = frozenset(
    {
        Recurso.CRIAR_PROVA,
        Recurso.CADASTRO_USUARIOS,
        Recurso.RELATORIOS,
        Recurso.CONFIGURACOES,
        Recurso.LOG_AUDITORIA,
        Recurso.REINICIAR_CICLO,
        Recurso.CANCELAR_PROVA,
    }
)


def autorizar(usuario: Usuario, recurso: Recurso) -> bool:
    """Decisão de acesso por perfil ao ``recurso`` (nível de página/ação).

    Usuário inativo nunca acessa (defesa em profundidade — o ban do Auth já
    bloqueia o login, mas a autorização não confia só nisso). Recurso de admin
    exige o flag ``administrador``; recurso universal basta estar ativo.
    """
    if not usuario.ativo:
        return False
    if recurso in RECURSOS_ADMIN:
        return usuario.administrador
    if recurso in RECURSOS_UNIVERSAIS:
        return True
    return False  # recurso desconhecido: negação por padrão


__all__ = [
    "RECURSOS_ADMIN",
    "RECURSOS_UNIVERSAIS",
    "Recurso",
    "autorizar",
]
