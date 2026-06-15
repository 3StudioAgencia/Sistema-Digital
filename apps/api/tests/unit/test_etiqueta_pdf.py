"""Etiqueta PDF (W2-C06 · RF-003/DP-1/DP-2) — tamanho físico, campos e QR.

O conteúdo textual é extraído dos content streams do PDF (zlib quando
comprimidos) — sem dependência de leitor de PDF. O payload do QR é capturado
interceptando o ``segno.make_qr`` do módulo (o QR é vetorial; decodificá-lo
exigiria um leitor de imagem, e o que importa é o CONTEÚDO codificado — DP-3).
"""

import datetime as dt
import re
import zlib

import pytest
import segno
from src.adapters.outbound.etiqueta import fpdf_etiqueta
from src.adapters.outbound.etiqueta.fpdf_etiqueta import EtiquetaTemplate, FpdfEtiquetaGenerator
from src.domain.provas import Prova, Rota
from src.domain.settings import ConfiguracaoEtiqueta

MM_PARA_PT = 72 / 25.4


def _prova(rota: Rota = Rota.MATRIZ) -> Prova:
    return Prova(
        id="00000000-0000-0000-0000-000000000001",
        codigo="PRV-2026-06-K3T9XB",
        nome="Etiq Cafe Caproni Classico",
        requerimento="155295",
        cliente="Cafe Caproni",
        vendedor_id="00000000-0000-0000-0000-000000000002",
        rota=rota,
        arte_key="provas/x/arte.png",
        arte_content_type="image/png",
        created_at=dt.datetime(2026, 6, 12, tzinfo=dt.UTC),
    )


def _texto_do_pdf(pdf: bytes) -> str:
    """Concatena os content streams (descomprimindo os zlib) em latin-1."""
    partes: list[bytes] = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.DOTALL):
        bloco = m.group(1)
        try:
            bloco = zlib.decompress(bloco)
        except zlib.error:
            pass
        partes.append(bloco)
    return b"\n".join(partes).decode("latin-1", errors="ignore")


@pytest.fixture(scope="module")
def pdf() -> bytes:
    return FpdfEtiquetaGenerator().gerar_pdf(_prova(), "Renan Petrim")


