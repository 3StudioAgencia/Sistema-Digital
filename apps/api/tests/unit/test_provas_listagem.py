"""Listagem de provas (W2-C07) — casos de uso de leitura, offline (sem Postgres).

Cobre o ``ProvasConsultaService`` com um repositório em memória: resolução de
nome do vendedor por PÁGINA (sem N+1 — RNF-022), composição correta da linha e o
saneamento dos filtros (clamp de paginação, trim da busca).
"""

import datetime as dt

import pytest
from src.application.ports.provas_repository import (
    PAGE_SIZE_MAXIMO,
    FiltrosProvas,
    PaginaProvas,
    ProvasRepositoryPort,
)
from src.application.provas import ProvasConsultaService
from src.domain.provas import EstadoProva, Prova, Rota


def _prova(vendedor_id: str, *, codigo: str = "PRV-2026-06-ABCDEF") -> Prova:
    return Prova(
        id=f"id-{codigo}",
        codigo=codigo,
        nome="Etiqueta",
        requerimento="155295",
        cliente="Cafe Caproni",
        vendedor_id=vendedor_id,
        rota=Rota.MATRIZ,
        arte_key="provas/x/arte.png",
        arte_content_type="image/png",
        status=EstadoProva.CRIADA,
        created_at=dt.datetime(2026, 4, 9, tzinfo=dt.UTC),
    )


class FakeProvasRepo(ProvasRepositoryPort):
    """Repositório em memória — conta quantas vezes resolve nomes (prova do N+1)."""

    def __init__(self, pagina: PaginaProvas, nomes: dict[str, str]) -> None:
        self._pagina = pagina
        self._nomes = nomes
        self.chamadas_nomes: list[list[str]] = []
        self.distintos: list[str] = []

    async def add(self, prova: Prova) -> None:  # pragma: no cover - não usado na leitura
        raise NotImplementedError

    async def get(self, prova_id: str) -> Prova | None:  # pragma: no cover
        raise NotImplementedError

    async def listar(self, filtros: FiltrosProvas) -> PaginaProvas:
        return self._pagina

    async def vendedor_ids_distintos(self) -> list[str]:
        return self.distintos

    async def nomes_de_vendedores(self, ids: list[str]) -> dict[str, str]:
        self.chamadas_nomes.append(ids)
        return {i: self._nomes[i] for i in ids if i in self._nomes}


async def test_listar_resolve_nome_do_vendedor_uma_vez_por_pagina() -> None:
    """Sem N+1: a página com 3 linhas de 2 vendedores faz UMA resolução de nomes."""
    pagina = PaginaProvas(
        items=[_prova("v1", codigo="PRV-2026-06-AAAAAA"), _prova("v2", codigo="PRV-2026-06-BBBBBB"),
               _prova("v1", codigo="PRV-2026-06-CCCCCC")],
        total=3,
        page=1,
        page_size=20,
    )
    repo = FakeProvasRepo(pagina, {"v1": "Regiane", "v2": "Packon"})
    service = ProvasConsultaService(repo)

    resultado = await service.listar(FiltrosProvas())

    assert len(repo.chamadas_nomes) == 1  # uma ida ao projetor, não por linha
    assert sorted(repo.chamadas_nomes[0]) == ["v1", "v2"]  # ids distintos
    nomes = {i.prova.codigo: i.vendedor_nome for i in resultado.items}
    assert nomes["PRV-2026-06-AAAAAA"] == "Regiane"
    assert nomes["PRV-2026-06-BBBBBB"] == "Packon"
    assert nomes["PRV-2026-06-CCCCCC"] == "Regiane"
    assert resultado.total == 3


async def test_listar_pagina_vazia_nao_chama_o_projetor() -> None:
    repo = FakeProvasRepo(PaginaProvas(items=[], total=0, page=1, page_size=20), {})
    service = ProvasConsultaService(repo)

    resultado = await service.listar(FiltrosProvas())

    assert resultado.items == []
    assert repo.chamadas_nomes == []  # nenhuma ida ao banco para 0 linhas


async def test_vendedores_para_dropdown_vem_ordenado_por_nome() -> None:
    repo = FakeProvasRepo(
        PaginaProvas(items=[], total=0, page=1, page_size=20),
        {"v1": "Regiane", "v2": "Adriana", "v3": "Packon"},
    )
    repo.distintos = ["v1", "v2", "v3"]
    service = ProvasConsultaService(repo)

    vendedores = await service.vendedores()

    assert [v.nome for v in vendedores] == ["Adriana", "Packon", "Regiane"]


async def test_vendedores_sem_provas_visiveis_retorna_lista_vazia() -> None:
    repo = FakeProvasRepo(PaginaProvas(items=[], total=0, page=1, page_size=20), {})
    service = ProvasConsultaService(repo)

    assert await service.vendedores() == []


@pytest.mark.parametrize(
    ("page", "page_size", "esperado_page", "esperado_size"),
    [
        (0, 20, 1, 20),  # page mínima = 1
        (1, 0, 1, 1),  # page_size mínimo = 1
        (1, 9999, 1, PAGE_SIZE_MAXIMO),  # clamp ao teto (RNF-019)
    ],
)
def test_filtros_saneados_clampa_paginacao(
    page: int, page_size: int, esperado_page: int, esperado_size: int
) -> None:
    saneado = FiltrosProvas(page=page, page_size=page_size).saneados()
    assert saneado.page == esperado_page
    assert saneado.page_size == esperado_size


def test_filtros_saneados_normaliza_busca_e_cliente() -> None:
    saneado = FiltrosProvas(busca="  granola  ", cliente="   ").saneados()
    assert saneado.busca == "granola"
    assert saneado.cliente is None  # só espaços vira None (filtro inativo)
