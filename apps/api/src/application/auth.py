"""Casos de uso de autenticação própria (migração Supabase->local).

Login/refresh/logout — o caminho PRÉ-AUTENTICAÇÃO. Roda numa sessão de SISTEMA
(sem claims): valida credencial (argon2), emite o access token (ES256, contrato
de claims) e gere o refresh token ROTATIVO (persistido só como hash).

Anti-enumeração/anti-timing (RN-014 aplicado ao login): e-mail inexistente, senha
errada e usuário inativo devolvem o MESMO ``None`` (a borda mapeia a um 401
genérico). Quando o e-mail não existe, ainda gastamos o tempo de uma verificação
argon2 falsa (``verificar_falso``) para não vazar a existência por tempo.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.application.ports.auth_repository import AuthRepositoryPort
from src.application.ports.password_hasher import PasswordHasherPort
from src.application.ports.tokens import TokenIssuerPort
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.auth import gerar_refresh_token, hash_refresh_token
from src.domain.usuarios import normalizar_email

logger = logging.getLogger("rastreio.auth")


@dataclass(frozen=True)
class ResultadoAuth:
    """Tokens emitidos + o perfil do usuário (a borda seta cookies/responde)."""

    access_token: str
    refresh_token: str
    user_id: str
    email: str
    setor: str
    administrador: bool


class AutenticacaoService:
    def __init__(
        self,
        *,
        repo: AuthRepositoryPort,
        hasher: PasswordHasherPort,
        issuer: TokenIssuerPort,
        uow: UnitOfWork,
        refresh_ttl_seconds: int,
    ) -> None:
        self._repo = repo
        self._hasher = hasher
        self._issuer = issuer
        self._uow = uow
        self._refresh_ttl = refresh_ttl_seconds

    async def login(self, email: str, senha: str) -> ResultadoAuth | None:
        """Valida e-mail+senha; emite tokens. ``None`` se inválido/inativo."""
        cred = await self._repo.credencial_por_email(normalizar_email(email))
        if cred is None:
            # Sem conta: gasta o mesmo tempo de um verify real (anti-timing).
            self._hasher.verificar_falso(senha)
            return None
        if not self._hasher.verificar(senha, cred.senha_hash):
            return None
        if not cred.ativo:
            # Conta desativada: negação genérica (não revela que o e-mail existe).
            return None
        logger.info("login bem-sucedido", extra={"event": "login_ok", "usuario_id": cred.user_id})
        return await self._emitir(cred.user_id, cred.email, cred.setor, cred.administrador)

    async def refresh(self, refresh_token: str | None) -> ResultadoAuth | None:
        """Rotaciona o refresh token e emite um novo access. ``None`` se inválido."""
        if not refresh_token:
            return None
        novo_refresh = gerar_refresh_token()
        user_id = await self._repo.rotacionar_sessao(
            hash_refresh_token(refresh_token),
            hash_refresh_token(novo_refresh),
            self._expira_refresh(),
        )
        if user_id is None:
            # Refresh reusado/expirado/desconhecido: nada foi rotacionado.
            await self._uow.rollback()
            return None
        perfil = await self._repo.perfil_para_token(user_id)
        if perfil is None or not perfil.ativo:
            # Usuário sumiu/desativado desde a emissão: desfaz a rotação e nega.
            await self._uow.rollback()
            return None
        access = self._issuer.emitir_access(
            sub=perfil.user_id,
            email=perfil.email,
            setor=perfil.setor,
            administrador=perfil.administrador,
        )
        await self._uow.commit()
        return ResultadoAuth(
            access_token=access,
            refresh_token=novo_refresh,
            user_id=perfil.user_id,
            email=perfil.email,
            setor=perfil.setor,
            administrador=perfil.administrador,
        )

    async def logout(self, refresh_token: str | None) -> None:
        """Revoga o refresh token (idempotente). Os cookies são limpos na borda."""
        if refresh_token:
            await self._repo.revogar_sessao(hash_refresh_token(refresh_token))
            await self._uow.commit()

    async def _emitir(
        self, user_id: str, email: str, setor: str, administrador: bool
    ) -> ResultadoAuth:
        access = self._issuer.emitir_access(
            sub=user_id, email=email, setor=setor, administrador=administrador
        )
        refresh = gerar_refresh_token()
        await self._repo.criar_sessao(user_id, hash_refresh_token(refresh), self._expira_refresh())
        await self._uow.commit()
        return ResultadoAuth(
            access_token=access,
            refresh_token=refresh,
            user_id=user_id,
            email=email,
            setor=setor,
            administrador=administrador,
        )

    def _expira_refresh(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=self._refresh_ttl)


__all__ = ["AutenticacaoService", "ResultadoAuth"]
