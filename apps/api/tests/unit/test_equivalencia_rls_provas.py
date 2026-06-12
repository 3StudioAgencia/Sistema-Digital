"""Equivalência anti-drift da RLS de provas (W2-C06 — extensão do harness do C05).

O harness de página (``test_equivalencia_matriz.py``) trava espelhos da Matriz a
nível de PÁGINA. Aqui travamos as células de DADO de ``provas`` entre as três
fontes que precisam andar juntas:

1. o DOMÍNIO (``EstadoProva``/``ESTADOS_EM_TRANSITO``/``Rota``);
2. o espelho versionado ``migrations/rls/provas_*.sql`` (DAT §2);
3. a migration ``0008`` que aplica as policies inline (e a ``0007``, os enums).

O comportamento real contra o banco é coberto pelos testes @db
(``test_rls_provas.py``); este módulo roda offline e pega DRIFT entre arquivos.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from src.domain.provas import ESTADOS_EM_TRANSITO, EstadoProva, Rota

_API = Path(__file__).resolve().parents[2]
_RLS = _API / "migrations" / "rls"
_VERSIONS = _API / "migrations" / "versions"


def _carregar_migration(nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, _VERSIONS / f"{nome}.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _policies_de(texto: str) -> set[str]:
    return set(re.findall(r"CREATE POLICY (\w+)", texto))


def test_enums_da_migration_0007_espelham_o_dominio() -> None:
    """Sincronização Python ↔ PG (CLAUDE.md §6/DAT §4.5) — pega drift de enum."""
    mig = _carregar_migration("0007_provas")
    assert tuple(mig.ROTAS) == tuple(r.value for r in Rota)
    assert tuple(mig.ESTADOS) == tuple(e.value for e in EstadoProva)


def test_policy_motorista_usa_exatamente_os_estados_em_transito() -> None:
    """Matriz §7 ("Em Trânsito") = ESTADOS_EM_TRANSITO do domínio, nos dois espelhos."""
    esperados = {e.value for e in ESTADOS_EM_TRANSITO}
    for fonte in (
        (_RLS / "provas_select_motorista.sql").read_text(encoding="utf-8"),
        (_VERSIONS / "0008_rls_provas_e_runtime_role.py").read_text(encoding="utf-8"),
    ):
        bloco = fonte[fonte.index("provas_select_motorista") :]
        achados = set(re.findall(r"'(com_motorista_\w+)'", bloco))
        assert achados == esperados


def test_policy_vendedor_escopa_pelo_vendedor_id_do_claim() -> None:
    sql = (_RLS / "provas_select_vendedor.sql").read_text(encoding="utf-8")
    assert "public.app_setor() = 'vendedor'" in sql
    assert "vendedor_id = public.app_current_user_id()" in sql


def test_migration_0008_aplica_as_mesmas_policies_dos_espelhos_sql() -> None:
    """Regra do espelho 1:1 (DAT §2): policy na migration ⇔ arquivo em rls/."""
    de_arquivos: set[str] = set()
    for arquivo in _RLS.glob("provas_*.sql"):
        de_arquivos |= _policies_de(arquivo.read_text(encoding="utf-8"))
    da_migration = _policies_de(
        (_VERSIONS / "0008_rls_provas_e_runtime_role.py").read_text(encoding="utf-8")
    )
    assert de_arquivos == da_migration
    # cobertura mínima da Matriz: 5 escopos de SELECT + INSERT exclusivo de admin
    assert de_arquivos == {
        "provas_select_studio",
        "provas_select_clicheria",
        "provas_select_admin",
        "provas_select_vendedor",
        "provas_select_motorista",
        "provas_insert_admin",
    }


def test_runtime_role_e_nao_owner_nobypassrls_nos_dois_espelhos() -> None:
    """ADR-034 item 3: o role de runtime nasce sem LOGIN (nenhum segredo no repo)."""
    for fonte in (
        (_RLS / "_runtime_role.sql").read_text(encoding="utf-8"),
        (_VERSIONS / "0008_rls_provas_e_runtime_role.py").read_text(encoding="utf-8"),
    ):
        # NOLOGIN: o role nasce sem credencial — a senha é passo de operação,
        # nunca versionada (CLAUDE.md §9).
        assert "CREATE ROLE rastreio_runtime NOLOGIN NOINHERIT NOBYPASSRLS" in fonte
        assert "GRANT authenticated TO rastreio_runtime" in fonte
