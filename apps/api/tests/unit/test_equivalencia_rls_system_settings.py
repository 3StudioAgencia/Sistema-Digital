"""Equivalência anti-drift da RLS de ``system_settings`` (W2-C09).

Trava as policies entre o espelho versionado ``migrations/rls/system_settings_*.sql``
(DAT §2) e a migration ``0013`` que as aplica inline, e fixa a postura DP-2/DP-3
(leitura authenticated, escrita admin-only, sem DELETE). Roda offline; o
comportamento real contra o banco é coberto por ``test_rls_system_settings.py``.
"""

import re
from pathlib import Path

_API = Path(__file__).resolve().parents[2]
_RLS = _API / "migrations" / "rls"
_VERSIONS = _API / "migrations" / "versions"

ESPERADAS = {
    "system_settings_select_authenticated",
    "system_settings_insert_admin",
    "system_settings_update_admin",
}


def _policies(texto: str) -> set[str]:
    return set(re.findall(r"CREATE POLICY (\w+)", texto))


def test_policies_espelham_entre_sql_e_migration() -> None:
    de_arquivos: set[str] = set()
    for arquivo in _RLS.glob("system_settings_*.sql"):
        de_arquivos |= _policies(arquivo.read_text(encoding="utf-8"))
    das_migrations: set[str] = set()
    for versao in _VERSIONS.glob("0*.py"):
        das_migrations |= {
            p
            for p in _policies(versao.read_text(encoding="utf-8"))
            if p.startswith("system_settings_")
        }
    assert de_arquivos == das_migrations == ESPERADAS


def test_leitura_authenticated_escrita_admin_only() -> None:
    select = (_RLS / "system_settings_select_authenticated.sql").read_text(encoding="utf-8")
    insert = (_RLS / "system_settings_insert_admin.sql").read_text(encoding="utf-8")
    update = (_RLS / "system_settings_update_admin.sql").read_text(encoding="utf-8")
    # leitura aberta (DP-2): USING true e NÃO chaveia pelo flag admin
    assert "USING (true)" in select
    assert "app_is_admin" not in select
    # escrita exclusiva do flag admin (DP-3)
    assert "WITH CHECK (public.app_is_admin())" in insert
    assert "USING (public.app_is_admin())" in update


def test_grants_sem_delete_privilegio_minimo() -> None:
    grants = (_RLS / "system_settings_grants.sql").read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE system_settings TO authenticated" in grants
    assert "DELETE" not in grants  # a app nunca apaga config
