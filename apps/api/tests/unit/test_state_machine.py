"""Máquina de estados (W3-C11) — testes PUROS, célula a célula (cobertura ≥ 95%).

Estratégia de dupla escrituração: ``_ORACULO`` é uma transcrição INDEPENDENTE da
§6 (não importa ``_FLUXOS``); o teste assere que ``TRANSITION_RULES`` é igual ao
oráculo + o Cancelar transversal. Um typo em ``rules.py`` falha aqui (as duas
transcrições teriam de errar igual). Em seguida, os testes comportamentais do
motor (422/403/motivo/admin) e a travessia completa das quatro rotas.

Sem banco, sem IO: a §6 é regra pura (DAT §4).
"""

import itertools

import pytest
from src.domain.provas import EstadoProva as E
from src.domain.provas import Rota
from src.domain.state_machine.enums import Acao
from src.domain.state_machine.enums import Autorizacao as Az
from src.domain.state_machine.machine import (
    ACOES_ADMINISTRATIVAS,
    ACOES_AVANCO,
    MotivoObrigatorioError,
    TransicaoInvalidaError,
    TransicaoNaoAutorizadaError,
    autoriza,
    avaliar_transicao,
    exige_assinatura,
    sequencia_canonica,
    transicoes_de,
)
from src.domain.state_machine.rules import ESTADOS_TERMINAIS, TRANSITION_RULES, Transicao
from src.domain.usuarios import Setor

ID = Acao.IDENTIFICAR_E_ASSINAR
APROVAR = Acao.APROVAR
REPROVAR = Acao.REPROVAR
REINICIAR = Acao.REINICIAR_CICLO
CANCELAR = Acao.CANCELAR


def _av(perfil: Az, destino: E) -> Transicao:
    return Transicao(ID, perfil, destino)


def _aprovar() -> Transicao:
    return Transicao(APROVAR, Az.VENDEDOR, E.APROVADA_VENDEDOR)


def _reprovar() -> Transicao:
    return Transicao(REPROVAR, Az.VENDEDOR, E.REPROVADA_VENDEDOR, exige_motivo=True)


_REINICIAR = Transicao(REINICIAR, Az.ADMIN, E.CRIADA)
_CANCELAR = Transicao(CANCELAR, Az.ADMIN, E.CANCELADA, exige_motivo=True)


