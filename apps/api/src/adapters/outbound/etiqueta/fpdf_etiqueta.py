"""Gerador da etiqueta PDF — fpdf2 + segno (W2-C06 · RF-003/RN-011 · DP-1/DP-2/DP-7).

Template PADRÃO do sistema, parametrizável via ``EtiquetaTemplate`` (a tela de
configuração é do C09 — RN-011). Saída no tamanho físico EXATO 95 x 55 mm
(landscape), fiel ao design do Figma com a reconciliação da DP-1: o **código
alfanumérico em fonte grande abaixo do QR** (Backlog C06) e a **rota** como
quinta linha do bloco de campos.

Tudo vetorial (nítido em qualquer impressora, sem dependência raster):
- QR desenhado módulo a módulo a partir da matriz do segno — o payload é o
  PRÓPRIO código (DP-3/DAT §8.3, sem indireção);
- logos em SVG pré-processado (``assets/``), embutidas pelo parser do fpdf2;
- fontes core (Helvetica) — sem embedding, PDF mínimo.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import segno
from fpdf import FPDF

from src.application.ports.etiqueta import EtiquetaPort
from src.domain.provas import Prova, Rota
from src.domain.settings import ConfiguracaoEtiqueta

_ASSETS = Path(__file__).parent / "assets"


def _imprimivel(texto: str) -> str:
    """Reduz ``texto`` ao repertório cp1252 das fontes core do PDF.

    Caracteres fora (emoji, símbolos raros) viram ``?`` — uma etiqueta sempre
    sai, nunca um 500 (degradação graciosa; revisão adversarial W2-C06).
    """
    return texto.encode("cp1252", errors="replace").decode("cp1252")


# Rótulos de impressão das rotas (apresentação — o frontend tem o próprio mapa).
ROTULO_ROTA: dict[Rota, str] = {
    Rota.MATRIZ: "Matriz",
    Rota.LAM_MATRIZ: "Lam. Matriz",
    Rota.FILIAL: "Filial",
    Rota.LAM_FILIAL: "Lam. Filial",
}


@dataclass(frozen=True)
class EtiquetaTemplate:
    """Parâmetros do template padrão (RN-011 — o C09 os torna configuráveis).

    Medidas em mm; tamanho físico exato confirmado na DP-2:
    9,5 cm (largura) x 5,5 cm (altura), landscape.
    """

    largura: float = 95.0
    altura: float = 55.0
    margem: float = 3.0
    fonte: str = "helvetica"
    # Módulos de zona quieta do QR DENTRO da área reservada (somam-se ao
    # respiro branco da moldura; ≥ 4 módulos efetivos no total).
    qr_zona_quieta_modulos: int = 2


class FpdfEtiquetaGenerator(EtiquetaPort):
    """Renderiza a etiqueta no layout do design + DP-1 (ver docs/provas.md)."""

    def __init__(self, template: EtiquetaTemplate | None = None) -> None:
        self._t = template or EtiquetaTemplate()

    def _template_efetivo(self, config: ConfiguracaoEtiqueta | None) -> EtiquetaTemplate:
        """Resolve o template da geração (W2-C09 — RN-011/DP-5).

        ``config`` ``personalizado`` sobrescreve os 5 parâmetros do template;
        ``None``/``padrao`` mantém o template padrão injetado (``self._t``)."""
        if config is None or not config.personalizado:
            return self._t
        return EtiquetaTemplate(
            largura=config.largura,
            altura=config.altura,
            margem=config.margem,
            fonte=config.fonte,
            qr_zona_quieta_modulos=config.qr_zona_quieta_modulos,
        )

    # ------------------------------------------------------------------ público
    def gerar_pdf(
        self, prova: Prova, vendedor_nome: str, config: ConfiguracaoEtiqueta | None = None
    ) -> bytes:
        t = self._template_efetivo(config)
        pdf = FPDF(unit="mm", format=(t.largura, t.altura))
        # Fontes core com cp1252 (cobre acentos PT-BR, travessão, aspas curvas,
        # €): o default latin-1 do fpdf2 LEVANTA para esses caracteres — e nome/
        # cliente são texto livre (revisão adversarial W2-C06, achado alto).
        pdf.core_fonts_encoding = "windows-1252"
        pdf.set_auto_page_break(False)
        pdf.set_margins(0, 0, 0)
        pdf.set_title(f"Etiqueta {prova.codigo}")
        pdf.set_creator("Sistema de Rastreio de Provas Digitais - 3Studio")
        # Data de criação do DOCUMENTO fixada na da prova: reimprimir a mesma
        # etiqueta gera bytes idênticos (geração sob demanda, sem estado — DP-7).
        pdf.creation_date = prova.created_at or datetime.now(UTC)
        pdf.add_page()
        pdf.set_text_color(0)
        pdf.set_draw_color(0)
        pdf.set_fill_color(0)

        x0, x1 = t.margem, t.largura - t.margem
        # Geometria do QR definida aqui (reusada pelo caption acima dele, para
        # "Aponte a câmera..." ficar CENTRADO sobre o QR — mesmo x-range).
        qr_box_x, qr_box_y, qr_box_l, qr_box_a = 60.0, 14.5, 31.0, 28.0

        # Réguas horizontais (topo/rodapé do design) — linha FINA (~2px ≈ 0,5mm)
        pdf.rect(x0, 3.0, x1 - x0, 0.5, style="F")
        pdf.rect(x0, 51.8, x1 - x0, 0.5, style="F")

        # Cabeçalho: wordmark 3STUDIO + logo studio&ART! (fixas — DP-2)
        pdf.image(str(_ASSETS / "logo_3studio.svg"), x=4.0, y=6.8, h=4.6)
        pdf.image(str(_ASSETS / "logo_studio_art.svg"), x=28.6, y=5.0, h=8.2)

        # "Aponte a câmera para o QR CODE" — centrado SOBRE o QR (mesmo x-range)
        pdf.set_xy(qr_box_x, 5.8)
        pdf.set_font(t.fonte, "", 8.5)
        pdf.multi_cell(
            qr_box_l, 3.6, "Aponte a câmera\npara o **QR CODE**", markdown=True, align="C"
        )

        # Barra divisória (parcial, como no design)
        pdf.rect(x0, 14.4, 49.5, 2.0, style="F")

        # Bloco de campos (esquerda) — Nome/Requerimento/Cliente/Vendedor + Rota
        # (DP-1). Valores reduzidos ao repertório cp1252 das fontes core: o que
        # sobrar (emoji etc.) vira "?" em vez de derrubar a renderização.
        campos = [
            ("Nome:", _imprimivel(prova.nome)),
            ("Requerimento:", _imprimivel(prova.requerimento)),
            ("Cliente:", _imprimivel(prova.cliente)),
            ("Vendedor:", _imprimivel(vendedor_nome)),
            ("Rota:", ROTULO_ROTA[prova.rota]),
        ]
        y = 19.6
        for rotulo, valor in campos:
            pdf.set_xy(4.5, y)
            pdf.set_font(t.fonte, "B", 10.5)
            largura_rotulo = pdf.get_string_width(rotulo) + 1.8
            pdf.cell(largura_rotulo, 4.2, rotulo)
            restante = 56.0 - pdf.get_x()
            # Valor: encolhe a fonte (até 6.5pt) antes de truncar — nomes longos
            # cabem inteiros, como no design.
            pdf.set_font(t.fonte, "", 8.0)
            valor_texto = valor.upper()
            while pdf.font_size_pt > 6.5 and pdf.get_string_width(valor_texto) > restante:
                pdf.set_font_size(pdf.font_size_pt - 0.25)
            pdf.cell(restante, 4.2, self._ajustar(pdf, valor_texto, restante))
            y += 5.4

        # QR Code (direita) em moldura arredondada — contorno FINO (~2px ≈ 0,5mm)
        pdf.set_line_width(0.5)
        pdf.rect(qr_box_x, qr_box_y, qr_box_l, qr_box_a, round_corners=True, corner_radius=3.5)
        pdf.set_line_width(0.2)
        lado_qr = qr_box_a - 5.2
        self._desenhar_qr(
            pdf,
            conteudo=prova.codigo,
            x=qr_box_x + (qr_box_l - lado_qr) / 2,
            y=qr_box_y + 2.6,
            lado=lado_qr,
            quieta=t.qr_zona_quieta_modulos,
        )

        # Código alfanumérico em DESTAQUE, fonte grande abaixo do QR (DP-1/RF-003)
        pdf.set_font(t.fonte, "B", 12.0)
        codigo_largura_max = 34.5  # centrado no QR sem invadir a margem direita
        while pdf.font_size_pt > 8.0 and pdf.get_string_width(prova.codigo) > codigo_largura_max:
            pdf.set_font_size(pdf.font_size_pt - 0.5)
        pdf.set_xy(qr_box_x + qr_box_l / 2 - codigo_largura_max / 2, 43.6)
        pdf.cell(codigo_largura_max, 4.6, prova.codigo, align="C")

        # Rodapé: ano de criação (dinâmico) + "Etiqueta de rastreio"
        ano = str((prova.created_at or datetime.now(UTC)).year)
        pdf.set_font(t.fonte, "", 9.5)
        pdf.set_xy(5.2, 47.9)
        pdf.cell(pdf.get_string_width(ano) + 0.5, 4.0, ano)

        rotulo_rodape = "Etiqueta de rastreio"
        largura_rodape = pdf.get_string_width(rotulo_rodape) + 4.0
        pdf.set_xy(x1 - largura_rodape + 2.0, 47.9)
        pdf.cell(largura_rodape - 4.0, 4.0, rotulo_rodape)

        return bytes(pdf.output())

    # ----------------------------------------------------------------- privados
    @staticmethod
    def _ajustar(pdf: FPDF, texto: str, largura: float) -> str:
        if pdf.get_string_width(texto) <= largura:
            return texto
        while texto and pdf.get_string_width(texto + "...") > largura:
            texto = texto[:-1]
        return texto + "..."

    def _desenhar_qr(
        self, pdf: FPDF, conteudo: str, x: float, y: float, lado: float, quieta: int
    ) -> None:
        """QR vetorial: um retângulo preenchido por módulo escuro da matriz.

        ``quieta`` (zona quieta em módulos) vem do template EFETIVO da geração
        (W2-C09/DP-5): assim a sobrescrita ``personalizado`` deste campo vale,
        em vez de ler o default da instância. O leve overlap (+0,02 mm) evita
        fendas brancas entre módulos adjacentes em rasterizadores de visualização;
        irrelevante na impressão.
        """
        qr = segno.make_qr(conteudo, error="m")
        matriz = [bytes(linha) for linha in qr.matrix]
        n = len(matriz)
        modulo = lado / (n + 2 * quieta)
        origem_x = x + quieta * modulo
        origem_y = y + quieta * modulo
        for i, linha in enumerate(matriz):
            for j, escuro in enumerate(linha):
                if escuro:
                    pdf.rect(
                        origem_x + j * modulo,
                        origem_y + i * modulo,
                        modulo + 0.02,
                        modulo + 0.02,
                        style="F",
                    )


__all__ = ["ROTULO_ROTA", "EtiquetaTemplate", "FpdfEtiquetaGenerator"]
