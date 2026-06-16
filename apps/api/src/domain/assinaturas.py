"""Domínio da assinatura digital (W3-C12) — o comprovante de cada movimentação.

RN-003: cada transição da máquina de estados (C11) é comprovada por uma assinatura
DESENHADA (``react-signature-canvas`` → PNG). A imagem é pequena (poucos KB) e nasce
na MESMA transação atômica que a movimentação (RNF-017/DP-1): assinatura e
movimentação **nascem/falham juntas**. Armazenada como ``bytea`` na tabela
``assinaturas`` (DP-2): nada externo a sincronizar — o R2 NÃO participa da transação
do Postgres, o que abriria a porta a uma assinatura órfã num rollback.

Camada interna (CLAUDE.md §5.2): apenas stdlib + o detector de imagem compartilhado
do domínio de provas (fonte única dos magic bytes — sem drift).
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.provas import detectar_tipo_imagem
from src.domain.usuarios import ErroDeDominio

# Teto da imagem da assinatura: um traço de canvas em PNG raramente passa de
# dezenas de KB; 1 MB é folga ampla e defende contra abuso (o teto do corpo
# inteiro da requisição é do ``BodyLimitMiddleware``, pré-auth).
ASSINATURA_TAMANHO_MAXIMO = 1 * 1024 * 1024  # 1 MB
ASSINATURA_TIPOS_PERMITIDOS: frozenset[str] = frozenset({"image/png", "image/jpeg"})


class AssinaturaInvalidaError(ErroDeDominio):
    """Imagem da assinatura fora do contrato (vazia, grande demais ou não-imagem).
    Mapeada a 422 (default do domínio — W3-C12/RN-003)."""

    codigo = "assinatura_invalida"


def validar_assinatura(data: bytes) -> str:
    """Valida a imagem da assinatura (RN-003) e devolve o content-type EFETIVO.

    Como na arte (C06), o tipo vem dos MAGIC BYTES, nunca de um header declarado:
    o que se persiste é o tipo REAL do conteúdo. PNG é o formato natural do
    ``react-signature-canvas``; JPEG é aceito por robustez (mesmo conjunto da arte).
    """
    if len(data) == 0:
        raise AssinaturaInvalidaError("Assinatura obrigatória: desenhe a assinatura.")
    if len(data) > ASSINATURA_TAMANHO_MAXIMO:
        raise AssinaturaInvalidaError("Assinatura excede o tamanho máximo permitido.")
    tipo = detectar_tipo_imagem(data)
    if tipo is None:
        raise AssinaturaInvalidaError("Assinatura inválida: imagem não reconhecida.")
    return tipo


@dataclass
class Assinatura:
    """Uma assinatura digital — comprovante imutável de uma movimentação (RN-003).

    Carrega ``prova_id`` e ``ator_id`` PRÓPRIOS (denormalizados) para a RLS se
    escopar SEM depender da movimentação, que é inserida DEPOIS (a FK
    ``movimentacoes.assinatura_ref`` aponta para cá — DP-1). ``imagem`` é o PNG do
    canvas em bytes; ``content_type`` alimenta o futuro proxy de leitura (C13).
    """

    id: str
    prova_id: str
    ator_id: str
    imagem: bytes = field(repr=False)
    content_type: str
    created_at: datetime | None = field(default=None, compare=False)


__all__ = [
    "ASSINATURA_TAMANHO_MAXIMO",
    "ASSINATURA_TIPOS_PERMITIDOS",
    "Assinatura",
    "AssinaturaInvalidaError",
    "validar_assinatura",
]