# Oráculo: transcrição INDEPENDENTE da §6.2—6.6 (sem o Cancelar transversal, que
# é acrescentado a todo estado ativo no teste de equivalência).
_ORACULO: dict[tuple[Rota, E], set[Transicao]] = {
    # §6.2 Matriz
    (Rota.MATRIZ, E.CRIADA): {_av(Az.VENDEDOR, E.RETIRADA_VENDEDOR)},
    (Rota.MATRIZ, E.RETIRADA_VENDEDOR): {_aprovar(), _reprovar()},
    (Rota.MATRIZ, E.APROVADA_VENDEDOR): {_av(Az.STUDIO, E.DE_VOLTA_STUDIO)},
    (Rota.MATRIZ, E.DE_VOLTA_STUDIO): {_av(Az.MOTORISTA, E.COM_MOTORISTA_ENTREGA_FINAL)},
    (Rota.MATRIZ, E.COM_MOTORISTA_ENTREGA_FINAL): {_av(Az.CLICHERIA, E.RECEBIDA_CLICHERIA)},
    (Rota.MATRIZ, E.REPROVADA_VENDEDOR): {_REINICIAR},
    # §6.3 Lam. Matriz
    (Rota.LAM_MATRIZ, E.CRIADA): {_av(Az.STUDIO, E.ENCAMINHADA_PARA_LAMINACAO)},
    (Rota.LAM_MATRIZ, E.ENCAMINHADA_PARA_LAMINACAO): {
        _av(Az.MOTORISTA, E.COM_MOTORISTA_IDA_LAMINACAO)
    },
    (Rota.LAM_MATRIZ, E.COM_MOTORISTA_IDA_LAMINACAO): {_av(Az.CLICHERIA, E.LAMINACAO_CONCLUIDA)},
    (Rota.LAM_MATRIZ, E.LAMINACAO_CONCLUIDA): {
        _av(Az.MOTORISTA, E.COM_MOTORISTA_VOLTA_LAMINACAO)
    },
    (Rota.LAM_MATRIZ, E.COM_MOTORISTA_VOLTA_LAMINACAO): {
        _av(Az.STUDIO, E.DE_VOLTA_STUDIO_POS_LAMINACAO)
    },
    (Rota.LAM_MATRIZ, E.DE_VOLTA_STUDIO_POS_LAMINACAO): {_av(Az.VENDEDOR, E.RETIRADA_VENDEDOR)},
    (Rota.LAM_MATRIZ, E.RETIRADA_VENDEDOR): {_aprovar(), _reprovar()},
    (Rota.LAM_MATRIZ, E.APROVADA_VENDEDOR): {_av(Az.STUDIO, E.DE_VOLTA_STUDIO)},
    (Rota.LAM_MATRIZ, E.DE_VOLTA_STUDIO): {_av(Az.MOTORISTA, E.COM_MOTORISTA_ENTREGA_FINAL)},
    (Rota.LAM_MATRIZ, E.COM_MOTORISTA_ENTREGA_FINAL): {_av(Az.CLICHERIA, E.RECEBIDA_CLICHERIA)},
    (Rota.LAM_MATRIZ, E.REPROVADA_VENDEDOR): {_REINICIAR},
    # §6.4 Filial
    (Rota.FILIAL, E.CRIADA): {_av(Az.VENDEDOR, E.ENCAMINHADA_PARA_VENDEDOR)},
    (Rota.FILIAL, E.ENCAMINHADA_PARA_VENDEDOR): {_aprovar(), _reprovar()},
    (Rota.FILIAL, E.APROVADA_VENDEDOR): {_av(Az.CLICHERIA, E.RECEBIDA_CLICHERIA)},
    (Rota.FILIAL, E.REPROVADA_VENDEDOR): {_REINICIAR},
    # §6.5 Lam. Filial
    (Rota.LAM_FILIAL, E.CRIADA): {_av(Az.STUDIO, E.ENCAMINHADA_PARA_LAMINACAO)},
    (Rota.LAM_FILIAL, E.ENCAMINHADA_PARA_LAMINACAO): {
        _av(Az.MOTORISTA, E.COM_MOTORISTA_IDA_LAMINACAO)
    },
    (Rota.LAM_FILIAL, E.COM_MOTORISTA_IDA_LAMINACAO): {_av(Az.CLICHERIA, E.LAMINACAO_CONCLUIDA)},
    (Rota.LAM_FILIAL, E.LAMINACAO_CONCLUIDA): {_av(Az.VENDEDOR, E.ENCAMINHADA_PARA_VENDEDOR)},
    (Rota.LAM_FILIAL, E.ENCAMINHADA_PARA_VENDEDOR): {_aprovar(), _reprovar()},
    (Rota.LAM_FILIAL, E.APROVADA_VENDEDOR): {_av(Az.CLICHERIA, E.RECEBIDA_CLICHERIA)},
    (Rota.LAM_FILIAL, E.REPROVADA_VENDEDOR): {_REINICIAR},
}


# ---------------------------------------------------------------------------
# Equivalência estrutural: TRANSITION_RULES == oráculo + Cancelar transversal
# ---------------------------------------------------------------------------
def test_chaves_de_rules_batem_com_o_oraculo() -> None:
    assert set(TRANSITION_RULES.keys()) == set(_ORACULO.keys())


@pytest.mark.parametrize("chave", list(_ORACULO.keys()))
def test_cada_celula_bate_com_o_oraculo_mais_cancelar(chave: tuple[Rota, E]) -> None:
    esperado = set(_ORACULO[chave]) | {_CANCELAR}
    assert set(TRANSITION_RULES[chave]) == esperado


def test_cancelar_existe_em_todo_estado_ativo_e_so_uma_vez() -> None:
    for (_rota, estado), transicoes in TRANSITION_RULES.items():
        assert estado not in ESTADOS_TERMINAIS
        cancelares = [t for t in transicoes if t.acao is CANCELAR]
        assert len(cancelares) == 1
        assert cancelares[0] == _CANCELAR


def test_estados_terminais_nunca_sao_origem() -> None:
    origens = {estado for _rota, estado in TRANSITION_RULES}
    assert ESTADOS_TERMINAIS.isdisjoint(origens)
    # E não há transição cujo destino "saia" de um terminal (eles não são chave).
    for terminal in ESTADOS_TERMINAIS:
        for rota in Rota:
            assert transicoes_de(rota, terminal) == ()


