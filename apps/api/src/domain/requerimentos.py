"""Domínio de requerimentos de arte — dados lidos do ERP legado (Firebird).

Camada interna (CLAUDE.md §5.2): value object PURO, sem import de framework/IO. O
requerimento é a origem de uma prova (RF-001, novo fluxo): o número informado na
criação resolve, no ERP, o nome da prova (``PRODART``), o cliente e o vendedor, além
do código de faturamento que compõe o caminho da arte no servidor de arquivos.

O ERP é fonte de **LEITURA** — nunca escrita (regra inegociável do projeto). Os
campos nulos refletem fielmente o schema legado (``NOMVEN``/``CLIENTE`` são
``NULLABLE``; ``COD_VEND_FAT`` é ``NULLABLE`` e, quando ausente, impede montar o
caminho da arte — bloqueio tratado no fluxo de criação, não aqui).
"""

from dataclasses import dataclass

from src.domain.usuarios import ErroDeDominio


class RequerimentoNaoEncontradoError(ErroDeDominio):
    """Requerimento inexistente no ERP. Mapeada a 404 na borda HTTP.

    Mensagem enxuta e sem eco do número consultado — o requerimento é digitado pelo
    admin no fluxo de criação; não há aqui a preocupação anti-enumeração de ``provas``
    (a superfície é admin-only), apenas honestidade de "não achei"."""

    codigo = "requerimento_nao_encontrado"

    def __init__(self) -> None:
        super().__init__("Requerimento não encontrado.")


class RequerimentoIncompletoError(ErroDeDominio):
    """O requerimento existe no ERP, mas faltam dados essenciais para originar a
    prova: nome do produto (``PRODART``), cliente ou o código de faturamento
    (``COD_VEND_FAT``, que compõe o caminho da arte). Mapeada a 422 (regra de
    negócio) — não se cria prova a partir de um requerimento incompleto (D11)."""

    codigo = "requerimento_incompleto"

    def __init__(self) -> None:
        super().__init__(
            "Requerimento sem dados suficientes para criar a prova "
            "(nome do produto, cliente ou código de faturamento ausente)."
        )


class VendedorNaoMapeadoError(ErroDeDominio):
    """O vendedor do requerimento (``COD_VENDE`` do ERP) não está cadastrado no
    sistema com esse código do Firebird. Mapeada a 422 — o admin precisa registrar
    o código do vendedor no cadastro do usuário antes de criar a prova (Fatia 3/4)."""

    codigo = "vendedor_nao_mapeado"

    def __init__(self) -> None:
        super().__init__(
            "O vendedor deste requerimento não está cadastrado no sistema "
            "(código do Firebird). Cadastre-o antes de criar a prova."
        )


class ArteNaoDisponivelError(ErroDeDominio):
    """O requerimento existe, mas não há imagem de arte utilizável no servidor de
    arquivos (pasta ``VERSAO\\`` ausente/vazia, ou o arquivo não é JPG/PNG válido).

    Condição de NEGÓCIO que bloqueia a criação da prova (D11): a prova nasce da arte
    aprovada; sem ela, não se cria "meia-boca". Mapeada a 422 (regra de negócio).
    Distinta de ``ArteFonteError`` (infra: servidor de arquivos fora do ar → 503)."""

    codigo = "arte_indisponivel"

    def __init__(self) -> None:
        super().__init__(
            "Não há imagem de arte disponível para este requerimento no servidor."
        )


@dataclass(frozen=True)
class RequerimentoArte:
    """Dados de um requerimento lidos do ERP (Firebird, read-only) que originam a prova.

    - ``cod_req_art``  → ``TB_REQ_ARTE.COD_REQ_ART`` (número do requerimento).
    - ``nome``         → ``TB_REQ_ARTE.PRODART`` (nome da prova).
    - ``cod_cliente``/``nome_cliente`` → ``TB_REQ_ARTE.COD_CLIEN`` + ``TB_CLIENTES.CLIENTE``.
    - ``cod_vendedor``/``nome_vendedor`` → ``TB_REQ_ARTE.COD_VENDE`` + ``TB_VENDEDOR.NOMVEN``.
    - ``cod_vend_fat`` → ``TB_VENDEDOR.COD_VEND_FAT`` (compõe o caminho da arte).
    - ``anexo_imagem`` → ``TB_REQ_ARTE.ANEXO_IMAGEM`` (arquivo OFICIAL da versão
      atual, dentro da subpasta ``VERSAO\\`` — fonte determinística da imagem).
    """

    cod_req_art: int
    nome: str | None
    cod_cliente: int
    nome_cliente: str | None
    cod_vendedor: int
    nome_vendedor: str | None
    cod_vend_fat: int | None
    anexo_imagem: str | None


__all__ = [
    "ArteNaoDisponivelError",
    "RequerimentoArte",
    "RequerimentoIncompletoError",
    "RequerimentoNaoEncontradoError",
    "VendedorNaoMapeadoError",
]
