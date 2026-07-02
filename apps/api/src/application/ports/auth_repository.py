"""Porta de acesso às tabelas de autenticação (migração Supabase->local).

Abstrai as funções ``private.auth_*`` (SECURITY DEFINER) usadas no caminho
PRÉ-AUTENTICAÇÃO (login/refresh/logout). Roda numa sessão de SISTEMA (sem claims,
no role de runtime) — nunca na sessão RLS de request. As credenciais/refresh
tokens ficam fora do alcance direto do role de cliente (RLS deny-all); só estas
funções (e, portanto, esta porta) os tocam.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CredencialComPerfil:
    """Retorno de ``auth_credencial_por_email`` (credencial + perfil de domínio)."""

    user_id: str
    senha_hash: str
    ativo: bool
    setor: str
    administrador: bool
    email: str
    nome: str


@dataclass(frozen=True)
class PerfilAuth:
    """Retorno de ``auth_perfil_para_token`` (perfil para remontar os claims)."""

    user_id: str
    ativo: bool
    setor: str
    administrador: bool
    email: str
    nome: str


class AuthRepositoryPort(ABC):
    @abstractmethod
    async def credencial_por_email(self, email: str) -> CredencialComPerfil | None:
        """Credencial + perfil pelo e-mail (login); ``None`` se não existir."""

    @abstractmethod
    async def perfil_para_token(self, user_id: str) -> PerfilAuth | None:
        """Perfil atual para remontar os claims no refresh; ``None`` se não existir."""

    @abstractmethod
    async def criar_sessao(self, user_id: str, refresh_hash: str, expires_at: datetime) -> None:
        """Registra um refresh token (hash) — login."""

    @abstractmethod
    async def rotacionar_sessao(
        self, refresh_hash: str, novo_hash: str, expires_at: datetime
    ) -> str | None:
        """Valida+revoga o refresh corrente e emite um novo (atômico). Devolve o
        ``user_id`` quando válido; ``None`` se reusado/expirado/desconhecido."""

    @abstractmethod
    async def revogar_sessao(self, refresh_hash: str) -> None:
        """Revoga um refresh token — logout."""


__all__ = ["AuthRepositoryPort", "CredencialComPerfil", "PerfilAuth"]