def test_todo_estado_nao_terminal_aparece_como_origem_em_alguma_rota() -> None:
    origens = {estado for _rota, estado in TRANSITION_RULES}
    ativos = set(E) - ESTADOS_TERMINAIS
    assert ativos == origens  # cobertura total dos 12 estados ativos


def test_contagem_de_transicoes_de_avanco_por_rota() -> None:
    """Cross-check do Backlog C11: Lam. Matriz 'percorre as 11', Lam. Filial 'as
    7' — avanços (IDENTIFICAR) + Reprovar, sem Cancelar/Reiniciar."""

    def avancos_e_reprovar(rota: Rota) -> int:
        return sum(
            1
            for (r, _e), ts in TRANSITION_RULES.items()
            if r is rota
            for t in ts
            if t.acao in (ID, APROVAR, REPROVAR)
        )

    assert avancos_e_reprovar(Rota.LAM_MATRIZ) == 11
    assert avancos_e_reprovar(Rota.LAM_FILIAL) == 7
    assert avancos_e_reprovar(Rota.MATRIZ) == 6  # 5 avanços + 1 reprovar
    assert avancos_e_reprovar(Rota.FILIAL) == 4  # 3 avanços + 1 reprovar


# ---------------------------------------------------------------------------
# Travessia completa (caminho feliz) de cada rota, com o perfil correto
# ---------------------------------------------------------------------------
_TRAVESSIAS: dict[Rota, list[tuple[E, Acao, Setor, E]]] = {
    Rota.MATRIZ: [
        (E.CRIADA, ID, Setor.VENDEDOR, E.RETIRADA_VENDEDOR),
        (E.RETIRADA_VENDEDOR, APROVAR, Setor.VENDEDOR, E.APROVADA_VENDEDOR),
        (E.APROVADA_VENDEDOR, ID, Setor.STUDIO, E.DE_VOLTA_STUDIO),
        (E.DE_VOLTA_STUDIO, ID, Setor.MOTORISTA, E.COM_MOTORISTA_ENTREGA_FINAL),
        (E.COM_MOTORISTA_ENTREGA_FINAL, ID, Setor.CLICHERIA, E.RECEBIDA_CLICHERIA),
    ],
    Rota.LAM_MATRIZ: [
        (E.CRIADA, ID, Setor.STUDIO, E.ENCAMINHADA_PARA_LAMINACAO),
        (E.ENCAMINHADA_PARA_LAMINACAO, ID, Setor.MOTORISTA, E.COM_MOTORISTA_IDA_LAMINACAO),
        (E.COM_MOTORISTA_IDA_LAMINACAO, ID, Setor.CLICHERIA, E.LAMINACAO_CONCLUIDA),
        (E.LAMINACAO_CONCLUIDA, ID, Setor.MOTORISTA, E.COM_MOTORISTA_VOLTA_LAMINACAO),
        (E.COM_MOTORISTA_VOLTA_LAMINACAO, ID, Setor.STUDIO, E.DE_VOLTA_STUDIO_POS_LAMINACAO),
        (E.DE_VOLTA_STUDIO_POS_LAMINACAO, ID, Setor.VENDEDOR, E.RETIRADA_VENDEDOR),
        (E.RETIRADA_VENDEDOR, APROVAR, Setor.VENDEDOR, E.APROVADA_VENDEDOR),
        (E.APROVADA_VENDEDOR, ID, Setor.STUDIO, E.DE_VOLTA_STUDIO),
        (E.DE_VOLTA_STUDIO, ID, Setor.MOTORISTA, E.COM_MOTORISTA_ENTREGA_FINAL),
        (E.COM_MOTORISTA_ENTREGA_FINAL, ID, Setor.CLICHERIA, E.RECEBIDA_CLICHERIA),
    ],
    Rota.FILIAL: [
        (E.CRIADA, ID, Setor.VENDEDOR, E.ENCAMINHADA_PARA_VENDEDOR),
        (E.ENCAMINHADA_PARA_VENDEDOR, APROVAR, Setor.VENDEDOR, E.APROVADA_VENDEDOR),
        (E.APROVADA_VENDEDOR, ID, Setor.CLICHERIA, E.RECEBIDA_CLICHERIA),
    ],
    Rota.LAM_FILIAL: [
        (E.CRIADA, ID, Setor.STUDIO, E.ENCAMINHADA_PARA_LAMINACAO),
        (E.ENCAMINHADA_PARA_LAMINACAO, ID, Setor.MOTORISTA, E.COM_MOTORISTA_IDA_LAMINACAO),
        (E.COM_MOTORISTA_IDA_LAMINACAO, ID, Setor.CLICHERIA, E.LAMINACAO_CONCLUIDA),
        (E.LAMINACAO_CONCLUIDA, ID, Setor.VENDEDOR, E.ENCAMINHADA_PARA_VENDEDOR),
        (E.ENCAMINHADA_PARA_VENDEDOR, APROVAR, Setor.VENDEDOR, E.APROVADA_VENDEDOR),
        (E.APROVADA_VENDEDOR, ID, Setor.CLICHERIA, E.RECEBIDA_CLICHERIA),
    ],
}


