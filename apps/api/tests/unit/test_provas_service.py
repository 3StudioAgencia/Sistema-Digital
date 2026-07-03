"""``ProvasService`` (Fatia 3) — criação por REQUERIMENTO: resolução no ERP,
mapeamento do vendedor, snapshot da imagem, atomicidade e idempotência.

Offline, com dublês: a ordem resolver→arte→upload→INSERT→commit e a compensação do
snapshot são o coração da RNF-017 (nunca prova órfã; objeto órfão só se a própria
compensação falhar — e aí com CRITICAL no log).
"""

import datetime as dt
import logging

import pytest
from src.application.ports.arte_fonte import ArteSelecionada
from src.application.ports.audit_log import AuditLogPort
from src.application.ports.provas_repository import (
    CodigoJaExisteError,
    FiltrosProvas,
    PaginaProvas,
    ProvaJaExisteError,
    ProvasRepositoryPort,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.application.ports.usuarios_repository import (
    FiltrosUsuarios,
    PaginaUsuarios,
    UsuariosRepositoryPort,
)
from src.application.provas import (
    MAX_TENTATIVAS_CODIGO,
    CriarProva,
    GeracaoDeCodigoEsgotadaError,
    ProvasService,
)
from src.domain.auditoria import EventoAuditoria, NovoEventoAuditoria
from src.domain.provas import (
    CriacaoDivergenteError,
    EstadoProva,
    Prova,
    Rota,
    VendedorInvalidoError,
    validar_codigo,
)
from src.domain.requerimentos import (
    ArteNaoDisponivelError,
    RequerimentoArte,
    RequerimentoIncompletoError,
    RequerimentoNaoEncontradoError,
    VendedorNaoMapeadoError,
)
from src.domain.usuarios import Localizacao, Setor, Usuario

from tests.conftest import FakeArteFonte, FakeRequerimentoReader, FakeStorage

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
QUANDO = dt.datetime(2026, 6, 12, tzinfo=dt.UTC)
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"
COD_REQ = 150288
COD_VENDE = 10

REQ = RequerimentoArte(
    cod_req_art=COD_REQ,
    nome="QUEIJO MUSSARELA FLORA MILK",
    cod_cliente=1058,
    nome_cliente="LATICINIOS FLORIDA LTDA",
    cod_vendedor=COD_VENDE,
    nome_vendedor="REGISLAINE PETRIM",
    cod_vend_fat=10,
    anexo_imagem="VERSAO_150288_V3.jpg",
)
ARTE_JPEG = ArteSelecionada(conteudo=JPEG, content_type="image/jpeg", nome_arquivo="V3.jpg")
ARTE_PNG = ArteSelecionada(conteudo=PNG, content_type="image/png", nome_arquivo="V3.png")


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------
class FakeProvasRepository(ProvasRepositoryPort):
    def __init__(self) -> None:
        self.provas: dict[str, Prova] = {}
        self.codigos_tentados: list[str] = []
        self.falhas_pendentes: list[Exception] = []

    async def add(self, prova: Prova) -> None:
        self.codigos_tentados.append(prova.codigo)
        if self.falhas_pendentes:
            raise self.falhas_pendentes.pop(0)
        prova.created_at = prova.updated_at = QUANDO
        self.provas[prova.id] = prova

    async def get(self, prova_id: str) -> Prova | None:
        return self.provas.get(prova_id)

    async def obter_para_transicao(self, prova_id: str) -> Prova | None:  # pragma: no cover
        raise NotImplementedError

    async def atualizar_status(
        self,
        prova_id: str,
        novo_status: EstadoProva,
        finalizada_em: dt.datetime | None,
        quando: dt.datetime,
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    async def incrementar_ciclo(self, prova_id: str) -> int:  # pragma: no cover
        raise NotImplementedError

    async def buscar_por_codigo(self, codigo: str) -> Prova | None:  # pragma: no cover
        raise NotImplementedError

    async def listar(self, filtros: FiltrosProvas) -> PaginaProvas:  # pragma: no cover
        raise NotImplementedError

    async def vendedor_ids_distintos(self) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    async def nomes_de_vendedores(self, ids: list[str]) -> dict[str, str]:  # pragma: no cover
        raise NotImplementedError


class FakeUsuariosRepository(UsuariosRepositoryPort):
    def __init__(self) -> None:
        self.usuarios: dict[str, Usuario] = {}

    async def get(self, usuario_id: str) -> Usuario | None:
        return self.usuarios.get(usuario_id)

    async def buscar_por_cod_vendedor_firebird(self, cod: int) -> Usuario | None:
        for u in self.usuarios.values():
            if u.cod_vendedor_firebird == cod:
                return u
        return None

    async def get_by_email(self, email: str) -> Usuario | None:  # pragma: no cover
        raise NotImplementedError

    async def add(self, usuario: Usuario) -> None:  # pragma: no cover
        raise NotImplementedError

    async def update(self, usuario: Usuario) -> None:  # pragma: no cover
        raise NotImplementedError

    async def listar(self, filtros: FiltrosUsuarios) -> PaginaUsuarios:  # pragma: no cover
        raise NotImplementedError

    async def count_admins_ativos(self, excluir_id: str | None = None) -> int:  # pragma: no cover
        raise NotImplementedError

    async def travar_gestao_de_admins(self) -> None:  # pragma: no cover
        raise NotImplementedError


class FakeUow(UnitOfWork):
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class StorageComDeleteQuebrado(FakeStorage):
    def delete(self, key: str) -> None:
        raise RuntimeError("delete indisponível")


class FakeAuditLog(AuditLogPort):
    def __init__(self) -> None:
        self.eventos: list[NovoEventoAuditoria] = []

    async def registrar(self, evento: NovoEventoAuditoria) -> None:
        self.eventos.append(evento)


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------
def _vendedor(
    ativo: bool = True, setor: Setor = Setor.VENDEDOR, cod: int | None = COD_VENDE
) -> Usuario:
    return Usuario(
        id=VENDEDOR_ID,
        nome="Renan Petrim",
        email="renan@x.z",
        setor=setor,
        localizacao=Localizacao.MATRIZ if setor is Setor.VENDEDOR else None,
        ativo=ativo,
        cod_vendedor_firebird=cod if setor is Setor.VENDEDOR else None,
    )


class _Ctx:
    def __init__(
        self,
        service: ProvasService,
        repo: FakeProvasRepository,
        storage: FakeStorage,
        uow: FakeUow,
        firebird: FakeRequerimentoReader,
        arte_fonte: FakeArteFonte,
        audit: FakeAuditLog,
    ) -> None:
        self.service = service
        self.repo = repo
        self.storage = storage
        self.uow = uow
        self.firebird = firebird
        self.arte_fonte = arte_fonte
        self.audit = audit


def _montar(
    vendedor: Usuario | None = None,
    *,
    req: RequerimentoArte | None = REQ,
    arte: ArteSelecionada = ARTE_JPEG,
    storage: FakeStorage | None = None,
) -> _Ctx:
    repo = FakeProvasRepository()
    usuarios = FakeUsuariosRepository()
    if vendedor is not None:
        usuarios.usuarios[vendedor.id] = vendedor
    storage = storage or FakeStorage()
    firebird = FakeRequerimentoReader({req.cod_req_art: req} if req is not None else {})
    arte_fonte = FakeArteFonte(arte)
    audit = FakeAuditLog()
    uow = FakeUow()
    service = ProvasService(
        repo=repo,
        usuarios_repo=usuarios,
        storage=storage,
        firebird=firebird,
        arte_fonte=arte_fonte,
        uow=uow,
        relogio=lambda: QUANDO,
        audit=audit,
    )
    return _Ctx(service, repo, storage, uow, firebird, arte_fonte, audit)


def _cmd(**overrides: object) -> CriarProva:
    base: dict[str, object] = {"cod_req_art": COD_REQ, "rota": Rota.MATRIZ}
    base.update(overrides)
    return CriarProva(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Caminho feliz
# ---------------------------------------------------------------------------
async def test_criar_resolve_no_erp_e_persiste_com_snapshot_da_arte() -> None:
    ctx = _montar(_vendedor())

    prova = await ctx.service.criar(_cmd())

    assert prova.status is EstadoProva.CRIADA  # US-001
    assert prova.rota is Rota.MATRIZ
    assert validar_codigo(prova.codigo)
    assert prova.nome == "QUEIJO MUSSARELA FLORA MILK"  # PRODART do ERP
    assert prova.cliente == "LATICINIOS FLORIDA LTDA"  # TB_CLIENTES.CLIENTE
    assert prova.requerimento == str(COD_REQ)
    assert prova.vendedor_id == VENDEDOR_ID  # COD_VENDE -> usuário do app
    assert prova.arte_key == f"provas/{prova.id}/arte.jpg"
    assert ctx.storage.download(prova.arte_key) == JPEG  # snapshot da fonte
    assert prova.arte_content_type == "image/jpeg"
    assert ctx.uow.commits == 1
    # o snapshot leu do share com os códigos do requerimento
    assert ctx.arte_fonte.chamadas == [(10, 1058, COD_REQ, "VERSAO_150288_V3.jpg")]


async def test_criar_detecta_png_pela_fonte() -> None:
    ctx = _montar(_vendedor(), arte=ARTE_PNG)
    prova = await ctx.service.criar(_cmd())
    assert prova.arte_key.endswith("/arte.png")
    assert prova.arte_content_type == "image/png"
    assert ctx.storage.download(prova.arte_key) == PNG


# ---------------------------------------------------------------------------
# Bloqueios de resolução (nada sobe ao storage nem ao banco)
# ---------------------------------------------------------------------------
async def test_requerimento_inexistente_bloqueia() -> None:
    ctx = _montar(_vendedor(), req=None)  # firebird não conhece o requerimento
    with pytest.raises(RequerimentoNaoEncontradoError):
        await ctx.service.criar(_cmd())
    assert ctx.repo.provas == {} and ctx.storage._objects == {}


_SEM_NOME = RequerimentoArte(COD_REQ, None, 1058, "Cli", COD_VENDE, "Vend", 10, "a.jpg")
_SEM_CLIENTE = RequerimentoArte(COD_REQ, "Prod", 1058, None, COD_VENDE, "Vend", 10, "a.jpg")
_SEM_FAT = RequerimentoArte(COD_REQ, "Prod", 1058, "Cli", COD_VENDE, "Vend", None, "a.jpg")


@pytest.mark.parametrize("req", [_SEM_NOME, _SEM_CLIENTE, _SEM_FAT])
async def test_requerimento_incompleto_bloqueia(req: RequerimentoArte) -> None:
    ctx = _montar(_vendedor(), req=req)
    with pytest.raises(RequerimentoIncompletoError):
        await ctx.service.criar(_cmd())
    assert ctx.repo.provas == {} and ctx.storage._objects == {}


async def test_vendedor_nao_mapeado_bloqueia() -> None:
    ctx = _montar(_vendedor(cod=999))  # nenhum usuário com COD_VENDE=10
    with pytest.raises(VendedorNaoMapeadoError):
        await ctx.service.criar(_cmd())
    assert ctx.repo.provas == {} and ctx.storage._objects == {}


async def test_vendedor_mapeado_mas_inativo_bloqueia() -> None:
    # tem o código (COD_VENDE=10) e é encontrado, mas está inativo → inválido.
    ctx = _montar(_vendedor(ativo=False))
    with pytest.raises(VendedorInvalidoError):
        await ctx.service.criar(_cmd())
    assert ctx.repo.provas == {} and ctx.storage._objects == {}


async def test_arte_indisponivel_no_share_bloqueia_sem_snapshot() -> None:
    ctx = _montar(_vendedor())
    ctx.arte_fonte.erro = ArteNaoDisponivelError()
    with pytest.raises(ArteNaoDisponivelError):
        await ctx.service.criar(_cmd())
    assert ctx.repo.provas == {} and ctx.storage._objects == {}  # nem chegou ao upload


# ---------------------------------------------------------------------------
# Colisão de código (DP-3) e atomicidade (RNF-017)
# ---------------------------------------------------------------------------
async def test_colisao_de_codigo_regenera_e_converge() -> None:
    ctx = _montar(_vendedor())
    ctx.repo.falhas_pendentes = [CodigoJaExisteError("PRV-X")]

    prova = await ctx.service.criar(_cmd())

    assert len(ctx.repo.codigos_tentados) == 2
    assert ctx.repo.codigos_tentados[0] != ctx.repo.codigos_tentados[1]
    assert ctx.storage.download(prova.arte_key) == JPEG  # snapshot não re-enviado
    assert ctx.uow.commits == 1


async def test_colisao_loga_criou_prova_uma_vez() -> None:
    ctx = _montar(_vendedor())
    ctx.repo.falhas_pendentes = [CodigoJaExisteError("PRV-X")]

    prova = await ctx.service.criar(_cmd())

    assert len(ctx.audit.eventos) == 1  # a tentativa que falhou não logou
    assert ctx.audit.eventos[0].evento is EventoAuditoria.CRIOU_PROVA
    assert ctx.audit.eventos[0].prova_id == prova.id


async def test_colisoes_esgotadas_viram_erro_interno_e_compensam() -> None:
    ctx = _montar(_vendedor())
    ctx.repo.falhas_pendentes = [CodigoJaExisteError("PRV-X")] * MAX_TENTATIVAS_CODIGO

    with pytest.raises(GeracaoDeCodigoEsgotadaError):
        await ctx.service.criar(_cmd())

    assert len(ctx.repo.codigos_tentados) == MAX_TENTATIVAS_CODIGO
    assert ctx.storage._objects == {}  # compensação removeu o snapshot
    assert ctx.repo.provas == {}


async def test_falha_no_insert_compensa_e_propaga() -> None:
    ctx = _montar(_vendedor())
    ctx.repo.falhas_pendentes = [RuntimeError("banco caiu")]

    with pytest.raises(RuntimeError, match="banco caiu"):
        await ctx.service.criar(_cmd())

    assert ctx.storage._objects == {}
    assert ctx.repo.provas == {}
    assert ctx.uow.rollbacks >= 1


async def test_compensacao_que_falha_loga_critical(caplog: pytest.LogCaptureFixture) -> None:
    ctx = _montar(_vendedor(), storage=StorageComDeleteQuebrado())
    ctx.repo.falhas_pendentes = [RuntimeError("banco caiu")]

    with (
        caplog.at_level(logging.CRITICAL, logger="rastreio.provas"),
        pytest.raises(RuntimeError, match="banco caiu"),
    ):
        await ctx.service.criar(_cmd())

    assert any(getattr(r, "event", "") == "compensacao_arte_falhou" for r in caplog.records)


# ---------------------------------------------------------------------------
# Idempotência por prova_id (RNF-015)
# ---------------------------------------------------------------------------
async def test_reenvio_converge_sem_reresolver_nem_reupload() -> None:
    ctx = _montar(_vendedor())
    chave = "33333333-3333-3333-3333-333333333333"
    primeira = await ctx.service.criar(_cmd(prova_id=chave))
    uploads_antes = dict(ctx.storage._objects)
    chamadas_antes = list(ctx.arte_fonte.chamadas)

    segunda = await ctx.service.criar(_cmd(prova_id=chave))

    assert segunda.id == primeira.id and segunda.codigo == primeira.codigo
    assert len(ctx.repo.provas) == 1
    assert ctx.storage._objects == uploads_antes  # convergiu ANTES do upload
    assert ctx.arte_fonte.chamadas == chamadas_antes  # não releu o share
    assert ctx.uow.commits == 1


async def test_mesma_chave_com_rota_diferente_e_409() -> None:
    ctx = _montar(_vendedor())
    chave = "33333333-3333-3333-3333-333333333333"
    await ctx.service.criar(_cmd(prova_id=chave, rota=Rota.MATRIZ))
    with pytest.raises(CriacaoDivergenteError):
        await ctx.service.criar(_cmd(prova_id=chave, rota=Rota.FILIAL))
    assert len(ctx.repo.provas) == 1


async def test_corrida_de_idempotencia_no_insert_converge_sem_compensar() -> None:
    ctx = _montar(_vendedor())
    chave = "44444444-4444-4444-4444-444444444444"
    existente = Prova(
        id=chave,
        codigo="PRV-2026-06-K3T9XB",
        nome="QUEIJO MUSSARELA FLORA MILK",
        requerimento=str(COD_REQ),
        cliente="LATICINIOS FLORIDA LTDA",
        vendedor_id=VENDEDOR_ID,
        rota=Rota.MATRIZ,
        arte_key=f"provas/{chave}/arte.jpg",
        arte_content_type="image/jpeg",
        created_at=QUANDO,
        updated_at=QUANDO,
    )
    ctx.repo.falhas_pendentes = [ProvaJaExisteError(chave)]

    async def get_pos_colisao(prova_id: str) -> Prova | None:
        return existente if ctx.repo.codigos_tentados else None

    ctx.repo.get = get_pos_colisao  # type: ignore[method-assign]

    prova = await ctx.service.criar(_cmd(prova_id=chave))

    assert prova is existente
    assert existente.arte_key in ctx.storage._objects  # compensação NÃO rodou
