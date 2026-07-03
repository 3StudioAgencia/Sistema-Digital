"""UsuariosService (W1-C04; auth própria): criação ATÔMICA, RN-009/RN-010, revogação.

Tudo offline: repositório em memória + escritor de credenciais fake + hasher fake +
UoW de teste. Migração Supabase->local: acabou a compensação/adoção-de-órfão (a
credencial nasce na MESMA transação da linha de domínio). Desativar/mudar claims
revoga as sessões.
"""

import pytest
from src.application.ports.auth_credentials_writer import AuthCredentialsWriterPort
from src.application.ports.password_hasher import PasswordHasherPort
from src.application.ports.unit_of_work import UnitOfWork
from src.application.ports.usuarios_repository import (
    FiltrosUsuarios,
    PaginaUsuarios,
    UsuariosRepositoryPort,
)
from src.application.usuarios import (
    CriarUsuario,
    EditarUsuario,
    EmailJaCadastradoError,
    UsuarioNaoEncontradoError,
    UsuariosService,
)
from src.domain.usuarios import (
    AutoDesativacaoError,
    AutoRemocaoDeAdminError,
    Localizacao,
    LocalizacaoInvalidaError,
    SenhaFracaError,
    Setor,
    UltimoAdminError,
    Usuario,
)

SENHA_OK = "senha-forte-1"


# ---------------------------------------------------------------------------
# Dublês locais
# ---------------------------------------------------------------------------
class FakeUsuariosRepository(UsuariosRepositoryPort):
    def __init__(self) -> None:
        self.por_id: dict[str, Usuario] = {}
        self.fail_add: Exception | None = None
        self.fail_update: Exception | None = None
        self.travas = 0
        # Sequência opcional de retornos do count (simula corrida entre o
        # fast-fail e o recheck transacional); esgotada → contagem real.
        self.count_admins_sequencia: list[int] = []

    async def get(self, usuario_id: str) -> Usuario | None:
        return self.por_id.get(usuario_id)

    async def get_by_email(self, email: str) -> Usuario | None:
        alvo = email.lower()
        return next((u for u in self.por_id.values() if u.email.lower() == alvo), None)

    async def buscar_por_cod_vendedor_firebird(self, cod: int) -> Usuario | None:
        return next((u for u in self.por_id.values() if u.cod_vendedor_firebird == cod), None)

    async def add(self, usuario: Usuario) -> None:
        if self.fail_add is not None:
            raise self.fail_add
        self.por_id[usuario.id] = usuario

    async def update(self, usuario: Usuario) -> None:
        if self.fail_update is not None:
            raise self.fail_update
        self.por_id[usuario.id] = usuario

    async def listar(self, filtros: FiltrosUsuarios) -> PaginaUsuarios:
        items = sorted(self.por_id.values(), key=lambda u: u.nome.lower())
        inicio = (filtros.page - 1) * filtros.page_size
        return PaginaUsuarios(
            items=items[inicio : inicio + filtros.page_size],
            total=len(items),
            page=filtros.page,
            page_size=filtros.page_size,
        )

    async def count_admins_ativos(self, excluir_id: str | None = None) -> int:
        if self.count_admins_sequencia:
            return self.count_admins_sequencia.pop(0)
        return sum(
            1 for u in self.por_id.values() if u.administrador and u.ativo and u.id != excluir_id
        )

    async def travar_gestao_de_admins(self) -> None:
        self.travas += 1


class FakeAuthCredentialsWriter(AuthCredentialsWriterPort):
    def __init__(self) -> None:
        self.credenciais: dict[str, tuple[str, str]] = {}  # user_id -> (email, hash)
        self.revogadas: list[str] = []

    async def criar_credencial(self, user_id: str, email: str, senha_hash: str) -> None:
        self.credenciais[user_id] = (email, senha_hash)

    async def revogar_sessoes(self, user_id: str) -> None:
        self.revogadas.append(user_id)


class FakeHasher(PasswordHasherPort):
    def hash(self, senha: str) -> str:
        return f"hash::{senha}"

    def verificar(self, senha: str, hash_armazenado: str) -> bool:
        return hash_armazenado == f"hash::{senha}"

    def verificar_falso(self, senha: str) -> None:
        return None


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


ADMIN = Usuario(
    id="11111111-1111-1111-1111-111111111111",
    nome="Mônica",
    email="monica@3studio.test",
    setor=Setor.STUDIO,
    administrador=True,
)


def _montar(
    *, com_admin: bool = True
) -> tuple[UsuariosService, FakeUsuariosRepository, FakeAuthCredentialsWriter, FakeUnitOfWork]:
    repo = FakeUsuariosRepository()
    if com_admin:
        repo.por_id[ADMIN.id] = ADMIN
    auth = FakeAuthCredentialsWriter()
    uow = FakeUnitOfWork()
    service = UsuariosService(repo=repo, auth=auth, hasher=FakeHasher(), uow=uow)
    return service, repo, auth, uow


