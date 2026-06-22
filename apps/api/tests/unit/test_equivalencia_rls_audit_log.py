"""Equivalência anti-drift da RLS de ``audit_log`` (W6-C20).

Mesmo princípio do ``test_equivalencia_rls_wave3``: a migration 0022 aplica a
policy e os grants como strings inline e ``migrations/rls/audit_log_*.sql`` são
espelhos de reaplicação manual (CLAUDE.md §9). Este harness trava os dois lados
offline (sem banco):

1. **Nome da policy** — mirror ⇔ migration ⇔ ``{audit_log_select_admin}`` (não há
   policy de INSERT: a escrita é só pela função DEFINER);
2. **Grants a ``authenticated`` na tabela** — mirror ⇔ migration ⇔ ``{SELECT}``.
   É o que fixa o invariante: ``audit_log`` NUNCA recebe INSERT/UPDATE/DELETE direto
   (a captura passa por ``private.audit_log_append``);
3. **Corpo da policy** (USING) — idêntico (insensível a espaços) entre os lados.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

_API = Path(__file__).resolve().parents[2]
_RLS = _API / "migrations" / "rls"
_VERSIONS = _API / "migrations" / "versions"

_POLICIES_ESPERADAS = {"audit_log_select_admin"}
_GRANTS_ESPERADOS = {"SELECT"}


def _carregar_migration(nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, _VERSIONS / f"{nome}.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _sem_espacos(sql: str) -> str:
    return re.sub(r"\s+", "", sql).rstrip(";")


def _create_policies_do_texto(texto: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"CREATE POLICY (\w+)", texto):
        inicio = m.start()
        fim = texto.find(";", inicio)
        out[m.group(1)] = texto[inicio:fim] if fim != -1 else texto[inicio:]
    return out


def _policies_da_migration(modulo: ModuleType, prefixo: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for valor in vars(modulo).values():
        if isinstance(valor, str) and "CREATE POLICY" in valor:
            for nome, corpo in _create_policies_do_texto(valor).items():
                if nome.startswith(prefixo):
                    out[nome] = corpo
    return out


def _grants_authenticated(texto: str, tabela: str) -> set[str]:
    privs: set[str] = set()
    for m in re.finditer(rf"GRANT ([A-Z, ]+?) ON TABLE {tabela} TO authenticated", texto):
        privs |= {p.strip() for p in m.group(1).split(",") if p.strip()}
    return privs


def _mirrors() -> dict[str, str]:
    de_arquivos: dict[str, str] = {}
    for arquivo in _RLS.glob("audit_log_*.sql"):
        de_arquivos.update(_create_policies_do_texto(arquivo.read_text(encoding="utf-8")))
    return de_arquivos


def test_nome_da_policy_bate_entre_espelho_e_migration() -> None:
    do_espelho = set(_mirrors())
    da_migration = set(_policies_da_migration(_carregar_migration("0022_audit_log"), "audit_log_"))
    assert do_espelho == _POLICIES_ESPERADAS
    assert da_migration == _POLICIES_ESPERADAS


def test_grants_a_authenticated_sao_somente_select() -> None:
    """``{SELECT}`` codifica o invariante: sem INSERT/UPDATE/DELETE direto — a
    escrita é exclusiva da função DEFINER. Um futuro GRANT INSERT/UPDATE/DELETE
    num dos lados quebra este teste."""
    grants_file = (_RLS / "audit_log_grants.sql").read_text(encoding="utf-8")
    do_espelho = _grants_authenticated(grants_file, "audit_log")
    da_migration = _grants_authenticated(
        (_VERSIONS / "0022_audit_log.py").read_text(encoding="utf-8"), "audit_log"
    )
    assert do_espelho == _GRANTS_ESPERADOS
    assert da_migration == _GRANTS_ESPERADOS


def test_corpo_da_policy_e_identico_entre_espelho_e_migration() -> None:
    espelho = _mirrors()
    inline = _policies_da_migration(_carregar_migration("0022_audit_log"), "audit_log_")
    assert set(espelho) == set(inline) == _POLICIES_ESPERADAS
    for nome in _POLICIES_ESPERADAS:
        assert _sem_espacos(espelho[nome]) == _sem_espacos(inline[nome]), nome
