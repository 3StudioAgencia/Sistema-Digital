"""Detalhe/arte/etiqueta de UMA prova (W2-C08) — ``ProvasConsultaService``, offline.

Cobre os três caminhos de leitura pontual do C08 com dublês em memória:
- ``obter``: prova + nome do vendedor (DP-7);
- ``obter_arte``: bytes + content-type, resolvendo a prova ANTES de tocar o
  storage (anti-vazamento da key do R2 — DP-5);
- ``gerar_etiqueta``: PDF universal-em-escopo, nome via projetor + fallback "-" (DP-8).

Prova inexistente/fora-de-escopo é o MESMO 404 (``ProvaNaoEncontradaError``).
"""

import datetime as dt

import pytest
from src.application.ports.etiqueta import EtiquetaPort
from src.application.ports.provas_repository import (
    FiltrosProvas,
    PaginaProvas,
    ProvasRepositoryPort,
)
from src.application.ports.storage import StorageObjectNotFound
from src.application.provas import ProvasConsultaService
from src.domain.provas import EstadoProva, Prova, ProvaNaoEncontradaError, Rota
from src.domain.settings import ConfiguracaoEtiqueta

from tests.conftest import FakeStorage

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
VENDEDOR_ID = "22222222-2222-2222-2222-222222222222"
PROVA_ID = "33333333-3333-3333-3333-333333333333"


def _prova() -> Prova:
    return Prova(
        id=PROVA_ID,
        codigo="PRV-2026-06-ABCDEF",
        nome="Mussarela fatiada",
        requerimento="123456",
        cliente="Edulat",
        vendedor_id=VENDEDOR_ID,
        rota=Rota.MATRIZ,
        arte_key=f"provas/{PROVA_ID}/arte.png",
        arte_content_type="image/png",
        status=EstadoProva.CRIADA,
        ciclo_atual=1,
        created_at=dt.datetime(2026, 4, 27, tzinfo=dt.UTC),
    )


class FakeRepo(ProvasRepositoryPort):
    def __init__(self, prova: Prova | None, nomes: dict[str, str]) -> None:
        self._prova = prova
        self._nomes = nomes

    async def get(self, prova_id: str) -> Prova | None:
        return self._prova if self._prova and self._prova.id == prova_id else None

    async def nomes_de_vendedores(self, ids: list[str]) -> dict[str, str]:
        return {i: self._nomes[i] for i in ids if i in self._nomes}

    async def add(self, prova: Prova) -> None:  # pragma: no cover - leitura
        raise NotImplementedError

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

    async def buscar_por_codigo(self, codigo: str) -> Prova | None:  # pragma: no cover - C10
        raise NotImplementedError

    async def listar(self, filtros: FiltrosProvas) -> PaginaProvas:  # pragma: no cover
        raise NotImplementedError

    async def vendedor_ids_distintos(self) -> list[str]:  # pragma: no cover
        raise NotImplementedError


class FakeEtiqueta(EtiquetaPort):
    """Captura o nome/config recebidos — prova que o fallback/projetor e a
    configuração (W2-C09) chegaram ao gerador."""

    def __init__(self) -> None:
        self.ultimo_nome: str | None = None
        self.ultima_config: ConfiguracaoEtiqueta | None = None

    def gerar_pdf(
        self, prova: Prova, vendedor_nome: str, config: ConfiguracaoEtiqueta | None = None
    ) -> bytes:
        self.ultimo_nome = vendedor_nome
        self.ultima_config = config
        return b"%PDF-fake " + prova.codigo.encode()


class StorageProibido(FakeStorage):
    """Falha se ``download`` for chamado — prova que a prova é resolvida antes."""

    def download(self, key: str) -> bytes:
        raise AssertionError("storage não deveria ser tocado para prova fora do escopo")


class StorageSemObjeto(FakeStorage):
    """Objeto ausente no R2 (key perdida) para uma prova que existe/é visível."""

    def download(self, key: str) -> bytes:
        raise StorageObjectNotFound(key)


