"""Adapter da porta de auth — chama as funções ``private.auth_*`` (migração local).

Session-bound (uma instância por requisição de auth). A sessão é de SISTEMA
(plain, no role de runtime, sem claims): as funções ``private.auth_*`` de
pré-autenticação têm ``EXECUTE`` concedido ao ``rastreio_runtime`` e rodam como
owner (SECURITY DEFINER), acessando ``auth_credentials``/``auth_sessions`` que a
RLS mantém deny-all para qualquer role de cliente.
"""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.auth_repository import (
    AuthRepositoryPort,
    CredencialComPerfil,
    PerfilAuth,
)

_CREDENCIAL_POR_EMAIL = text("SELECT * FROM private.auth_credencial_por_email(:email)")
_PERFIL_PARA_TOKEN = text("SELECT * FROM private.auth_perfil_para_token(:user_id)")
_CRIAR_SESSAO = text("SELECT private.auth_criar_sessao(:user_id, :refresh_hash, :expires_at)")
_ROTACIONAR_SESSAO = text(
    "SELECT * FROM private.auth_rotacionar_sessao(:refresh_hash, :novo_hash, :expires_at)"
)
_REVOGAR_SESSAO = text("SELECT private.auth_revogar_sessao(:refresh_hash)")


class SqlAlchemyAuthRepository(AuthRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def credencial_por_email(self, email: str) -> CredencialComPerfil | None:
        result = await self._session.execute(_CREDENCIAL_POR_EMAIL, {"email": email})
        row = result.mappings().first()
        if row is None:
            return None
        return CredencialComPerfil(
            user_id=str(row["user_id"]),
            senha_hash=row["senha_hash"],
            ativo=bool(row["ativo"]),
            setor=str(row["setor"]),
            administrador=bool(row["administrador"]),
            email=str(row["email"]),
            nome=str(row["nome"]),
        )

    async def perfil_para_token(self, user_id: str) -> PerfilAuth | None:
        result = await self._session.execute(_PERFIL_PARA_TOKEN, {"user_id": user_id})
        row = result.mappings().first()
        if row is None:
            return None
        return PerfilAuth(
            user_id=str(row["user_id"]),
            ativo=bool(row["ativo"]),
            setor=str(row["setor"]),
            administrador=bool(row["administrador"]),
            email=str(row["email"]),
            nome=str(row["nome"]),
        )

    async def criar_sessao(self, user_id: str, refresh_hash: str, expires_at: datetime) -> None:
        await self._session.execute(
            _CRIAR_SESSAO,
            {"user_id": user_id, "refresh_hash": refresh_hash, "expires_at": expires_at},
        )

    async def rotacionar_sessao(
        self, refresh_hash: str, novo_hash: str, expires_at: datetime
    ) -> str | None:
        row = (
            await self._session.execute(
                _ROTACIONAR_SESSAO,
                {"refresh_hash": refresh_hash, "novo_hash": novo_hash, "expires_at": expires_at},
            )
        ).first()
        return str(row[0]) if row is not None else None

    async def revogar_sessao(self, refresh_hash: str) -> None:
        await self._session.execute(_REVOGAR_SESSAO, {"refresh_hash": refresh_hash})


__all__ = ["SqlAlchemyAuthRepository"]
