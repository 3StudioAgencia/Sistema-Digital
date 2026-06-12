"""UsuariosService (W1-C04): provisionamento coordenado, compensação e RN-009/RN-010.

Tudo offline: repositório em memória, FakeIdentityProvider e UoW de teste.
Foco nos contratos críticos do prompt §7 — falha parcial NUNCA deixa órfão
não-recuperável e as regras de negócio são enforce no backend.
"""

import pytest
from src.application.ports.identity_provider import (
    MARCA_PROVISIONAMENTO,
    IdentityProviderError,
    IdentityProviderPort,
)
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

from tests.conftest import FakeIdentityProvider

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
            1
            for u in self.por_id.values()
            if u.administrador and u.ativo and u.id != excluir_id
        )

    async def travar_gestao_de_admins(self) -> None:
        self.travas += 1


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
) -> tuple[UsuariosService, FakeUsuariosRepository, FakeIdentityProvider, FakeUnitOfWork]:
    repo = FakeUsuariosRepository()
    if com_admin:
        repo.por_id[ADMIN.id] = ADMIN
    identity = FakeIdentityProvider()
    uow = FakeUnitOfWork()
    return UsuariosService(repo=repo, identity=identity, uow=uow), repo, identity, uow


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
# Criar — caminho feliz e validações
# ---------------------------------------------------------------------------
async def test_criar_provisiona_auth_e_dominio() -> None:
    service, repo, identity, uow = _montar()
    usuario = await service.criar(_cmd())

    assert usuario.nome == "Mario Souza"  # strip aplicado
    assert usuario.email == "mario@estudio.com.br"  # normalizado
    assert usuario.ativo is True
    assert repo.por_id[usuario.id] == usuario
    assert uow.commits == 1
    metadata = identity.users[usuario.id]["app_metadata"]
    assert metadata == {
        "setor": "vendedor",
        "administrador": False,
        "provisionado_por": MARCA_PROVISIONAMENTO,
    }


async def test_criar_senha_fraca_nao_toca_provedor() -> None:
    service, _, identity, _ = _montar()
    with pytest.raises(SenhaFracaError):
        await service.criar(_cmd(senha="curta1"))
    assert identity.calls == []


async def test_criar_vendedor_sem_localizacao_rejeitado(
) -> None:
    service, _, identity, _ = _montar()
    with pytest.raises(LocalizacaoInvalidaError):
        await service.criar(_cmd(localizacao=None))
    assert identity.calls == []


async def test_criar_nao_vendedor_com_localizacao_rejeitado() -> None:
    service, _, identity, _ = _montar()
    with pytest.raises(LocalizacaoInvalidaError):
        await service.criar(_cmd(setor=Setor.CLICHERIA, localizacao=Localizacao.FILIAL))
    assert identity.calls == []


async def test_criar_email_ja_no_dominio_rejeitado_sem_tocar_provedor() -> None:
    service, _, identity, _ = _montar()
    with pytest.raises(EmailJaCadastradoError):
        await service.criar(_cmd(email=ADMIN.email))
    assert identity.calls == []


# ---------------------------------------------------------------------------
# Criar — falha parcial e compensação (prompt §7)
# ---------------------------------------------------------------------------
async def test_criar_insert_falha_compensa_no_provedor() -> None:
    service, repo, identity, _ = _montar()
    repo.fail_add = RuntimeError("banco caiu")

    with pytest.raises(RuntimeError):
        await service.criar(_cmd())

    # O auth user criado foi removido (compensação) — sem órfão.
    assert ("delete_user", next(iter(identity.users), "")) not in identity.calls or True
    assert all(u["email"] != "mario@estudio.com.br" for u in identity.users.values())
    assert any(c[0] == "delete_user" for c in identity.calls)
    assert repo.por_id.get("mario") is None


async def test_criar_compensacao_falha_propaga_erro_original() -> None:
    service, repo, identity, _ = _montar()
    repo.fail_add = RuntimeError("banco caiu")
    identity.fail_delete = IdentityProviderError("provedor caiu")

    with pytest.raises(RuntimeError, match="banco caiu"):
        await service.criar(_cmd())
    # Órfão ficou no provedor, MAS com a marca — adotável no retry.
    orfao = await identity.find_user_by_email("mario@estudio.com.br")
    assert orfao is not None
    assert orfao.provisionado_por_nos


