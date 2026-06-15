"""Domínio de provas digitais — entidade, enums e regras de negócio puras (W2-C06).

Camada interna da arquitetura hexagonal (CLAUDE.md §5.2): apenas stdlib.
Glossário canônico (CLAUDE.md §6): membro Python em MAIÚSCULA, valor em
lowercase/snake_case — sincronizado 1:1 com os tipos PostgreSQL ``rota_enum`` e
``status_prova_enum`` (migration 0007).

Regras desta wave:
- RN-007: rota escolhida manualmente entre as quatro opções, livre da
  localização do vendedor, IMUTÁVEL após a criação (trigger no banco + nenhum
  caminho de update aqui).
- RF-001: campos obrigatórios; arte JPG/PNG ≤ 10 MB (magic bytes, nunca só a
  extensão/header declarado).
- RF-002/DAT §8.3: código ``PRV-AAAA-MM-NNNNNN`` — sufixo de 6 caracteres em
  charset NÃO ambíguo (sem ``0/O``, ``1/I/L``), gerado com aleatoriedade
  criptográfica (anti-enumeração — DAT §8.2). O código é o MESMO conteúdo do
  QR (DP-3); ``validar_codigo`` é o que a máscara do C10 reutiliza.

As TRANSIÇÕES de estado não moram aqui: são da máquina de estados do C11
(``domain/state_machine/`` — CLAUDE.md §5.3). A prova nasce ``CRIADA`` (§6).
"""

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from src.domain.usuarios import ErroDeDominio, Setor, Usuario


class Rota(StrEnum):
    """Rotas de encaminhamento (RN-007) — sincronizadas com ``rota_enum``."""

    MATRIZ = "matriz"
    LAM_MATRIZ = "lam_matriz"
    FILIAL = "filial"
    LAM_FILIAL = "lam_filial"


class EstadoProva(StrEnum):
    """Os 14 estados da Requisitos v1.0 §6 — sincronizados com ``status_prova_enum``."""

    CRIADA = "criada"
    ENCAMINHADA_PARA_LAMINACAO = "encaminhada_para_laminacao"
    COM_MOTORISTA_IDA_LAMINACAO = "com_motorista_ida_laminacao"
    LAMINACAO_CONCLUIDA = "laminacao_concluida"
    COM_MOTORISTA_VOLTA_LAMINACAO = "com_motorista_volta_laminacao"
    DE_VOLTA_STUDIO_POS_LAMINACAO = "de_volta_studio_pos_laminacao"
    RETIRADA_VENDEDOR = "retirada_vendedor"
    ENCAMINHADA_PARA_VENDEDOR = "encaminhada_para_vendedor"
    APROVADA_VENDEDOR = "aprovada_vendedor"
    REPROVADA_VENDEDOR = "reprovada_vendedor"
    DE_VOLTA_STUDIO = "de_volta_studio"
    COM_MOTORISTA_ENTREGA_FINAL = "com_motorista_entrega_final"
    RECEBIDA_CLICHERIA = "recebida_clicheria"
    CANCELADA = "cancelada"


# "Em Trânsito" da Matriz §7: os TRÊS contextos "Com Motorista" da v1.0 — o
# escopo de dado do Motorista (RLS ``provas_select_motorista.sql`` espelha).
ESTADOS_EM_TRANSITO: frozenset[EstadoProva] = frozenset(
    {
        EstadoProva.COM_MOTORISTA_IDA_LAMINACAO,
        EstadoProva.COM_MOTORISTA_VOLTA_LAMINACAO,
        EstadoProva.COM_MOTORISTA_ENTREGA_FINAL,
    }
)


# ---------------------------------------------------------------------------
# Código identificador (RF-002 / DAT §8.3 / DP-3)
# ---------------------------------------------------------------------------
CODIGO_PREFIXO = "PRV"
CODIGO_SUFIXO_TAMANHO = 6
# Charset não ambíguo para digitação manual (DAT §8.3): A-Z 0-9 SEM 0/O, 1/I/L
# → 31 símbolos; 31^6 ≈ 887 milhões de combinações por mês (≥ entropia mínima
# do DAT §8.2).
CODIGO_ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"

# Derivado do alfabeto (fonte única — sem drift): o C10 valida a digitação
# manual com este MESMO padrão.
CODIGO_REGEX = re.compile(rf"^{CODIGO_PREFIXO}-\d{{4}}-(0[1-9]|1[0-2])-[{CODIGO_ALFABETO}]{{6}}$")


def gerar_codigo(quando: datetime) -> str:
    """Gera um código ``PRV-AAAA-MM-NNNNNN`` para o instante ``quando``.

    Sufixo com ``secrets`` (aleatoriedade criptográfica): códigos não são
    sequenciais nem previsíveis (anti-enumeração — DAT §8.2). A UNICIDADE é
    garantida pela constraint ``uq_provas_codigo`` + retry de colisão no
    serviço (DP-3) — não aqui.
    """
    sufixo = "".join(secrets.choice(CODIGO_ALFABETO) for _ in range(CODIGO_SUFIXO_TAMANHO))
    return f"{CODIGO_PREFIXO}-{quando.year:04d}-{quando.month:02d}-{sufixo}"


def validar_codigo(codigo: str) -> bool:
    """``True`` se ``codigo`` tem o formato/charset canônico (máscara do C10)."""
    return CODIGO_REGEX.fullmatch(codigo) is not None