# ---------------------------------------------------------------------------
# Sequência canônica (W3-C13/DP-1) — DERIVADA de TRANSITION_RULES, consistente
# com a travessia feliz (oráculo independente). Garante que a Timeline desenha
# exatamente o caminho da máquina, sem duplicar a §6.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("rota", list(Rota))
def test_sequencia_canonica_bate_com_a_travessia_feliz(rota: Rota) -> None:
    # A cadeia de destinos da travessia feliz (começando em CRIADA) É a sequência
    # canônica — o oráculo independente prova que a derivação não driftou da §6.
    esperada = (E.CRIADA, *(destino for _o, _a, _s, destino in _TRAVESSIAS[rota]))
    assert sequencia_canonica(rota) == esperada


def test_sequencia_canonica_comprimentos_por_rota() -> None:
    """Backlog C13: Lam. Matriz percorre ~11 etapas; Filial ~4 (conta os nós)."""
    assert len(sequencia_canonica(Rota.MATRIZ)) == 6
    assert len(sequencia_canonica(Rota.LAM_MATRIZ)) == 11
    assert len(sequencia_canonica(Rota.FILIAL)) == 4
    assert len(sequencia_canonica(Rota.LAM_FILIAL)) == 7


@pytest.mark.parametrize("rota", list(Rota))
def test_sequencia_canonica_e_um_caminho_real_da_maquina(rota: Rota) -> None:
    seq = sequencia_canonica(rota)
    assert seq[0] == E.CRIADA
    assert seq[-1] == E.RECEBIDA_CLICHERIA
    # Desvios nunca entram no caminho canônico (são eventos, não etapas — C13).
    assert E.REPROVADA_VENDEDOR not in seq
    assert E.CANCELADA not in seq
    # Cada par consecutivo é a ÚNICA transição de avanço da §6 (consistência C11).
    for origem, destino in itertools.pairwise(seq):
        avancos = [t for t in transicoes_de(rota, origem) if t.acao in ACOES_AVANCO]
        assert len(avancos) == 1, f"{rota}/{origem} deve ter 1 avanço"
        assert avancos[0].estado_destino == destino


@pytest.mark.parametrize("rota", list(Rota))
def test_travessia_completa_da_rota(rota: Rota) -> None:
    estado = E.CRIADA
    for origem, acao, setor, destino in _TRAVESSIAS[rota]:
        assert estado == origem  # encadeamento contíguo
        t = avaliar_transicao(
            rota, estado, acao, setor=setor, administrador=False, motivo=None
        )
        assert t.estado_destino == destino
        estado = t.estado_destino
    assert estado in ESTADOS_TERMINAIS  # toda rota termina em Recebida pela Clicheria
    assert estado == E.RECEBIDA_CLICHERIA


# ---------------------------------------------------------------------------
# Desambiguação por rota (a rota decide o ator/destino do MESMO estado)
# ---------------------------------------------------------------------------
def test_aprovada_vendedor_vai_a_studio_na_matriz_e_clicheria_na_filial() -> None:
    t_matriz = avaliar_transicao(
        Rota.MATRIZ, E.APROVADA_VENDEDOR, ID,
        setor=Setor.STUDIO, administrador=False, motivo=None,
    )
    assert t_matriz.estado_destino == E.DE_VOLTA_STUDIO
    t_filial = avaliar_transicao(
        Rota.FILIAL, E.APROVADA_VENDEDOR, ID,
        setor=Setor.CLICHERIA, administrador=False, motivo=None,
    )
    assert t_filial.estado_destino == E.RECEBIDA_CLICHERIA
    # E o ator é exclusivo da rota: Clicheria não aprova→studio na Matriz, etc.
    with pytest.raises(TransicaoNaoAutorizadaError):
        avaliar_transicao(
            Rota.MATRIZ, E.APROVADA_VENDEDOR, ID,
            setor=Setor.CLICHERIA, administrador=False, motivo=None,
        )