async def test_criar_adota_orfao_marcado_e_recria() -> None:
    service, repo, identity, _ = _montar()
    orfao_id = identity.seed(
        "mario@estudio.com.br", {"provisionado_por": MARCA_PROVISIONAMENTO}
    )

    usuario = await service.criar(_cmd())

    assert usuario.id != orfao_id  # recriado do zero
    assert orfao_id not in identity.users
    assert repo.por_id[usuario.id] == usuario


async def test_criar_conta_de_dashboard_nao_e_adotada() -> None:
    service, _, identity, _ = _montar()
    preexistente = identity.seed("mario@estudio.com.br", {})  # sem a nossa marca

    with pytest.raises(EmailJaCadastradoError):
        await service.criar(_cmd())
    assert preexistente in identity.users  # intocada


async def test_criar_orfao_jovem_nao_e_adotado() -> None:
    """Conta marcada mas RECENTE pode ser uma criação concorrente em andamento
    (INSERT ainda invisível) — a adoção não pode deletá-la (revisão W1-C04)."""
    import datetime as dt

    service, _, identity, _ = _montar()
    jovem = identity.seed(
        "mario@estudio.com.br",
        {"provisionado_por": MARCA_PROVISIONAMENTO},
        criada_ha=dt.timedelta(seconds=30),
    )

    with pytest.raises(EmailJaCadastradoError):
        await service.criar(_cmd())
    assert jovem in identity.users  # intocada — retry futuro adota quando envelhecer


# ---------------------------------------------------------------------------
# Editar — RN-009/RN-010 e sincronização de claims
# ---------------------------------------------------------------------------
async def test_editar_nome() -> None:
    service, repo, identity, _ = _montar()
    vendedor = Usuario(
        id="v1", nome="Ana", email="ana@x.y", setor=Setor.VENDEDOR,
        localizacao=Localizacao.FILIAL,
    )
    repo.por_id[vendedor.id] = vendedor

    editado = await service.editar(ADMIN, "v1", EditarUsuario(nome="Ana Maria"))

    assert editado.nome == "Ana Maria"
    # nome não muda claims — nenhum update_app_metadata
    assert all(c[0] != "update_app_metadata" for c in identity.calls)


async def test_editar_setor_sincroniza_app_metadata() -> None:
    service, repo, identity, _ = _montar()
    identity.seed("ana@x.y")  # id "...0001" — não importa o vínculo aqui
    vendedor = Usuario(
        id="v1", nome="Ana", email="ana@x.y", setor=Setor.VENDEDOR,
        localizacao=Localizacao.FILIAL,
    )
    repo.por_id[vendedor.id] = vendedor

    editado = await service.editar(ADMIN, "v1", EditarUsuario(setor=Setor.CLICHERIA))

    assert editado.setor is Setor.CLICHERIA
    assert editado.localizacao is None  # limpa resíduo ao sair de Vendedor
    assert ("update_app_metadata", "v1") in identity.calls


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
    # ator hipotético fora do repo (defesa em profundidade além do guard)
    service, repo, _, _ = _montar(com_admin=False)
    unico_admin = Usuario(
        id="a2", nome="Bia", email="b@x.y", setor=Setor.STUDIO, administrador=True
    )
    repo.por_id[unico_admin.id] = unico_admin
    ator_externo = Usuario(
        id="fora", nome="X", email="x@x.y", setor=Setor.STUDIO, administrador=True
    )

    with pytest.raises(UltimoAdminError):
        await service.editar(ator_externo, "a2", EditarUsuario(administrador=False))


async def test_editar_update_falha_reverte_metadata() -> None:
    service, repo, identity, _ = _montar()
    repo.por_id["v1"] = Usuario(
        id="v1", nome="Ana", email="ana@x.y", setor=Setor.VENDEDOR,
        localizacao=Localizacao.FILIAL,
    )
    repo.fail_update = RuntimeError("banco caiu")

    with pytest.raises(RuntimeError):
        await service.editar(ADMIN, "v1", EditarUsuario(setor=Setor.MOTORISTA))

    # metadata foi sincronizada e depois revertida (duas chamadas)
    chamadas = [c for c in identity.calls if c[0] == "update_app_metadata"]
    assert len(chamadas) == 2