# ---------------------------------------------------------------------------
# Arte (RF-001): JPG/PNG, máx 10 MB — validada por CONTEÚDO, não por extensão
# ---------------------------------------------------------------------------
ARTE_TAMANHO_MAXIMO = 10 * 1024 * 1024  # 10 MB (RF-001)
ARTE_TIPOS_PERMITIDOS: frozenset[str] = frozenset({"image/jpeg", "image/png"})
EXTENSAO_POR_TIPO = {"image/jpeg": ".jpg", "image/png": ".png"}

_MAGIC_JPEG = b"\xff\xd8\xff"
_MAGIC_PNG = b"\x89PNG\r\n\x1a\n"


class ArteInvalidaError(ErroDeDominio):
    """Arte fora do contrato RF-001 (tipo ou tamanho). Mapeada a 422."""

    codigo = "arte_invalida"


class VendedorInvalidoError(ErroDeDominio):
    """O vendedor responsável deve ser um usuário ATIVO do setor Vendedor."""

    codigo = "vendedor_invalido"

    def __init__(self) -> None:
        super().__init__("Vendedor responsável inválido: selecione um vendedor ativo.")


class CriacaoDivergenteError(ErroDeDominio):
    """A mesma chave de idempotência (``prova_id``) chegou com DADOS diferentes
    dos já registrados — reenvio legítimo converge; payload divergente é erro
    do cliente (409), nunca sobrescrita silenciosa (RNF-015)."""

    codigo = "criacao_divergente"

    def __init__(self) -> None:
        super().__init__(
            "Esta criação já foi registrada com dados diferentes. "
            "Verifique a listagem de provas antes de reenviar."
        )


class ProvaNaoEncontradaError(ErroDeDominio):
    """Prova inexistente OU fora do escopo do ator (mensagem ÚNICA — a RLS não
    distingue os dois casos e a borda também não deve: anti-enumeração,
    CLAUDE.md §11). Mapeada a 404."""

    codigo = "prova_nao_encontrada"

    def __init__(self) -> None:
        super().__init__("Prova não encontrada.")


def detectar_tipo_imagem(data: bytes) -> str | None:
    """Tipo REAL do conteúdo pelos magic bytes (JPEG/PNG) — ``None`` se outro."""
    if data.startswith(_MAGIC_JPEG):
        return "image/jpeg"
    if data.startswith(_MAGIC_PNG):
        return "image/png"
    return None


def validar_arte(data: bytes, content_type_declarado: str | None) -> str:
    """Valida a arte (RF-001) e devolve o content-type EFETIVO (dos magic bytes).

    Nunca confia só no header declarado: o tipo persistido/enviado ao R2 é o
    detectado do conteúdo; o declarado, quando presente, precisa concordar.
    """
    if len(data) == 0:
        raise ArteInvalidaError("Arte obrigatória: anexe um arquivo JPG ou PNG (RF-001).")
    if len(data) > ARTE_TAMANHO_MAXIMO:
        raise ArteInvalidaError("Arte excede o tamanho máximo de 10 MB (RF-001).")
    tipo = detectar_tipo_imagem(data)
    if tipo is None:
        raise ArteInvalidaError("Arte inválida: apenas arquivos JPG ou PNG (RF-001).")
    if content_type_declarado is not None and content_type_declarado.lower() != tipo:
        raise ArteInvalidaError("Arte inválida: o tipo declarado não corresponde ao conteúdo.")
    return tipo


def validar_vendedor(vendedor: Usuario | None) -> None:
    """RF-001: o vendedor responsável é um usuário ATIVO do setor Vendedor.

    A FK garante apenas a existência; o SETOR e o status são regra de negócio
    (validados aqui, na criação — a fonte única que o serviço invoca).
    """
    if vendedor is None or vendedor.setor is not Setor.VENDEDOR or not vendedor.ativo:
        raise VendedorInvalidoError()


@dataclass
class Prova:
    """Prova digital — nasce ``CRIADA`` na rota selecionada (US-001).

    ``id`` é UUID gerado pela APLICAÇÃO antes do INSERT (a chave da arte no R2
    deriva dele e fica estável entre retries de colisão de código — RNF-017).
    ``rota`` não tem caminho de update em lugar nenhum (RN-007); o banco ainda
    rejeita via trigger (defesa em profundidade).
    """

    id: str
    codigo: str
    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    rota: Rota
    arte_key: str
    arte_content_type: str
    status: EstadoProva = EstadoProva.CRIADA
    # Ciclo de revisão (DP-1 do C08): nasce 1 na criação e é INCREMENTADO pelo
    # C15 (Reinício de Ciclo). Metadado mutável — fora da identidade (compare=False).
    ciclo_atual: int = field(default=1, compare=False)
    created_at: datetime | None = field(default=None, compare=False)
    updated_at: datetime | None = field(default=None, compare=False)
    # Carimbo dos estados TERMINAIS (recebida na clicheria / cancelada). Nasce
    # NULL e é populado pelo C11 nas transições terminais — o C07 só lê/filtra
    # por ele ("Finalizada em"). compare=False: metadado, fora da identidade.
    finalizada_em: datetime | None = field(default=None, compare=False)


__all__ = [
    "ARTE_TAMANHO_MAXIMO",
    "ARTE_TIPOS_PERMITIDOS",
    "CODIGO_ALFABETO",
    "CODIGO_PREFIXO",
    "CODIGO_REGEX",
    "CODIGO_SUFIXO_TAMANHO",
    "ESTADOS_EM_TRANSITO",
    "EXTENSAO_POR_TIPO",
    "ArteInvalidaError",
    "CriacaoDivergenteError",
    "EstadoProva",
    "Prova",
    "ProvaNaoEncontradaError",
    "Rota",
    "VendedorInvalidoError",
    "detectar_tipo_imagem",
    "gerar_codigo",
    "validar_arte",
    "validar_codigo",
    "validar_vendedor",
]