def _service(
    prova: Prova | None,
    nomes: dict[str, str] | None = None,
    storage: FakeStorage | None = None,
    etiqueta: EtiquetaPort | None = None,
) -> ProvasConsultaService:
    return ProvasConsultaService(
        repo=FakeRepo(prova, nomes or {}),
        storage=storage or FakeStorage(),
        etiqueta=etiqueta or FakeEtiqueta(),
    )


# ---------------------------------------------------------------------------
# obter (detalhe)
# ---------------------------------------------------------------------------
async def test_obter_devolve_prova_com_nome_do_vendedor() -> None:
    service = _service(_prova(), {VENDEDOR_ID: "Regiane"})

    item = await service.obter(PROVA_ID)

    assert item.prova.codigo == "PRV-2026-06-ABCDEF"
    assert item.prova.ciclo_atual == 1
    assert item.vendedor_nome == "Regiane"


async def test_obter_nome_nao_resolvido_fica_none() -> None:
    service = _service(_prova(), {})  # projetor não devolve o nome
    item = await service.obter(PROVA_ID)
    assert item.vendedor_nome is None


async def test_obter_de_prova_inexistente_ou_fora_de_escopo_e_404() -> None:
    service = _service(None)
    with pytest.raises(ProvaNaoEncontradaError, match=r"Prova não encontrada\."):
        await service.obter("00000000-0000-0000-0000-000000000099")


# ---------------------------------------------------------------------------
# obter_arte (proxy da arte — DP-5)
# ---------------------------------------------------------------------------
async def test_obter_arte_devolve_bytes_e_content_type() -> None:
    storage = FakeStorage()
    storage.upload(f"provas/{PROVA_ID}/arte.png", PNG_BYTES, "image/png")
    service = _service(_prova(), storage=storage)

    dados, content_type = await service.obter_arte(PROVA_ID)

    assert dados == PNG_BYTES
    assert content_type == "image/png"


async def test_obter_arte_de_prova_fora_de_escopo_e_404_sem_tocar_storage() -> None:
    """A prova é resolvida ANTES do storage: fora do escopo → 404 e o R2 nem é lido."""
    service = _service(None, storage=StorageProibido())
    with pytest.raises(ProvaNaoEncontradaError):
        await service.obter_arte("00000000-0000-0000-0000-000000000099")


async def test_obter_arte_com_objeto_ausente_no_r2_e_404_nao_503() -> None:
    """Prova VISÍVEL mas key perdida no R2 → 404 (inconsistência de dado), nunca o
    503 'storage_indisponivel' (que faria o cliente retentar em loop)."""
    service = _service(_prova(), storage=StorageSemObjeto())
    with pytest.raises(ProvaNaoEncontradaError):
        await service.obter_arte(PROVA_ID)


# ---------------------------------------------------------------------------
# gerar_etiqueta (universal-em-escopo — DP-8)
# ---------------------------------------------------------------------------
async def test_gerar_etiqueta_devolve_pdf_e_codigo_com_nome_resolvido() -> None:
    etiqueta = FakeEtiqueta()
    service = _service(_prova(), {VENDEDOR_ID: "Regiane"}, etiqueta=etiqueta)

    pdf, codigo = await service.gerar_etiqueta(PROVA_ID)

    assert codigo == "PRV-2026-06-ABCDEF"
    assert pdf.startswith(b"%PDF")
    assert etiqueta.ultimo_nome == "Regiane"  # nome resolvido via projetor (DP-7)


async def test_gerar_etiqueta_sem_nome_resolvido_usa_fallback_hifen() -> None:
    etiqueta = FakeEtiqueta()
    service = _service(_prova(), {}, etiqueta=etiqueta)  # projetor vazio

    await service.gerar_etiqueta(PROVA_ID)

    assert etiqueta.ultimo_nome == "-"  # nunca quebra a etiqueta por nome ausente


async def test_gerar_etiqueta_de_prova_inexistente_e_404() -> None:
    service = _service(None)
    with pytest.raises(ProvaNaoEncontradaError, match=r"Prova não encontrada\."):
        await service.gerar_etiqueta("00000000-0000-0000-0000-000000000099")
