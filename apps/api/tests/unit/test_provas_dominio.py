"""Domínio de provas (W2-C06) — código, charset, arte (magic bytes), vendedor."""

import datetime as dt

import pytest
from src.domain.provas import (
    ARTE_TAMANHO_MAXIMO,
    CODIGO_ALFABETO,
    ESTADOS_EM_TRANSITO,
    ArteInvalidaError,
    EstadoProva,
    Rota,
    VendedorInvalidoError,
    detectar_tipo_imagem,
    gerar_codigo,
    validar_arte,
    validar_codigo,
    validar_vendedor,
)
from src.domain.usuarios import Localizacao, Setor, Usuario

JPEG_MINIMO = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PNG_MINIMO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
QUANDO = dt.datetime(2026, 6, 12, tzinfo=dt.UTC)


# ---------------------------------------------------------------------------
# Glossário canônico (CLAUDE.md §6) — sincronizado com a migration 0007
# ---------------------------------------------------------------------------
def test_rota_tem_as_quatro_opcoes_canonicas() -> None:
    assert {r.value for r in Rota} == {"matriz", "lam_matriz", "filial", "lam_filial"}


def test_estado_prova_tem_os_14_estados_canonicos() -> None:
    assert len(EstadoProva) == 14
    assert {e.value for e in EstadoProva} == {
        "criada",
        "encaminhada_para_laminacao",
        "com_motorista_ida_laminacao",
        "laminacao_concluida",
        "com_motorista_volta_laminacao",
        "de_volta_studio_pos_laminacao",
        "retirada_vendedor",
        "encaminhada_para_vendedor",
        "aprovada_vendedor",
        "reprovada_vendedor",
        "de_volta_studio",
        "com_motorista_entrega_final",
        "recebida_clicheria",
        "cancelada",
    }


def test_em_transito_sao_os_tres_contextos_com_motorista() -> None:
    assert ESTADOS_EM_TRANSITO == {
        EstadoProva.COM_MOTORISTA_IDA_LAMINACAO,
        EstadoProva.COM_MOTORISTA_VOLTA_LAMINACAO,
        EstadoProva.COM_MOTORISTA_ENTREGA_FINAL,
    }


# ---------------------------------------------------------------------------
# Código identificador (DP-3 / DAT §8.3)
# ---------------------------------------------------------------------------
def test_alfabeto_nao_tem_caracteres_ambiguos() -> None:
    assert len(CODIGO_ALFABETO) == 31
    assert set("0O1IL").isdisjoint(set(CODIGO_ALFABETO))


def test_gerar_codigo_formato_e_charset() -> None:
    for _ in range(200):
        codigo = gerar_codigo(QUANDO)
        assert validar_codigo(codigo), codigo
        assert codigo.startswith("PRV-2026-06-")
        assert len(codigo) == 18
        assert all(c in CODIGO_ALFABETO for c in codigo[-6:])


def test_gerar_codigo_usa_o_instante_informado() -> None:
    assert gerar_codigo(dt.datetime(2027, 1, 3, tzinfo=dt.UTC)).startswith("PRV-2027-01-")


@pytest.mark.parametrize(
    "codigo",
    [
        "PRV-2026-06-K3T9XB",  # exemplo canônico do Backlog C06
        "PRV-2026-04-9PQYW2",  # exemplo canônico do DAT §8.3
    ],
)
def test_validar_codigo_aceita_exemplos_canonicos(codigo: str) -> None:
    assert validar_codigo(codigo)


@pytest.mark.parametrize(
    "codigo",
    [
        "PRV-2026-06-K3T9X0",  # 0 é ambíguo
        "PRV-2026-06-K3T9XO",  # O é ambíguo
        "PRV-2026-06-K3T9X1",  # 1 é ambíguo
        "PRV-2026-06-K3T9XI",  # I é ambíguo
        "PRV-2026-06-K3T9XL",  # L é ambíguo
        "PRV-2026-13-K3T9XB",  # mês inválido
        "PRV-2026-00-K3T9XB",  # mês inválido
        "PRV-2026-06-K3T9X",  # sufixo curto
        "PRV-2026-06-K3T9XBZ",  # sufixo longo
        "prv-2026-06-k3t9xb",  # minúsculas não fazem parte do charset
        "ABC-2026-06-K3T9XB",  # prefixo errado
        "",
    ],
)
def test_validar_codigo_rejeita_fora_do_formato(codigo: str) -> None:
    assert not validar_codigo(codigo)


# ---------------------------------------------------------------------------
# Arte (RF-001)
# ---------------------------------------------------------------------------
def test_detectar_tipo_imagem() -> None:
    assert detectar_tipo_imagem(JPEG_MINIMO) == "image/jpeg"
    assert detectar_tipo_imagem(PNG_MINIMO) == "image/png"
    assert detectar_tipo_imagem(b"GIF89a....") is None
    assert detectar_tipo_imagem(b"") is None


def test_validar_arte_aceita_jpeg_e_png() -> None:
    assert validar_arte(JPEG_MINIMO, "image/jpeg") == "image/jpeg"
    assert validar_arte(PNG_MINIMO, "image/png") == "image/png"
    # header declarado ausente: vale o conteúdo
    assert validar_arte(JPEG_MINIMO, None) == "image/jpeg"


def test_validar_arte_rejeita_vazia_grande_e_tipo_errado() -> None:
    with pytest.raises(ArteInvalidaError, match="obrigatória"):
        validar_arte(b"", "image/png")
    with pytest.raises(ArteInvalidaError, match="10 MB"):
        validar_arte(JPEG_MINIMO + b"\x00" * ARTE_TAMANHO_MAXIMO, "image/jpeg")
    with pytest.raises(ArteInvalidaError, match="JPG ou PNG"):
        validar_arte(b"GIF89a" + b"\x00" * 16, "image/gif")


def test_validar_arte_rejeita_header_que_mente_sobre_o_conteudo() -> None:
    # extensão/header declarado NUNCA é suficiente (CLAUDE.md/W2-C06 §3.3)
    with pytest.raises(ArteInvalidaError, match="não corresponde"):
        validar_arte(PNG_MINIMO, "image/jpeg")


# ---------------------------------------------------------------------------
# Vendedor responsável (RF-001)
# ---------------------------------------------------------------------------
def _usuario(setor: Setor, ativo: bool = True) -> Usuario:
    return Usuario(
        id="u1",
        nome="V",
        email="v@x.z",
        setor=setor,
        localizacao=Localizacao.MATRIZ if setor is Setor.VENDEDOR else None,
        ativo=ativo,
    )


def test_validar_vendedor_aceita_vendedor_ativo() -> None:
    validar_vendedor(_usuario(Setor.VENDEDOR))


@pytest.mark.parametrize(
    "vendedor",
    [
        None,  # inexistente
        _usuario(Setor.STUDIO),  # setor errado
        _usuario(Setor.MOTORISTA),
        _usuario(Setor.VENDEDOR, ativo=False),  # inativo
    ],
)
def test_validar_vendedor_rejeita_invalidos(vendedor: Usuario | None) -> None:
    with pytest.raises(VendedorInvalidoError):
        validar_vendedor(vendedor)
