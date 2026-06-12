"""Harness de equivalência (lado api) — W1-C05.

Trava ``domain/rbac.py`` à Matriz canônica
(``apps/web/src/lib/access-matrix.cells.json``) — o MESMO arquivo a que o lado
web (``access-matrix.equivalencia.test.ts``) trava ``access-matrix.ts``. Como as
duas implementações concordam com o mesmo espelho, concordam entre si (regra do
PR único — DAT §7.3 / CLAUDE.md §5.4).

Teste PURO (sem banco): cobre 100% das células de PÁGINA da Matriz. As células
de DADO (RLS) de ``usuarios`` são cobertas em ``test_rls_usuarios.py``; as de
``provas`` (vendedor/motorista) entram no C06 (DP-3).
"""

import json
from pathlib import Path

from src.domain.rbac import RECURSOS_ADMIN, RECURSOS_UNIVERSAIS, Recurso, autorizar
from src.domain.usuarios import Localizacao, Setor, Usuario

# apps/api/tests/unit/<este> → parents[3] = apps/ ; daí web/src/lib/...
_CELLS = Path(__file__).resolve().parents[3] / "web" / "src" / "lib" / "access-matrix.cells.json"


def _celulas() -> dict[str, str]:
    return json.loads(_CELLS.read_text(encoding="utf-8"))["celulas"]


_ADMIN = Usuario(
    id="a", nome="A", email="a@x.z", setor=Setor.STUDIO, administrador=True, ativo=True
)
_NAO_ADMIN = Usuario(
    id="b",
    nome="B",
    email="b@x.z",
    setor=Setor.VENDEDOR,
    localizacao=Localizacao.MATRIZ,
    administrador=False,
    ativo=True,
)


def test_conjunto_de_recursos_bate_com_a_matriz() -> None:
    assert {r.value for r in Recurso} == set(_celulas().keys())


def test_admin_universais_particionam_os_recursos() -> None:
    assert RECURSOS_ADMIN | RECURSOS_UNIVERSAIS == set(Recurso)
    assert RECURSOS_ADMIN.isdisjoint(RECURSOS_UNIVERSAIS)


def test_autorizar_concorda_com_a_matriz_em_todas_as_celulas() -> None:
    for recurso_str, politica in _celulas().items():
        recurso = Recurso(recurso_str)
        assert autorizar(_ADMIN, recurso) is True, recurso_str
        assert autorizar(_NAO_ADMIN, recurso) is (politica == "todos"), recurso_str


def test_usuario_inativo_e_negado_em_tudo() -> None:
    inativo = _ADMIN.com(ativo=False)
    for recurso in Recurso:
        assert autorizar(inativo, recurso) is False