def _cmd(**overrides: object) -> CriarUsuario:
    base: dict[str, object] = {
        "nome": "  Mario Souza  ",
        "email": "Mario@Estudio.com.BR",
        "senha": SENHA_OK,
        "setor": Setor.VENDEDOR,
        "localizacao": Localizacao.MATRIZ,
        "administrador": False,
    }
    base.update(overrides)
    return CriarUsuario(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Criar — atômico (domínio + credencial numa transação)
# ---------------------------------------------------------------------------
async def test_criar_provisiona_dominio_e_credencial() -> None:
    service, repo, auth, uow = _montar()
    usuario = await service.criar(_cmd())

    assert usuario.nome == "Mario Souza"  # strip aplicado
    assert usuario.email == "mario@estudio.com.br"  # normalizado
    assert usuario.ativo is True
    assert repo.por_id[usuario.id] == usuario
    assert uow.commits == 1  # UMA transação — atômico
    # Credencial criada com hash (a senha NUNCA em claro).
    assert usuario.id in auth.credenciais
    email_cred, hash_cred = auth.credenciais[usuario.id]
    assert email_cred == "mario@estudio.com.br"
    assert hash_cred == f"hash::{SENHA_OK}"


async def test_criar_senha_fraca_nao_escreve() -> None:
    service, repo, auth, uow = _montar()
    with pytest.raises(SenhaFracaError):
        await service.criar(_cmd(senha="curta1"))
    assert auth.credenciais == {}
    assert repo.por_id.get(ADMIN.id) is ADMIN  # nada mais criado
    assert uow.commits == 0


async def test_criar_vendedor_sem_localizacao_rejeitado() -> None:
    service, _, auth, _ = _montar()
    with pytest.raises(LocalizacaoInvalidaError):
        await service.criar(_cmd(localizacao=None))
    assert auth.credenciais == {}


async def test_criar_nao_vendedor_com_localizacao_rejeitado() -> None:
    service, _, auth, _ = _montar()
    with pytest.raises(LocalizacaoInvalidaError):
        await service.criar(_cmd(setor=Setor.CLICHERIA, localizacao=Localizacao.FILIAL))
    assert auth.credenciais == {}


async def test_criar_email_ja_no_dominio_rejeitado() -> None:
    service, _, auth, uow = _montar()
    with pytest.raises(EmailJaCadastradoError):
        await service.criar(_cmd(email=ADMIN.email))
    assert auth.credenciais == {}
    assert uow.commits == 0


# ---------------------------------------------------------------------------
# Editar — RN-009/RN-010 + revogação de sessão ao mudar claims
# ---------------------------------------------------------------------------
def _vendedor(uid: str = "v1") -> Usuario:
    return Usuario(
        id=uid, nome="Ana", email=f"{uid}@x.y", setor=Setor.VENDEDOR, localizacao=Localizacao.FILIAL
    )


async def test_editar_nome_nao_revoga_sessoes() -> None:
    service, repo, auth, _ = _montar()
    repo.por_id["v1"] = _vendedor()
    editado = await service.editar(ADMIN, "v1", EditarUsuario(nome="Ana Maria"))
    assert editado.nome == "Ana Maria"
    assert auth.revogadas == []  # nome não é claim


async def test_editar_setor_revoga_sessoes() -> None:
    service, repo, auth, _ = _montar()
    repo.por_id["v1"] = _vendedor()
    editado = await service.editar(ADMIN, "v1", EditarUsuario(setor=Setor.CLICHERIA))
    assert editado.setor is Setor.CLICHERIA
    assert editado.localizacao is None  # limpa resíduo ao sair de Vendedor
    assert "v1" in auth.revogadas  # setor é claim → força re-login


async def test_editar_promove_admin_revoga_sessoes() -> None:
    service, repo, auth, _ = _montar()
    repo.por_id["s1"] = Usuario(id="s1", nome="Léo", email="l@x.y", setor=Setor.STUDIO)
    editado = await service.editar(ADMIN, "s1", EditarUsuario(administrador=True))
    assert editado.administrador is True
    assert "s1" in auth.revogadas  # administrador é claim


async def test_editar_para_vendedor_exige_localizacao() -> None:
    service, repo, _, _ = _montar()
    repo.por_id["c1"] = Usuario(id="c1", nome="Léo", email="l@x.y", setor=Setor.CLICHERIA)
    with pytest.raises(LocalizacaoInvalidaError):
        await service.editar(ADMIN, "c1", EditarUsuario(setor=Setor.VENDEDOR))


async def test_editar_auto_remocao_de_admin_negada() -> None:
    service, _, _, _ = _montar()
    with pytest.raises(AutoRemocaoDeAdminError):
        await service.editar(ADMIN, ADMIN.id, EditarUsuario(administrador=False))


async def test_editar_remover_ultimo_admin_ativo_negado() -> None:
    service, repo, _, _ = _montar(com_admin=False)
    unico = Usuario(id="a2", nome="Bia", email="b@x.y", setor=Setor.STUDIO, administrador=True)
    repo.por_id["a2"] = unico
    ator_externo = Usuario(
        id="fora", nome="X", email="x@x.y", setor=Setor.STUDIO, administrador=True
    )
    with pytest.raises(UltimoAdminError):
        await service.editar(ator_externo, "a2", EditarUsuario(administrador=False))


async def test_editar_sem_mudanca_e_noop_idempotente() -> None:
    service, repo, auth, uow = _montar()
    repo.por_id["v1"] = _vendedor()
    resultado = await service.editar(ADMIN, "v1", EditarUsuario(nome="Ana"))
    assert resultado == repo.por_id["v1"]
    assert uow.commits == 0
    assert auth.revogadas == []


async def test_editar_inexistente() -> None:
    service, _, _, _ = _montar()
    with pytest.raises(UsuarioNaoEncontradoError):
        await service.editar(ADMIN, "nao-existe", EditarUsuario(nome="X"))


async def test_recheck_transacional_do_ultimo_admin_no_editar() -> None:
    service, repo, auth, uow = _montar()
    repo.por_id["a2"] = Usuario(
        id="a2", nome="Bia", email="bia@x.y", setor=Setor.STUDIO, administrador=True
    )
    # 1ª contagem (fast-fail): 1 → passa; 2ª (recheck sob lock): 0 → nega.
    repo.count_admins_sequencia = [1, 0]
    with pytest.raises(UltimoAdminError):
        await service.editar(ADMIN, "a2", EditarUsuario(administrador=False))
    assert repo.travas == 1
    assert repo.por_id["a2"].administrador is True  # rebaixamento não aconteceu
    assert auth.revogadas == []  # revoke só após o update bem-sucedido
    assert uow.commits == 0


# ---------------------------------------------------------------------------
# Desativar/Reativar — US-015 + RN-010 + revogação de sessão
# ---------------------------------------------------------------------------
async def test_desativar_revoga_sessoes_e_persiste() -> None:
    service, repo, auth, uow = _montar()
    repo.por_id["v1"] = _vendedor()
    resultado = await service.alterar_status(ADMIN, "v1", ativo=False)
    assert resultado.ativo is False
    assert "v1" in auth.revogadas
    assert repo.por_id["v1"].ativo is False
    assert uow.commits == 1
    assert "v1" in repo.por_id  # histórico preservado (US-015)


async def test_auto_desativacao_negada() -> None:
    service, _, auth, _ = _montar()
    with pytest.raises(AutoDesativacaoError):
        await service.alterar_status(ADMIN, ADMIN.id, ativo=False)
    assert auth.revogadas == []


async def test_desativar_ultimo_admin_ativo_negado() -> None:
    service, repo, _, _ = _montar(com_admin=False)
    repo.por_id["a2"] = Usuario(
        id="a2", nome="Bia", email="b@x.y", setor=Setor.STUDIO, administrador=True
    )
    ator_externo = Usuario(
        id="fora", nome="X", email="x@x.y", setor=Setor.STUDIO, administrador=True
    )
    with pytest.raises(UltimoAdminError):
        await service.alterar_status(ator_externo, "a2", ativo=False)


async def test_desativar_ja_inativo_e_noop_idempotente() -> None:
    service, repo, auth, uow = _montar()
    repo.por_id["v1"] = _vendedor().com(ativo=False)
    resultado = await service.alterar_status(ADMIN, "v1", ativo=False)
    assert resultado.ativo is False
    assert uow.commits == 0
    assert auth.revogadas == []  # estado idêntico: nada a fazer


async def test_reativar_nao_revoga_sessoes() -> None:
    service, repo, auth, _ = _montar()
    repo.por_id["v1"] = _vendedor().com(ativo=False)
    resultado = await service.alterar_status(ADMIN, "v1", ativo=True)
    assert resultado.ativo is True
    assert auth.revogadas == []


async def test_recheck_transacional_do_ultimo_admin_no_desativar() -> None:
    service, repo, auth, uow = _montar()
    repo.por_id["a2"] = Usuario(
        id="a2", nome="Bia", email="bia@x.y", setor=Setor.STUDIO, administrador=True
    )
    repo.count_admins_sequencia = [1, 0]
    with pytest.raises(UltimoAdminError):
        await service.alterar_status(ADMIN, "a2", ativo=False)
    assert repo.travas == 1
    assert repo.por_id["a2"].ativo is True  # não persistiu
    assert auth.revogadas == []
    assert uow.commits == 0


# ---------------------------------------------------------------------------
# Listagem — clamps de paginação (RNF-019)
# ---------------------------------------------------------------------------
async def test_listar_clampa_paginacao() -> None:
    service, _, _, _ = _montar()
    pagina = await service.listar(FiltrosUsuarios(page=-3, page_size=9999))
    assert pagina.page == 1
    assert pagina.page_size == 100