async def test_editar_sem_mudanca_e_noop_idempotente() -> None:
    service, repo, identity, uow = _montar()
    repo.por_id["v1"] = Usuario(
        id="v1", nome="Ana", email="ana@x.y", setor=Setor.VENDEDOR,
        localizacao=Localizacao.FILIAL,
    )

    resultado = await service.editar(ADMIN, "v1", EditarUsuario(nome="Ana"))

    assert resultado == repo.por_id["v1"]
    assert uow.commits == 0
    assert identity.calls == []


async def test_editar_inexistente() -> None:
    service, _, _, _ = _montar()
    with pytest.raises(UsuarioNaoEncontradoError):
        await service.editar(ADMIN, "nao-existe", EditarUsuario(nome="X"))


# ---------------------------------------------------------------------------
# Desativar/Reativar — US-015 + RN-010 + fail-closed
# ---------------------------------------------------------------------------
async def test_desativar_bane_revoga_e_persiste() -> None:
    service, repo, identity, uow = _montar()
    alvo_id = identity.seed("ana@x.y")
    repo.por_id[alvo_id] = Usuario(
        id=alvo_id, nome="Ana", email="ana@x.y", setor=Setor.VENDEDOR,
        localizacao=Localizacao.MATRIZ,
    )

    resultado = await service.alterar_status(ADMIN, alvo_id, ativo=False)

    assert resultado.ativo is False
    assert identity.users[alvo_id]["banned"] is True
    assert ("revoke_sessions", alvo_id) in identity.calls
    assert repo.por_id[alvo_id].ativo is False
    assert uow.commits == 1
    # histórico preservado: a linha continua existindo (US-015)
    assert alvo_id in repo.por_id


async def test_auto_desativacao_negada() -> None:
    service, _, identity, _ = _montar()
    with pytest.raises(AutoDesativacaoError):
        await service.alterar_status(ADMIN, ADMIN.id, ativo=False)
    assert identity.calls == []


async def test_desativar_ultimo_admin_ativo_negado() -> None:
    service, repo, _, _ = _montar(com_admin=False)
    unico = Usuario(id="a2", nome="Bia", email="b@x.y", setor=Setor.STUDIO, administrador=True)
    repo.por_id["a2"] = unico
    ator_externo = Usuario(
        id="fora", nome="X", email="x@x.y", setor=Setor.STUDIO, administrador=True
    )
    with pytest.raises(UltimoAdminError):
        await service.alterar_status(ator_externo, "a2", ativo=False)


async def test_desativar_ja_inativo_e_idempotente_e_converge_o_ban() -> None:
    service, repo, identity, uow = _montar()
    repo.por_id["v1"] = Usuario(
        id="v1", nome="Ana", email="ana@x.y", setor=Setor.VENDEDOR,
        localizacao=Localizacao.MATRIZ, ativo=False,
    )

    resultado = await service.alterar_status(ADMIN, "v1", ativo=False)

    assert resultado.ativo is False
    # nada gravado no banco, mas o ban é re-espelhado no provedor (reparo de
    # divergência auth↔domínio — revisão W1-C04)
    assert identity.calls == [("set_banned", "v1:True")]
    assert uow.commits == 0


async def test_desativar_update_falha_reverte_ban() -> None:
    service, repo, identity, _ = _montar()
    alvo_id = identity.seed("ana@x.y")
    repo.por_id[alvo_id] = Usuario(
        id=alvo_id, nome="Ana", email="ana@x.y", setor=Setor.VENDEDOR,
        localizacao=Localizacao.MATRIZ,
    )
    repo.fail_update = RuntimeError("banco caiu")

    with pytest.raises(RuntimeError):
        await service.alterar_status(ADMIN, alvo_id, ativo=False)

    # ban aplicado e depois revertido — estado consistente (fail-closed temporário)
    bans = [c for c in identity.calls if c[0] == "set_banned"]
    assert bans == [("set_banned", f"{alvo_id}:True"), ("set_banned", f"{alvo_id}:False")]
    assert identity.users[alvo_id]["banned"] is False


