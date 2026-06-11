"""Domínio de usuários — entidade, enums e regras de negócio puras (W1-C04).

Camada interna da arquitetura hexagonal (CLAUDE.md §5.2): nenhum import de
framework, ORM ou IO. As regras aqui (RN-009, RN-010, política de senha) são a
fonte única — adapters e casos de uso as INVOCAM, nunca as reimplementam.

Modelo Setor x Administrador (DP-1/ADR-023): ``setor`` define o escopo
operacional (um por usuário — RN-009); ``administrador`` é um flag ORTOGONAL ao
setor (como no design: "Perfil" Admin/Usuário deriva do flag). O antigo conceito
"3Studio (Administrador)" dos Requisitos equivale a ``setor=studio +
administrador=true``.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum

# Política de senha (RF-018 / prompt W1-C04 §3.4): mínimo 8, com letra e número.
SENHA_TAMANHO_MINIMO = 8


class Setor(StrEnum):
    """Setores operacionais — sincronizados com o ``setor_enum`` do PostgreSQL.

    Membro em MAIÚSCULA, valor em lowercase (CLAUDE.md §6). O rótulo de UI do
    ``STUDIO`` é "3Studio" (frontend); o valor persistido é ``studio``.
    """

    STUDIO = "studio"
    VENDEDOR = "vendedor"
    MOTORISTA = "motorista"
    CLICHERIA = "clicheria"


class Localizacao(StrEnum):
    """Localização cadastral — APENAS informativa (RN-009: nunca roteia provas)."""

    MATRIZ = "matriz"
    FILIAL = "filial"


class ErroDeDominio(Exception):
    """Base das violações de regra de negócio. Mapeada a 422 na borda HTTP."""

    codigo = "regra_de_negocio"


class SenhaFracaError(ErroDeDominio):
    codigo = "senha_fraca"

    def __init__(self) -> None:
        super().__init__(
            f"Senha inválida: mínimo de {SENHA_TAMANHO_MINIMO} caracteres, "
            "com pelo menos uma letra e um número."
        )


class LocalizacaoInvalidaError(ErroDeDominio):
    codigo = "localizacao_invalida"


class AutoDesativacaoError(ErroDeDominio):
    """RN-010: um administrador não pode desativar a si mesmo."""

    codigo = "auto_desativacao"

    def __init__(self) -> None:
        super().__init__("Um administrador não pode desativar a própria conta.")


class AutoRemocaoDeAdminError(ErroDeDominio):
    """RN-010: permissões de administrador são geridas por OUTRO administrador."""

    codigo = "auto_remocao_admin"

    def __init__(self) -> None:
        super().__init__("Um administrador não pode remover a própria permissão de administrador.")


class UltimoAdminError(ErroDeDominio):
    """Salvaguarda RN-010: o sistema nunca fica sem administrador ativo."""

    codigo = "ultimo_admin"

    def __init__(self) -> None:
        super().__init__("Operação negada: este é o último administrador ativo do sistema.")


@dataclass
class Usuario:
    """Usuário de domínio — vinculado 1:1 ao usuário do Supabase Auth (ADR-024).

    ``id`` é o MESMO UUID de ``auth.users`` (string, como chega no ``sub`` do
    JWT). ``created_at``/``updated_at`` são preenchidos pela persistência.
    """

    id: str
    nome: str
    email: str
    setor: Setor
    localizacao: Localizacao | None = None
    administrador: bool = False
    ativo: bool = True
    created_at: datetime | None = field(default=None, compare=False)
    updated_at: datetime | None = field(default=None, compare=False)

    def com(self, **alteracoes: object) -> "Usuario":
        """Cópia com campos alterados (a entidade circula como valor imutável)."""
        return replace(self, **alteracoes)  # type: ignore[arg-type]


def normalizar_email(email: str) -> str:
    """E-mail canônico para unicidade: minúsculo e sem espaços nas pontas."""
    return email.strip().lower()


def validar_senha(senha: str) -> None:
    """Política de senha (RF-018): min. 8 caracteres, com letra E número.

    Validada aqui (fonte única) e refletida no frontend; o dashboard do Supabase
    deve ser configurado com a MESMA política (defesa em profundidade — DP-3).
    """
    if (
        len(senha) < SENHA_TAMANHO_MINIMO
        or not any(c.isalpha() for c in senha)
        or not any(c.isdigit() for c in senha)
    ):
        raise SenhaFracaError()


def validar_localizacao(setor: Setor, localizacao: Localizacao | None) -> None:
    """RN-009: localização é OBRIGATÓRIA para Vendedor e INDEVIDA para os demais.

    A restrição bidirecional impede drift silencioso (espelhada no CHECK da
    tabela ``usuarios`` — migration 0002).
    """
    if setor is Setor.VENDEDOR and localizacao is None:
        raise LocalizacaoInvalidaError("Vendedor exige localização (Matriz ou Filial) — RN-009.")
    if setor is not Setor.VENDEDOR and localizacao is not None:
        raise LocalizacaoInvalidaError(
            "Localização só se aplica ao setor Vendedor (RN-009)."
        )


__all__ = [
    "SENHA_TAMANHO_MINIMO",
    "AutoDesativacaoError",
    "AutoRemocaoDeAdminError",
    "ErroDeDominio",
    "Localizacao",
    "LocalizacaoInvalidaError",
    "SenhaFracaError",
    "Setor",
    "UltimoAdminError",
    "Usuario",
    "normalizar_email",
    "validar_localizacao",
    "validar_senha",
]