def test_laminacao_concluida_vai_a_motorista_na_lam_matriz_e_vendedor_na_lam_filial() -> None:
    t_mat = avaliar_transicao(
        Rota.LAM_MATRIZ, E.LAMINACAO_CONCLUIDA, ID,
        setor=Setor.MOTORISTA, administrador=False, motivo=None,
    )
    assert t_mat.estado_destino == E.COM_MOTORISTA_VOLTA_LAMINACAO
    t_fil = avaliar_transicao(
        Rota.LAM_FILIAL, E.LAMINACAO_CONCLUIDA, ID,
        setor=Setor.VENDEDOR, administrador=False, motivo=None,
    )
    assert t_fil.estado_destino == E.ENCAMINHADA_PARA_VENDEDOR


# ---------------------------------------------------------------------------
# 422 — transição não definida (incl. cruzar rotas e estado terminal)
# ---------------------------------------------------------------------------
def test_acao_inaplicavel_ao_estado_e_422() -> None:
    with pytest.raises(TransicaoInvalidaError):
        avaliar_transicao(
            Rota.MATRIZ, E.CRIADA, APROVAR, setor=Setor.VENDEDOR, administrador=False, motivo=None
        )


def test_estado_inexistente_na_rota_e_422() -> None:
    # "Retirada pelo Vendedor" não existe na rota Filial.
    with pytest.raises(TransicaoInvalidaError):
        avaliar_transicao(
            Rota.FILIAL, E.RETIRADA_VENDEDOR, APROVAR,
            setor=Setor.VENDEDOR, administrador=False, motivo=None,
        )


@pytest.mark.parametrize("terminal", sorted(ESTADOS_TERMINAIS, key=lambda e: e.value))
@pytest.mark.parametrize("acao", list(Acao))
def test_qualquer_acao_a_partir_de_terminal_e_422(terminal: E, acao: Acao) -> None:
    with pytest.raises(TransicaoInvalidaError):
        avaliar_transicao(
            Rota.MATRIZ, terminal, acao, setor=Setor.STUDIO, administrador=True, motivo="x"
        )


# ---------------------------------------------------------------------------
# 403 — perfil não autorizado (rota+estado+ação válidos, ator errado)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("chave", list(_ORACULO.keys()))
def test_perfil_errado_em_toda_transicao_de_setor_da_403(chave: tuple[Rota, E]) -> None:
    rota, estado = chave
    for t in _ORACULO[chave]:
        if t.perfil_autorizado is Az.ADMIN:
            continue  # ações admin testadas à parte
        setor_certo = Setor(t.perfil_autorizado.value)
        for setor in Setor:
            if setor is setor_certo:
                continue
            # Mesmo um ator ADMIN de setor errado não passa um normal-flow.
            with pytest.raises(TransicaoNaoAutorizadaError):
                avaliar_transicao(
                    rota, estado, t.acao, setor=setor, administrador=True, motivo="x"
                )


# ---------------------------------------------------------------------------
# Aprovar / Reprovar nos estados de posse do vendedor
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("rota", "estado"),
    [
        (Rota.MATRIZ, E.RETIRADA_VENDEDOR),
        (Rota.LAM_MATRIZ, E.RETIRADA_VENDEDOR),
        (Rota.FILIAL, E.ENCAMINHADA_PARA_VENDEDOR),
        (Rota.LAM_FILIAL, E.ENCAMINHADA_PARA_VENDEDOR),
    ],
)
def test_aprovar_e_reprovar_nos_estados_de_posse(rota: Rota, estado: E) -> None:
    aprov = avaliar_transicao(
        rota, estado, APROVAR, setor=Setor.VENDEDOR, administrador=False, motivo=None
    )
    assert aprov.estado_destino == E.APROVADA_VENDEDOR
    reprov = avaliar_transicao(
        rota, estado, REPROVAR, setor=Setor.VENDEDOR, administrador=False, motivo="borrado"
    )
    assert reprov.estado_destino == E.REPROVADA_VENDEDOR
    # Reprovar SEM motivo → rejeitado (422).
    with pytest.raises(MotivoObrigatorioError):
        avaliar_transicao(
            rota, estado, REPROVAR, setor=Setor.VENDEDOR, administrador=False, motivo="   "
        )