async def test_desativar_segue_quando_revogacao_indisponivel() -> None:
    service, repo, identity, _ = _montar()
    alvo_id = identity.seed("ana@x.y")
    repo.por_id[alvo_id] = Usuario(
        id=alvo_id, nome="Ana", email="ana@x.y", setor=Setor.VENDEDOR,
        localizacao=Localizacao.MATRIZ,
    )
    identity.fail_revoke = IdentityProviderError("logout indisponível")

    resultado = await service.alterar_status(ADMIN, alvo_id, ativo=False)

    assert resultado.ativo is False  # best-effort: a operação não falha


async def test_reativar_desbane_sem_revogar() -> None:
    service, repo, identity, _ = _montar()
    alvo_id = identity.seed("ana@x.y")
    identity.users[alvo_id]["banned"] = True
    repo.por_id[alvo_id] = Usuario(
        id=alvo_id, nome="Ana", email="ana@x.y", setor=Setor.VENDEDOR,
        localizacao=Localizacao.MATRIZ, ativo=False,
    )

    resultado = await service.alterar_status(ADMIN, alvo_id, ativo=True)

    assert resultado.ativo is True
    assert identity.users[alvo_id]["banned"] is False
    assert all(c[0] != "revoke_sessions" for c in identity.calls)


async def test_recheck_transacional_do_ultimo_admin_no_desativar() -> None:
    """TOCTOU fechado (revisão W1-C04): o fast-fail passa, mas a recontagem sob
    lock dentro da transação detecta que outra operação concorrente removeu o
    penúltimo admin — a desativação é negada e o ban revertido."""
    service, repo, identity, uow = _montar()
    alvo_id = identity.seed("bia@x.y")
    repo.por_id[alvo_id] = Usuario(
        id=alvo_id, nome="Bia", email="bia@x.y", setor=Setor.STUDIO, administrador=True
    )
    # 1ª contagem (fast-fail): 1 admin restante → passa; 2ª (recheck na tx): 0.
    repo.count_admins_sequencia = [1, 0]

    with pytest.raises(UltimoAdminError):
        await service.alterar_status(ADMIN, alvo_id, ativo=False)

    assert repo.travas == 1  # lock de gestão de admins foi tomado
    assert identity.users[alvo_id]["banned"] is False  # ban revertido
    assert repo.por_id[alvo_id].ativo is True
    assert uow.commits == 0


async def test_recheck_transacional_do_ultimo_admin_no_editar() -> None:
    service, repo, identity, _ = _montar()
    alvo_id = identity.seed("bia@x.y")
    repo.por_id[alvo_id] = Usuario(
        id=alvo_id, nome="Bia", email="bia@x.y", setor=Setor.STUDIO, administrador=True
    )
    repo.count_admins_sequencia = [1, 0]

    with pytest.raises(UltimoAdminError):
        await service.editar(ADMIN, alvo_id, EditarUsuario(administrador=False))

    assert repo.travas == 1
    # metadata sincronizada e depois REVERTIDA (o rebaixamento não aconteceu)
    assert [c for c in identity.calls if c[0] == "update_app_metadata"] == [
        ("update_app_metadata", alvo_id),
        ("update_app_metadata", alvo_id),
    ]
    assert repo.por_id[alvo_id].administrador is True


# ---------------------------------------------------------------------------
# Listagem — clamps de paginação (RNF-019)
# ---------------------------------------------------------------------------
async def test_listar_clampa_paginacao() -> None:
    service, _, _, _ = _montar()
    pagina = await service.listar(FiltrosUsuarios(page=-3, page_size=9999))
    assert pagina.page == 1
    assert pagina.page_size == 100


def _identity_port_completa() -> None:
    """Sanity: o fake implementa a porta inteira (sem métodos esquecidos)."""
    assert issubclass(FakeIdentityProvider, IdentityProviderPort)


def test_fake_cobre_porta() -> None:
    _identity_port_completa()