def test_tamanho_fisico_exato_95x55_mm(pdf: bytes) -> None:
    """DP-2: o PDF sai EXATAMENTE em 95 x 55 mm (landscape)."""
    m = re.search(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", pdf)
    assert m is not None
    largura_pt, altura_pt = float(m.group(1)), float(m.group(2))
    assert largura_pt == pytest.approx(95 * MM_PARA_PT, abs=0.05)
    assert altura_pt == pytest.approx(55 * MM_PARA_PT, abs=0.05)


def test_etiqueta_contem_todos_os_campos_do_rf003(pdf: bytes) -> None:
    """RF-003 reconciliado (DP-1): nome, requerimento, vendedor, ROTA e o
    código em texto legível — além do cliente (design) e do ano dinâmico."""
    texto = _texto_do_pdf(pdf)
    assert "Nome:" in texto and "ETIQ CAFE CAPRONI CLASSICO" in texto
    assert "Requerimento:" in texto and "155295" in texto
    assert "Cliente:" in texto and "CAFE CAPRONI" in texto
    assert "Vendedor:" in texto and "RENAN PETRIM" in texto
    assert "Rota:" in texto and "MATRIZ" in texto  # DP-1: rota na etiqueta
    assert "PRV-2026-06-K3T9XB" in texto  # DP-1: código em destaque
    assert "Etiqueta de rastreio" in texto
    assert "2026" in texto  # ano derivado de created_at


@pytest.mark.parametrize(
    ("rota", "rotulo"),
    [
        (Rota.LAM_MATRIZ, "LAM. MATRIZ"),
        (Rota.FILIAL, "FILIAL"),
        (Rota.LAM_FILIAL, "LAM. FILIAL"),
    ],
)
def test_rotulo_da_rota_por_opcao(rota: Rota, rotulo: str) -> None:
    texto = _texto_do_pdf(FpdfEtiquetaGenerator().gerar_pdf(_prova(rota), "V"))
    assert rotulo in texto


def test_qr_codifica_exatamente_o_codigo(monkeypatch: pytest.MonkeyPatch) -> None:
    """DP-3/DAT §8.3: o payload do QR é o PRÓPRIO código — sem URL/indireção."""
    capturados: list[str] = []
    original = segno.make_qr

    def espiao(conteudo: str, **kwargs: object) -> object:
        capturados.append(conteudo)
        return original(conteudo, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(fpdf_etiqueta.segno, "make_qr", espiao)
    FpdfEtiquetaGenerator().gerar_pdf(_prova(), "V")
    assert capturados == ["PRV-2026-06-K3T9XB"]


def test_template_parametrizavel_muda_o_tamanho_fisico() -> None:
    """RN-011: o template padrão é parametrizável (o C09 traz a configuração)."""
    generator = FpdfEtiquetaGenerator(EtiquetaTemplate(largura=100.0, altura=60.0))
    pdf = generator.gerar_pdf(_prova(), "V")
    m = re.search(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", pdf)
    assert m is not None
    assert float(m.group(1)) == pytest.approx(100 * MM_PARA_PT, abs=0.05)
    assert float(m.group(2)) == pytest.approx(60 * MM_PARA_PT, abs=0.05)


def _media_box(pdf: bytes) -> tuple[float, float]:
    m = re.search(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", pdf)
    assert m is not None
    return float(m.group(1)), float(m.group(2))


def test_config_default_espelha_o_template_padrao_do_c06() -> None:
    """W2-C09/DP-5: os defaults do domínio não podem driftar do EtiquetaTemplate."""
    c = ConfiguracaoEtiqueta()
    t = EtiquetaTemplate()
    assert (c.largura, c.altura, c.margem, c.fonte, c.qr_zona_quieta_modulos) == (
        t.largura,
        t.altura,
        t.margem,
        t.fonte,
        t.qr_zona_quieta_modulos,
    )


def test_config_personalizado_sobrescreve_o_template() -> None:
    """W2-C09 (RN-011): config 'personalizado' muda a etiqueta gerada (C06)."""
    config = ConfiguracaoEtiqueta(modo="personalizado", largura=100.0, altura=60.0)
    largura, altura = _media_box(FpdfEtiquetaGenerator().gerar_pdf(_prova(), "V", config))
    assert largura == pytest.approx(100 * MM_PARA_PT, abs=0.05)
    assert altura == pytest.approx(60 * MM_PARA_PT, abs=0.05)


def test_config_padrao_ignora_sobrescritas() -> None:
    """'padrao' usa o template padrão mesmo com campos sobrescritos no objeto."""
    config = ConfiguracaoEtiqueta(modo="padrao", largura=100.0, altura=60.0)
    largura, altura = _media_box(FpdfEtiquetaGenerator().gerar_pdf(_prova(), "V", config))
    assert largura == pytest.approx(95 * MM_PARA_PT, abs=0.05)
    assert altura == pytest.approx(55 * MM_PARA_PT, abs=0.05)


def test_config_personalizado_aplica_zona_quieta_do_qr() -> None:
    """W2-C09/DP-5: a sobrescrita de qr_zona_quieta_modulos DEVE valer (o QR muda).

    Sem o tamanho físico mudar (mesma largura/altura), o único efeito é a zona
    quieta — então os bytes do PDF precisam diferir do padrão (módulo=2)."""
    padrao = FpdfEtiquetaGenerator().gerar_pdf(
        _prova(), "V", ConfiguracaoEtiqueta(modo="personalizado", qr_zona_quieta_modulos=2)
    )
    custom = FpdfEtiquetaGenerator().gerar_pdf(
        _prova(), "V", ConfiguracaoEtiqueta(modo="personalizado", qr_zona_quieta_modulos=8)
    )
    assert padrao != custom


def test_pdf_e_deterministico_para_a_mesma_prova() -> None:
    """Geração sob demanda (DP-7): reimprimir gera a MESMA etiqueta (sem estado)."""
    a = FpdfEtiquetaGenerator().gerar_pdf(_prova(), "V")
    b = FpdfEtiquetaGenerator().gerar_pdf(_prova(), "V")
    assert a == b


def test_texto_fora_do_latin1_nunca_derruba_a_geracao() -> None:
    """Revisão adversarial W2-C06 (achado alto): nome/cliente são texto livre —
    travessão, aspas curvas (Word/celular) e acentos saem no PDF (cp1252);
    emoji degrada para '?' em vez de 500 permanente no download da etiqueta."""
    prova = _prova()
    prova.nome = "Etiqueta — 'Premium' café"  # travessão + aspas curvas + acento
    prova.cliente = "Çã€™ Ltda"
    pdf = FpdfEtiquetaGenerator().gerar_pdf(prova, "José D'Ávila 😀")
    texto = _texto_do_pdf(pdf)
    assert "PREMIUM" in texto and "CAFÉ" in texto.upper()
    assert "JOSÉ" in texto.upper()
    assert "?" in texto  # o emoji degradou, não derrubou


def test_fallback_de_vendedor_ausente_e_ascii() -> None:
    """O fallback usado pelo serviço ('-') precisa ser renderizável SEMPRE."""
    pdf = FpdfEtiquetaGenerator().gerar_pdf(_prova(), "-")
    assert pdf.startswith(b"%PDF")