# ---------------------------------------------------------------------------
# Transversais: Cancelar (qualquer ativo) e Reiniciar (de Reprovada) — flag admin
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("chave", list(_ORACULO.keys()))
def test_cancelar_exige_admin_e_motivo(chave: tuple[Rota, E]) -> None:
    rota, estado = chave
    # Admin (de qualquer setor) cancela com motivo.
    t = avaliar_transicao(
        rota, estado, CANCELAR, setor=Setor.VENDEDOR, administrador=True, motivo="cliente desistiu"
    )
    assert t.estado_destino == E.CANCELADA
    # Sem motivo → 422.
    with pytest.raises(MotivoObrigatorioError):
        avaliar_transicao(
            rota, estado, CANCELAR, setor=Setor.STUDIO, administrador=True, motivo=None
        )
    # Não-admin (mesmo setor studio) → 403.
    with pytest.raises(TransicaoNaoAutorizadaError):
        avaliar_transicao(
            rota, estado, CANCELAR, setor=Setor.STUDIO, administrador=False, motivo="x"
        )


@pytest.mark.parametrize("rota", list(Rota))
def test_reiniciar_ciclo_de_reprovada_exige_admin(rota: Rota) -> None:
    t = avaliar_transicao(
        rota, E.REPROVADA_VENDEDOR, REINICIAR,
        setor=Setor.VENDEDOR, administrador=True, motivo=None,
    )
    assert t.estado_destino == E.CRIADA  # volta a "Criada (novo ciclo)" — rota preservada
    with pytest.raises(TransicaoNaoAutorizadaError):
        avaliar_transicao(
            rota, E.REPROVADA_VENDEDOR, REINICIAR,
            setor=Setor.STUDIO, administrador=False, motivo=None,
        )


def test_reprovada_aceita_reiniciar_e_cancelar() -> None:
    transicoes = transicoes_de(Rota.MATRIZ, E.REPROVADA_VENDEDOR)
    acoes = {t.acao for t in transicoes}
    assert acoes == {REINICIAR, CANCELAR}


# ---------------------------------------------------------------------------
# autoriza() — unidade
# ---------------------------------------------------------------------------
def test_autoriza_normal_flow_por_setor() -> None:
    assert autoriza(Az.VENDEDOR, Setor.VENDEDOR, administrador=False)
    assert not autoriza(Az.VENDEDOR, Setor.STUDIO, administrador=True)


def test_autoriza_admin_por_flag_independe_do_setor() -> None:
    assert autoriza(Az.ADMIN, Setor.VENDEDOR, administrador=True)
    assert autoriza(Az.ADMIN, Setor.STUDIO, administrador=True)
    assert not autoriza(Az.ADMIN, Setor.STUDIO, administrador=False)


# ---------------------------------------------------------------------------
# Ações administrativas e assinatura (W3-C14/§6.6) — Cancelar/Reiniciar não
# capturam traço (assinatura_ref NULL — ADR-066). Derivado de TRANSITION_RULES.
# ---------------------------------------------------------------------------
def test_acoes_administrativas_sao_exatamente_as_gated_por_admin() -> None:
    # As administrativas são EXATAMENTE as ações cujas transições na §6 são TODAS
    # gated por Autorizacao.ADMIN — trava o drift entre o conjunto e a máquina.
    todas_admin: dict[Acao, bool] = {}
    for transicoes in TRANSITION_RULES.values():
        for t in transicoes:
            todas_admin[t.acao] = todas_admin.get(t.acao, True) and (
                t.perfil_autorizado is Az.ADMIN
            )
    so_admin = {acao for acao, e_admin in todas_admin.items() if e_admin}
    assert so_admin == ACOES_ADMINISTRATIVAS == {CANCELAR, REINICIAR}


def test_exige_assinatura_so_e_falso_para_administrativas() -> None:
    assert not exige_assinatura(CANCELAR)
    assert not exige_assinatura(REINICIAR)
    assert exige_assinatura(ID)
    assert exige_assinatura(APROVAR)
    assert exige_assinatura(REPROVAR)
    # Total: toda ação NÃO-administrativa exige assinatura (RN-003 vs. §6.6).
    for acao in Acao:
        assert exige_assinatura(acao) is (acao not in ACOES_ADMINISTRATIVAS)
