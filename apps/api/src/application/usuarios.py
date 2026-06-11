"""Casos de uso de gestão de usuários (W1-C04) — RF-018, RF-020, US-015.

Orquestra DUAS fontes de verdade que precisam andar juntas (ADR-025):
1. o usuário de AUTENTICAÇÃO no Supabase Auth (via ``IdentityProviderPort``);
2. a linha de DOMÍNIO em ``usuarios`` (via ``UsuariosRepositoryPort`` + UoW).

Estratégia contra falha parcial (RNF-015/RNF-017):
- CRIAR: auth primeiro, banco depois; se o banco falhar, a criação no auth é
  COMPENSADA (delete). Se a própria compensação falhar, fica um órfão MARCADO
  (``app_metadata.provisionado_por``) que a próxima tentativa ADOTA (remove e
  recria) — o retry do administrador converge, nunca duplica.
- DESATIVAR/REATIVAR/EDITAR: provedor primeiro (fail-closed: na dúvida o login
  fica bloqueado), banco depois; falha no banco reverte o provedor (best-effort
  com log CRITICAL para alerta — RNF-024).
"""

import logging
from dataclasses import dataclass

from src.application.ports.identity_provider import (
    MARCA_PROVISIONAMENTO,
    EmailJaExisteNoProvedorError,
    IdentityProviderError,
    IdentityProviderPort,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.application.ports.usuarios_repository import (
    FiltrosUsuarios,
    PaginaUsuarios,
    UsuariosRepositoryPort,
)
from src.domain.usuarios import (
    AutoDesativacaoError,
    AutoRemocaoDeAdminError,
    ErroDeDominio,
    Localizacao,
    Setor,
    UltimoAdminError,
    Usuario,
    normalizar_email,
    validar_localizacao,
    validar_senha,
)

logger = logging.getLogger("rastreio.usuarios")


class EmailJaCadastradoError(ErroDeDominio):
    """E-mail já pertence a um usuário (domínio ou provedor). Mapeado a 409."""

    codigo = "email_ja_cadastrado"

    def __init__(self) -> None:
        super().__init__("Já existe um usuário cadastrado com este e-mail.")


class UsuarioNaoEncontradoError(ErroDeDominio):
    """Usuário inexistente. Mapeado a 404 (mensagem única, sem enumeração)."""

    codigo = "usuario_nao_encontrado"

    def __init__(self) -> None:
        super().__init__("Usuário não encontrado.")


@dataclass(frozen=True)
class CriarUsuario:
    """Comando de criação — payload já validado em forma pela borda HTTP."""

    nome: str
    email: str
    senha: str
    setor: Setor
    localizacao: Localizacao | None = None
    administrador: bool = False


@dataclass(frozen=True)
class EditarUsuario:
    """Comando de edição parcial (PATCH). ``localizacao_informada`` distingue
    "limpar localização" (None explícito) de "não mexer" — e-mail e senha NÃO
    são editáveis nesta wave (identidade do auth; ver docs/usuarios.md)."""

    nome: str | None = None
    setor: Setor | None = None
    localizacao: Localizacao | None = None
    localizacao_informada: bool = False
    administrador: bool | None = None


def montar_app_metadata(setor: Setor, administrador: bool) -> dict[str, object]:
    """Claims persistidas no ``app_metadata`` do auth user — consumidas pelo
    Custom Access Token Hook/RLS no C05 (DP-5). ``provisionado_por`` marca a
    autoria do provisionamento (adoção de órfãos)."""
    return {
        "setor": setor.value,
        "administrador": administrador,
        "provisionado_por": MARCA_PROVISIONAMENTO,
    }


class UsuariosService:
    """Fachada dos casos de uso de usuários (uma instância por requisição)."""

    def __init__(
        self,
        repo: UsuariosRepositoryPort,
        identity: IdentityProviderPort,
        uow: UnitOfWork,
    ) -> None:
        self._repo = repo
        self._identity = identity
        self._uow = uow

    # ------------------------------------------------------------------ leitura
    async def obter(self, usuario_id: str) -> Usuario | None:
        return await self._repo.get(usuario_id)

    async def listar(self, filtros: FiltrosUsuarios) -> PaginaUsuarios:
        return await self._repo.listar(filtros.saneados())

    # ------------------------------------------------------------------- criar
    async def criar(self, cmd: CriarUsuario) -> Usuario:
        validar_senha(cmd.senha)
        validar_localizacao(cmd.setor, cmd.localizacao)
        email = normalizar_email(cmd.email)
        if await self._repo.get_by_email(email) is not None:
            raise EmailJaCadastradoError()

        metadata = montar_app_metadata(cmd.setor, cmd.administrador)
        auth_id = await self._criar_identidade(email, cmd.senha, metadata)
        usuario = Usuario(
            id=auth_id,
            nome=cmd.nome.strip(),
            email=email,
            setor=cmd.setor,
            localizacao=cmd.localizacao,
            administrador=cmd.administrador,
            ativo=True,
        )
        try:
            async with self._uow:
                await self._repo.add(usuario)
                await self._uow.commit()
        except Exception:
            await self._compensar_criacao(auth_id)
            raise
        logger.info(
            "usuário criado",
            extra={
                "event": "usuario_criado",
                "usuario_id": usuario.id,
                "setor": usuario.setor.value,
                "administrador": usuario.administrador,
            },
        )
        return usuario

    async def _criar_identidade(
        self, email: str, senha: str, metadata: dict[str, object]
    ) -> str:
        try:
            return await self._identity.create_user(email, senha, metadata)
        except EmailJaExisteNoProvedorError:
            if not await self._adotar_orfao(email):
                raise EmailJaCadastradoError() from None
            return await self._identity.create_user(email, senha, metadata)

    async def _adotar_orfao(self, email: str) -> bool:
        """Remove uma conta de auth ÓRFÃ (criada por nós, sem linha de domínio).

        Contas sem a nossa marca (criadas pelo dashboard) NUNCA são tocadas —
        o conflito vira 409 e a decisão fica com o administrador.
        """
        identidade = await self._identity.find_user_by_email(email)
        if identidade is None or not identidade.provisionado_por_nos:
            return False
        if await self._repo.get(identidade.id) is not None:
            return False  # conta completa e legítima
        await self._identity.delete_user(identidade.id)
        logger.warning(
            "órfão de provisionamento adotado (auth user removido para recriação)",
            extra={"event": "orfao_adotado", "auth_user_id": identidade.id},
        )
        return True

    async def _compensar_criacao(self, auth_id: str) -> None:
        """Desfaz a criação no auth após falha no banco. Engole a própria falha
        (com CRITICAL) para o erro ORIGINAL chegar ao chamador; o órfão marcado
        é recuperado pela adoção na próxima tentativa."""
        try:
            await self._identity.delete_user(auth_id)
            logger.warning(
                "compensação executada: auth user removido após falha no banco",
                extra={"event": "compensacao_criacao", "auth_user_id": auth_id},
            )
        except Exception:
            logger.critical(
                "compensação FALHOU: auth user órfão (marcado p/ adoção em retry)",
                exc_info=True,
                extra={"event": "compensacao_falhou", "auth_user_id": auth_id},
            )

    # ------------------------------------------------------------------ editar
    async def editar(self, ator: Usuario, usuario_id: str, edicao: EditarUsuario) -> Usuario:
        alvo = await self._repo.get(usuario_id)
        if alvo is None:
            raise UsuarioNaoEncontradoError()

        novo = self._aplicar_edicao(alvo, edicao)
        if novo == alvo:
            return alvo  # nada a fazer — idempotente (RNF-015)
        validar_localizacao(novo.setor, novo.localizacao)
        if alvo.administrador and not novo.administrador:
            if ator.id == alvo.id:
                raise AutoRemocaoDeAdminError()
            if alvo.ativo and await self._repo.count_admins_ativos(excluir_id=alvo.id) == 0:
                raise UltimoAdminError()

        precisa_sync = (
            novo.setor is not alvo.setor or novo.administrador != alvo.administrador
        )
        if precisa_sync:
            await self._identity.update_app_metadata(
                alvo.id, montar_app_metadata(novo.setor, novo.administrador)
            )
        try:
            async with self._uow:
                await self._repo.update(novo)
                await self._uow.commit()
        except Exception:
            if precisa_sync:
                await self._reverter_metadata(alvo)
            raise
        logger.info(
            "usuário editado",
            extra={"event": "usuario_editado", "usuario_id": novo.id},
        )
        return novo

    @staticmethod
    def _aplicar_edicao(alvo: Usuario, edicao: EditarUsuario) -> Usuario:
        novo = alvo
        if edicao.nome is not None:
            novo = novo.com(nome=edicao.nome.strip())
        if edicao.setor is not None:
            novo = novo.com(setor=edicao.setor)
        if edicao.localizacao_informada:
            novo = novo.com(localizacao=edicao.localizacao)
        elif novo.setor is not Setor.VENDEDOR:
            # setor deixou de ser Vendedor sem localização explícita: limpa o
            # campo em vez de falhar por um resíduo invisível ao operador
            novo = novo.com(localizacao=None)
        if edicao.administrador is not None:
            novo = novo.com(administrador=edicao.administrador)
        return novo

    async def _reverter_metadata(self, original: Usuario) -> None:
        try:
            await self._identity.update_app_metadata(
                original.id, montar_app_metadata(original.setor, original.administrador)
            )
        except Exception:
            logger.critical(
                "reversão de app_metadata FALHOU — claims do auth divergem do domínio",
                exc_info=True,
                extra={"event": "reversao_metadata_falhou", "usuario_id": original.id},
            )

    # ----------------------------------------------------------------- status
    async def alterar_status(self, ator: Usuario, usuario_id: str, ativo: bool) -> Usuario:
        alvo = await self._repo.get(usuario_id)
        if alvo is None:
            raise UsuarioNaoEncontradoError()
        if alvo.ativo == ativo:
            return alvo  # repetição converge sem efeito colateral (RNF-015)

        if not ativo:
            if ator.id == alvo.id:
                raise AutoDesativacaoError()
            if alvo.administrador and await self._repo.count_admins_ativos(
                excluir_id=alvo.id
            ) == 0:
                raise UltimoAdminError()

        # Provedor PRIMEIRO (fail-closed): se o banco falhar depois, o pior
        # estado é "parece ativo mas não loga" — nunca o inverso.
        await self._identity.set_banned(alvo.id, banned=not ativo)
        if not ativo:
            await self._revogar_sessoes(alvo.id)

        novo = alvo.com(ativo=ativo)
        try:
            async with self._uow:
                await self._repo.update(novo)
                await self._uow.commit()
        except Exception:
            await self._reverter_ban(alvo)
            raise
        logger.info(
            "status de usuário alterado",
            extra={"event": "usuario_status_alterado", "usuario_id": novo.id, "ativo": ativo},
        )
        return novo

    async def _revogar_sessoes(self, usuario_id: str) -> None:
        """Best-effort: o ban já bloqueia novos tokens/refresh; a revogação só
        encurta a janela do access token corrente (TTL)."""
        try:
            await self._identity.revoke_sessions(usuario_id)
        except IdentityProviderError:
            logger.warning(
                "revogação de sessões indisponível — tokens expiram pelo TTL",
                extra={"event": "revogacao_sessoes_falhou", "usuario_id": usuario_id},
            )

    async def _reverter_ban(self, original: Usuario) -> None:
        try:
            await self._identity.set_banned(original.id, banned=not original.ativo)
        except Exception:
            logger.critical(
                "reversão de ban FALHOU — status do auth diverge do domínio",
                exc_info=True,
                extra={"event": "reversao_ban_falhou", "usuario_id": original.id},
            )


__all__ = [
    "CriarUsuario",
    "EditarUsuario",
    "EmailJaCadastradoError",
    "UsuarioNaoEncontradoError",
    "UsuariosService",
    "montar_app_metadata",
]
