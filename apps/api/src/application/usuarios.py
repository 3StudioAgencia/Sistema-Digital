"""Casos de uso de gestão de usuários (W1-C04; auth própria na migração local).

Orquestra DUAS escritas que agora vivem no MESMO banco (migração Supabase->local):
1. a linha de DOMÍNIO em ``usuarios`` (via ``UsuariosRepositoryPort``);
2. a CREDENCIAL de login em ``auth_credentials`` (via ``AuthCredentialsWriterPort``,
   que chama ``private.auth_criar_credencial``).

Como ambas são locais, a criação é **atômica** (uma transação — RNF-017): acabou a
máquina de compensação/adoção-de-órfão que o split externo do Supabase exigia. A
senha vira hash argon2id (``PasswordHasherPort``) e nunca trafega/persiste em claro.
Desativar ou mudar setor/perfil **revoga as sessões** do usuário (refresh tokens),
forçando re-login com claims novas — o access token vive no máximo o TTL curto.
"""

import logging
import uuid
from dataclasses import dataclass

from src.application.ports.auth_credentials_writer import AuthCredentialsWriterPort
from src.application.ports.password_hasher import PasswordHasherPort
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
    """E-mail já pertence a um usuário. Mapeado a 409."""

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
    são editáveis nesta wave (ver docs/usuarios.md)."""

    nome: str | None = None
    setor: Setor | None = None
    localizacao: Localizacao | None = None
    localizacao_informada: bool = False
    administrador: bool | None = None


class UsuariosService:
    """Fachada dos casos de uso de usuários (uma instância por requisição)."""

    def __init__(
        self,
        repo: UsuariosRepositoryPort,
        auth: AuthCredentialsWriterPort,
        hasher: PasswordHasherPort,
        uow: UnitOfWork,
    ) -> None:
        self._repo = repo
        self._auth = auth
        self._hasher = hasher
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
        senha_hash = self._hasher.hash(cmd.senha)
        usuario = Usuario(
            id=str(uuid.uuid4()),
            nome=cmd.nome.strip(),
            email=email,
            setor=cmd.setor,
            localizacao=cmd.localizacao,
            administrador=cmd.administrador,
            ativo=True,
        )
        # Uma transação (RNF-017): a pré-checagem de e-mail, a linha de domínio e a
        # credencial nascem/falham JUNTAS — órfão é impossível (fim da compensação).
        async with self._uow:
            if await self._repo.get_by_email(email) is not None:
                raise EmailJaCadastradoError()
            await self._repo.add(usuario)
            await self._auth.criar_credencial(usuario.id, email, senha_hash)
            await self._uow.commit()
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

    # ------------------------------------------------------------------ editar
    async def editar(self, ator: Usuario, usuario_id: str, edicao: EditarUsuario) -> Usuario:
        alvo = await self._repo.get(usuario_id)
        if alvo is None:
            raise UsuarioNaoEncontradoError()

        novo = self._aplicar_edicao(alvo, edicao)
        if novo == alvo:
            return alvo  # nada a fazer — idempotente (RNF-015)
        validar_localizacao(novo.setor, novo.localizacao)
        rebaixa_admin = alvo.administrador and not novo.administrador
        if rebaixa_admin:
            if ator.id == alvo.id:
                raise AutoRemocaoDeAdminError()
            # Fast-fail (UX); a checagem DECISIVA é refeita sob lock na transação.
            if alvo.ativo and await self._repo.count_admins_ativos(excluir_id=alvo.id) == 0:
                raise UltimoAdminError()

        # setor/administrador são CLAIMS (RLS/gates); ao mudá-los, revoga as sessões
        # para forçar re-login com claims frescas (o access token stale expira no TTL).
        muda_claims = novo.setor is not alvo.setor or novo.administrador != alvo.administrador
        async with self._uow:
            if rebaixa_admin and alvo.ativo:
                # Recheck ATÔMICO da RN-010: serializa com outras demoções/
                # desativações e reconta dentro da MESMA transação do UPDATE.
                await self._repo.travar_gestao_de_admins()
                if await self._repo.count_admins_ativos(excluir_id=alvo.id) == 0:
                    raise UltimoAdminError()
            await self._repo.update(novo)
            if muda_claims:
                await self._auth.revogar_sessoes(novo.id)
            await self._uow.commit()
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

    # ----------------------------------------------------------------- status
    async def alterar_status(self, ator: Usuario, usuario_id: str, ativo: bool) -> Usuario:
        alvo = await self._repo.get(usuario_id)
        if alvo is None:
            raise UsuarioNaoEncontradoError()
        if alvo.ativo == ativo:
            return alvo  # repetição converge (RNF-015): estado idêntico, no-op

        if not ativo:
            if ator.id == alvo.id:
                raise AutoDesativacaoError()
            # Fast-fail (UX); a checagem decisiva é refeita sob lock na transação.
            if alvo.administrador and await self._repo.count_admins_ativos(excluir_id=alvo.id) == 0:
                raise UltimoAdminError()

        novo = alvo.com(ativo=ativo)
        async with self._uow:
            if not ativo and alvo.administrador:
                # Recheck ATÔMICO da RN-010 (mesma razão do editar).
                await self._repo.travar_gestao_de_admins()
                if await self._repo.count_admins_ativos(excluir_id=alvo.id) == 0:
                    raise UltimoAdminError()
            await self._repo.update(novo)
            if not ativo:
                # Desativar mata as sessões: o refresh não renova e o gate já barra
                # por ``ativo`` a cada requisição (o access token stale expira no TTL).
                await self._auth.revogar_sessoes(novo.id)
            await self._uow.commit()
        logger.info(
            "status de usuário alterado",
            extra={"event": "usuario_status_alterado", "usuario_id": novo.id, "ativo": ativo},
        )
        return novo


__all__ = [
    "CriarUsuario",
    "EditarUsuario",
    "EmailJaCadastradoError",
    "UsuarioNaoEncontradoError",
    "UsuariosService",
]
