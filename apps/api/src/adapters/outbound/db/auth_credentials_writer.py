"""Adapter de escrita de credenciais — funções ``private.auth_*`` (provisionamento).

Session-bound, roda na sessão RLS do admin (SET LOCAL ROLE authenticated + claims):
as funções DEFINER checam ``app_is_admin()`` por dentro (defesa em profundidade) e
escrevem em ``auth_credentials``/``auth_sessions`` (RLS deny-all para clientes).
Participa da MESMA transação da linha de domínio → criação atômica.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.auth_credentials_writer import AuthCredentialsWriterPort

_CRIAR_CREDENCIAL = text("SELECT private.auth_criar_credencial(:user_id, :email, :senha_hash)")
_REVOGAR_SESSOES = text("SELECT private.auth_revogar_sessoes_do_usuario(:user_id)")


class SqlAlchemyAuthCredentialsWriter(AuthCredentialsWriterPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def criar_credencial(self, user_id: str, email: str, senha_hash: str) -> None:
        await self._session.execute(
            _CRIAR_CREDENCIAL,
            {"user_id": user_id, "email": email, "senha_hash": senha_hash},
        )

    async def revogar_sessoes(self, user_id: str) -> None:
        await self._session.execute(_REVOGAR_SESSOES, {"user_id": user_id})


__all__ = ["SqlAlchemyAuthCredentialsWriter"]
