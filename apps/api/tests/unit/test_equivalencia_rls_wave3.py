"""Equivalência anti-drift da RLS das tabelas da Wave 3 (remediação M-03).

A auditoria da Wave 3 (achado M-03) apontou que as migrations aplicam as policies
e grants como **strings SQL inline** e os arquivos ``migrations/rls/*.sql`` são
espelhos de reaplicação manual (CLAUDE.md §9: "reaplicar após DROP/recriação"),
mas o harness de equivalência offline só cobria ``provas_*`` e ``system_settings``.
Faltava travar ``movimentacoes_*`` (0015), ``assinaturas_*`` (0016) e
``rate_limit_contadores_*`` (0014) — justamente o log imutável e o comprovante.

O achado M-02 foi a **prova viva** de que esse drift acontece e passa despercebido.
Este módulo fecha a lacuna: para cada uma das três tabelas, trava o espelho contra
o SQL inline da migration em três níveis:

1. **Nomes de policy** — mirror ⇔ migration ⇔ conjunto literal esperado;
2. **Grants a ``authenticated``** — mirror ⇔ migration ⇔ conjunto esperado. É o que
   fixa o invariante APPEND-ONLY: ``movimentacoes``/``assinaturas`` recebem só
   ``SELECT, INSERT`` (UPDATE/DELETE jamais — RNF-006/RN-003);
3. **Corpo da policy** (USING/WITH CHECK) — comparação insensível a espaços entre
   mirror e migration: pega qualquer enfraquecimento silencioso da RLS.

Roda offline (sem banco); o comportamento real contra o Postgres é coberto pelos
testes @db (``test_rls_movimentacoes``/``test_rls_assinaturas``/
``test_rls_rate_limit``).
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

_API = Path(__file__).resolve().parents[2]
_RLS = _API / "migrations" / "rls"
_VERSIONS = _API / "migrations" / "versions"


def _carregar_migration(nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, _VERSIONS / f"{nome}.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _sem_espacos(sql: str) -> str:
    """Normaliza um statement SQL para comparação: remove TODO espaço em branco e
    o ``;`` final. Espaço entre tokens SQL não é semântico (não há literais com
    espaço significativo nestas policies), então isto é robusto contra a formatação
    multilinha do espelho vs. a string concatenada da migration — sem mascarar
    diferença de token (qualquer divergência de conteúdo permanece visível)."""
    return re.sub(r"\s+", "", sql).rstrip(";")


def _create_policies_do_texto(texto: str) -> dict[str, str]:
    """Extrai ``{nome: corpo}`` de cada ``CREATE POLICY`` presente no texto.

    O corpo vai do ``CREATE POLICY`` até o ``;`` seguinte (espelho .sql) ou ao fim
    da string literal (migration — as policies-alvo são constantes string puras,
    sem ``;``)."""
    nomes = list(re.finditer(r"CREATE POLICY (\w+)", texto))
    out: dict[str, str] = {}
    for m in nomes:
        inicio = m.start()
        fim = texto.find(";", inicio)
        corpo = texto[inicio:fim] if fim != -1 else texto[inicio:]
        out[m.group(1)] = corpo
    return out


def _policies_da_migration(modulo: ModuleType, prefixo: str) -> dict[str, str]:
    """Varre os atributos string do módulo da migration e devolve as policies cujo
    nome começa com ``prefixo`` (as três tabelas-alvo definem cada policy como uma
    constante string pura — não interpolada)."""
    out: dict[str, str] = {}
    for valor in vars(modulo).values():
        if isinstance(valor, str) and "CREATE POLICY" in valor:
            for nome, corpo in _create_policies_do_texto(valor).items():
                if nome.startswith(prefixo):
                    out[nome] = corpo
    return out


def _grants_authenticated(texto: str, tabela: str) -> set[str]:
    """Privilégios concedidos a ``authenticated`` na tabela (conjunto)."""
    privs: set[str] = set()
    for m in re.finditer(rf"GRANT ([A-Z, ]+?) ON TABLE {tabela} TO authenticated", texto):
        privs |= {p.strip() for p in m.group(1).split(",") if p.strip()}
    return privs


# (tabela, migration, prefixo_de_policy, policies esperadas, grants esperados)
_CASOS = [
    pytest.param(
        "movimentacoes",
        "0015_movimentacoes",
        "movimentacoes_",
        {"movimentacoes_select_por_prova_visivel", "movimentacoes_insert_ator_em_escopo"},
        {"SELECT", "INSERT"},
        id="movimentacoes",
    ),
    pytest.param(
        "assinaturas",
        "0016_assinaturas",
        "assinaturas_",
        {"assinaturas_select_por_prova_visivel", "assinaturas_insert_ator_em_escopo"},
        {"SELECT", "INSERT"},
        id="assinaturas",
    ),
    pytest.param(
        "rate_limit_contadores",
        "0014_rate_limit_identificacao",
        "rate_limit_contadores_",
        {"rate_limit_contadores_self"},
        {"SELECT", "INSERT", "UPDATE"},
        id="rate_limit_contadores",
    ),
]


def _mirrors_da_tabela(prefixo: str) -> dict[str, str]:
    de_arquivos: dict[str, str] = {}
    for arquivo in _RLS.glob(f"{prefixo}*.sql"):
        de_arquivos.update(_create_policies_do_texto(arquivo.read_text(encoding="utf-8")))
    return de_arquivos


@pytest.mark.parametrize(("tabela", "migration", "prefixo", "policies", "grants"), _CASOS)
def test_nomes_de_policy_batem_entre_espelho_e_migration(
    tabela: str, migration: str, prefixo: str, policies: set[str], grants: set[str]
) -> None:
    """Espelho 1:1 (DAT §2): os mesmos nomes de policy no .sql e na migration, e
    exatamente o conjunto esperado (pega policy adicionada/removida só num lado)."""
    do_espelho = set(_mirrors_da_tabela(prefixo))
    da_migration = set(_policies_da_migration(_carregar_migration(migration), prefixo))
    assert do_espelho == policies
    assert da_migration == policies


@pytest.mark.parametrize(("tabela", "migration", "prefixo", "policies", "grants"), _CASOS)
def test_grants_a_authenticated_batem_e_sao_append_only(
    tabela: str, migration: str, prefixo: str, policies: set[str], grants: set[str]
) -> None:
    """Grants do espelho ⇔ migration ⇔ esperado. Para ``movimentacoes``/
    ``assinaturas`` o conjunto ``{SELECT, INSERT}`` codifica o append-only: um
    futuro ``GRANT UPDATE``/``DELETE`` num dos lados quebra este teste."""
    grants_file = (_RLS / f"{prefixo}grants.sql").read_text(encoding="utf-8")
    do_espelho = _grants_authenticated(grants_file, tabela)
    da_migration = _grants_authenticated(
        (_VERSIONS / f"{migration}.py").read_text(encoding="utf-8"), tabela
    )
    assert do_espelho == grants
    assert da_migration == grants


@pytest.mark.parametrize(("tabela", "migration", "prefixo", "policies", "grants"), _CASOS)
def test_corpo_das_policies_e_identico_entre_espelho_e_migration(
    tabela: str, migration: str, prefixo: str, policies: set[str], grants: set[str]
) -> None:
    """O CORPO (USING/WITH CHECK) de cada policy é idêntico (insensível a espaços)
    entre o espelho e o SQL inline — pega enfraquecimento silencioso da RLS numa
    recriação que reaplica um espelho desatualizado (o cenário do achado M-03)."""
    espelho = _mirrors_da_tabela(prefixo)
    inline = _policies_da_migration(_carregar_migration(migration), prefixo)
    assert set(espelho) == set(inline) == policies
    for nome in policies:
        assert _sem_espacos(espelho[nome]) == _sem_espacos(inline[nome]), nome
