"""Porta de ESCRITA de credenciais (provisionamento — migração Supabase->local).

Usada pelo ``UsuariosService`` na sessão RLS do admin: cria a credencial de login
JUNTO com a linha de domínio (transação atômica — fim da compensação/órfão que o
split externo do Supabase exigia) e revoga sessões ao desativar/rebaixar. Fala com
as funções ``private.auth_*`` (SECURITY DEFINER) que checam ``app_is_admin()``.
"""

from abc import ABC, abstractmethod


class AuthCredentialsWriterPort(ABC):
    @abstractmethod
    async def criar_credencial(self, user_id: str, email: str, senha_hash: str) -> None:
        """Cria a credencial de login (mesma transação da linha de domínio)."""

    @abstractmethod
    async def revogar_sessoes(self, user_id: str) -> None:
        """Revoga TODAS as sessões (refresh tokens) do usuário — desativação ou
        mudança de privilégio (força re-login com claims novas)."""


__all__ = ["AuthCredentialsWriterPort"]
