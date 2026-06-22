"""Núcleo puro do Log de Auditoria (W6-C20) — sem banco, sem framework.

Trava o mapa ``Acao → EventoAuditoria`` (fonte única — DP-3), a heurística de
origem (User-Agent → rótulo) e o saneamento de paginação dos filtros.
"""

from datetime import date

import pytest
from src.domain.auditoria import (
    EVENTO_POR_ACAO,
    PAGE_SIZE_MAXIMO,
    PAGE_SIZE_PADRAO,
    EventoAuditoria,
    FiltrosAuditoria,
    rotulo_origem,
)
from src.domain.state_machine.enums import Acao


def test_evento_por_acao_cobre_todas_as_acoes() -> None:
    """As 5 ações da §6 mapeiam para um evento de transição (sem buraco)."""
    assert set(EVENTO_POR_ACAO) == set(Acao)
    assert EVENTO_POR_ACAO[Acao.IDENTIFICAR_E_ASSINAR] is EventoAuditoria.MUDOU_STATUS
    assert EVENTO_POR_ACAO[Acao.APROVAR] is EventoAuditoria.APROVOU_PROVA
    assert EVENTO_POR_ACAO[Acao.REPROVAR] is EventoAuditoria.REPROVOU_PROVA
    assert EVENTO_POR_ACAO[Acao.REINICIAR_CICLO] is EventoAuditoria.REINICIOU_CICLO
    assert EVENTO_POR_ACAO[Acao.CANCELAR] is EventoAuditoria.CANCELOU_PROVA


def test_eventos_nao_movimentacao_existem() -> None:
    """Os 2 eventos que o design pede além das movimentações (DP-1=C)."""
    assert EventoAuditoria.CRIOU_PROVA.value == "criou_prova"
    assert EventoAuditoria.ESCANEOU_QR.value == "escaneou_qr"


@pytest.mark.parametrize(
    ("ua", "esperado"),
    [
        (None, None),
        ("", None),
        (
            "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537 (KHTML) Chrome/120 Safari/537",
            "Aplicação Web · Chrome",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537 Chrome/120 Safari/537 Edg/120",
            "Aplicação Web · Edge",
        ),
        ("Mozilla/5.0 (X11; Linux) Gecko/20100101 Firefox/121", "Aplicação Web · Firefox"),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605 Version/17 Safari/605",
            "Aplicação Web · Safari",
        ),
        ("Mozilla/5.0 ... OPR/106", "Aplicação Web · Opera"),
        ("curl/8.4.0", "Aplicação Web"),
    ],
)
def test_rotulo_origem(ua: str | None, esperado: str | None) -> None:
    """Edge/Opera vêm ANTES de Chrome, e Chrome antes de Safari (ordem de
    especificidade): senão um UA do Edge seria rotulado "Chrome"."""
    assert rotulo_origem(ua) == esperado


def test_filtros_saneados_limita_paginacao() -> None:
    assert FiltrosAuditoria(page=0).saneados().page == 1
    assert FiltrosAuditoria(page=-5).saneados().page == 1
    assert FiltrosAuditoria(page_size=0).saneados().page_size == PAGE_SIZE_PADRAO
    assert FiltrosAuditoria(page_size=99999).saneados().page_size == PAGE_SIZE_MAXIMO
    assert FiltrosAuditoria(page_size=25).saneados().page_size == 25


def test_filtros_default() -> None:
    f = FiltrosAuditoria()
    assert f.ordem == "recentes"
    assert f.page == 1
    assert f.page_size == PAGE_SIZE_PADRAO
    assert f.eventos == ()
    assert f.ator_id is None


def test_filtros_preserva_periodo_e_eventos_no_saneamento() -> None:
    f = FiltrosAuditoria(
        eventos=(EventoAuditoria.CRIOU_PROVA,),
        de=date(2026, 6, 1),
        ate=date(2026, 6, 19),
        page_size=999,
    ).saneados()
    assert f.eventos == (EventoAuditoria.CRIOU_PROVA,)
    assert f.de == date(2026, 6, 1)
    assert f.ate == date(2026, 6, 19)
    assert f.page_size == PAGE_SIZE_MAXIMO
