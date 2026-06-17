"""Endpoints de provas digitais (W2-C06/C07/C08) — RF-001/002/003, RN-007, US-001.

Gate por endpoint (Matriz §7):
- **CRIAÇÃO** (``POST /provas``) é EXCLUSIVA do Administrador ("Criar Prova"):
  gate ``CRIAR_PROVA`` dentro de ``get_provas_service`` (uma sessão RLS por
  requisição — RNF-020).
- **LEITURA** — listagem (``GET /provas``), dropdown (``/provas/vendedores``),
  detalhe (``/provas/{id}``), arte (``/provas/{id}/arte``) e etiqueta
  (``/provas/{id}/etiqueta.pdf``) — é UNIVERSAL-em-escopo via
  ``get_provas_consulta_service`` (gate ``Recurso.PROVAS``); o ESCOPO de dado é
  da RLS de ``provas`` (W2-C08/DP-8: a etiqueta deixou de ser admin-only).

NÃO há endpoint de update nesta wave (DP-5 do C06): a rota é imutável (RN-007) e
as transições de status são do C11 — qualquer PATCH/PUT responde 405 por ausência.
"""

import base64
import binascii
import uuid
from datetime import date, datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, Form, Query, Response, UploadFile, status
from pydantic import BaseModel, Field

from src.adapters.inbound.http.dependencies import (
    get_cancelamento_service,
    get_identificacao_service,
    get_provas_consulta_service,
    get_provas_service,
    get_reinicio_service,
    get_transicao_service,
)
from src.application.ports.provas_repository import (
    PAGE_SIZE_MAXIMO,
    PAGE_SIZE_PADRAO,
    FiltrosProvas,
)
from src.application.provas import (
    CriarProva,
    MovimentacaoComAtor,
    ProvaListagem,
    ProvasConsultaService,
    ProvasIdentificacaoService,
    ProvasService,
    TimelineProva,
)
from src.application.transicoes import ProvasTransicaoService
from src.domain.assinaturas import ASSINATURA_TAMANHO_MAXIMO, AssinaturaInvalidaError
from src.domain.provas import ARTE_TAMANHO_MAXIMO, EstadoProva, Prova, Rota
from src.domain.state_machine.enums import Acao

# Teto do campo base64 da assinatura: ~4/3 do PNG (1 MB) + folga do prefixo
# data-URL. O teto do corpo inteiro (anti-DoS) é do ``BodyLimitMiddleware``.
ASSINATURA_BASE64_MAXIMO = (ASSINATURA_TAMANHO_MAXIMO // 3 + 1) * 4 + 64


def _decodificar_assinatura(valor: str) -> bytes:
    """Decodifica a imagem base64 da assinatura (aceita ``data:image/png;base64,``).

    Malformada → 422 (``AssinaturaInvalidaError``, mensagem genérica); o CONTEÚDO
    (magic bytes, tamanho) é validado no domínio (``validar_assinatura``)."""
    dados = valor.strip()
    if dados.startswith("data:"):
        _, _, dados = dados.partition(",")
    try:
        return base64.b64decode(dados, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AssinaturaInvalidaError("Assinatura inválida: imagem não reconhecida.") from exc

router = APIRouter(prefix="/provas", tags=["provas"])


# ---------------------------------------------------------------------------
# Schemas (validação de FORMA na borda; REGRAS vivem no domínio/serviço)
# ---------------------------------------------------------------------------
class ProvaOut(BaseModel):
    id: str
    codigo: str
    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    rota: Rota
    status: EstadoProva
    created_at: datetime | None

    @classmethod
    def de_dominio(cls, p: Prova) -> Self:
        return cls(
            id=p.id,
            codigo=p.codigo,
            nome=p.nome,
            requerimento=p.requerimento,
            cliente=p.cliente,
            vendedor_id=p.vendedor_id,
            rota=p.rota,
            status=p.status,
            created_at=p.created_at,
        )


class ProvaListagemOut(BaseModel):
    """Linha da listagem (W2-C07): acrescenta o NOME do vendedor (resolvido pela
    projeção SECURITY DEFINER — DP-7) e ``finalizada_em`` ao ``ProvaOut``."""

    id: str
    codigo: str
    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    vendedor_nome: str | None
    rota: Rota
    status: EstadoProva
    created_at: datetime | None
    finalizada_em: datetime | None

    @classmethod
    def de_dominio(cls, item: ProvaListagem) -> Self:
        p = item.prova
        return cls(
            id=p.id,
            codigo=p.codigo,
            nome=p.nome,
            requerimento=p.requerimento,
            cliente=p.cliente,
            vendedor_id=p.vendedor_id,
            vendedor_nome=item.vendedor_nome,
            rota=p.rota,
            status=p.status,
            created_at=p.created_at,
            finalizada_em=p.finalizada_em,
        )


class PaginaProvasOut(BaseModel):
    items: list[ProvaListagemOut]
    total: int
    page: int
    page_size: int


class VendedorRefOut(BaseModel):
    id: str
    nome: str


class ProvaDetalheOut(BaseModel):
    """Detalhe da prova (W2-C08): ``ProvaListagemOut`` + ``ciclo_atual`` (DP-1).

    A arte NÃO vem aqui — é servida pelo proxy ``GET /provas/{id}/arte`` (DP-5),
    para não trafegar imagem dentro do JSON nem expor a key do R2."""

    id: str
    codigo: str
    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    vendedor_nome: str | None
    rota: Rota
    status: EstadoProva
    ciclo_atual: int
    created_at: datetime | None
    finalizada_em: datetime | None

    @classmethod
    def de_dominio(cls, item: ProvaListagem) -> Self:
        p = item.prova
        return cls(
            id=p.id,
            codigo=p.codigo,
            nome=p.nome,
            requerimento=p.requerimento,
            cliente=p.cliente,
            vendedor_id=p.vendedor_id,
            vendedor_nome=item.vendedor_nome,
            rota=p.rota,
            status=p.status,
            ciclo_atual=p.ciclo_atual,
            created_at=p.created_at,
            finalizada_em=p.finalizada_em,
        )


class IdentificarIn(BaseModel):
    """Entrada da identificação (W3-C10): o conteúdo do QR OU o código digitado —
    MESMO campo, MESMO caminho (o QR carrega o próprio código — C06).

    **Sem limite de comprimento na borda, de propósito:** um código vazio, curto
    ou longo é apenas mais um valor que NÃO resolve. Deixá-lo passar para o serviço
    garante que ele seja CONTADO no rate limit e devolva o MESMO 404 genérico que o
    malformado (anti-enumeração — RN-014): nenhum 422 distinguível por comprimento.
    O teto anti-DoS do corpo inteiro é do ``BodyLimitMiddleware`` (pré-auth)."""

    codigo: str


class TransicaoIn(BaseModel):
    """Entrada da transição (W3-C11/C12). ``acao`` é a ação da §6; ``motivo`` é
    obrigatório (validado no domínio) só para Reprovar/Cancelar.

    ``assinatura`` é a IMAGEM da assinatura digital desenhada (RN-003 — W3-C12): o
    PNG do ``react-signature-canvas`` em base64 (com ou sem o prefixo data-URL). O
    backend cria a linha ``assinaturas`` e a vincula à movimentação na MESMA
    transação atômica (nascem/falham juntas — DP-1). ``idempotency_key`` é a chave
    por operação (RNF-015/DP-2): o reenvio da MESMA transição reusa a chave e
    converge, sem duplicar nem recriar a assinatura.
    """

    acao: Acao
    assinatura: str = Field(min_length=1, max_length=ASSINATURA_BASE64_MAXIMO)
    idempotency_key: uuid.UUID
    motivo: str | None = Field(default=None, max_length=500)


class CancelarIn(BaseModel):
    """Entrada do cancelamento administrativo (W3-C14 — RF-011/§6.6).

    Cancelar é "Ação administrativa: Cancelar Prova. Motivo obrigatório." (§6.6) —
    SEM assinatura desenhada (DP-2/ADR-066), ao contrário de Reprovar. Daí o corpo
    NÃO carregar ``assinatura``: só o ``motivo`` (obrigatório — ``min_length=1``,
    revalidado no domínio contra espaços) e a ``idempotency_key`` por operação
    (RNF-015: reenvio converge, sem duplicar). O ator + data/hora ficam gravados na
    movimentação pelo motor (RNF-006). Terminal e irreversível (RN-005)."""

    motivo: str = Field(min_length=1, max_length=500)
    idempotency_key: uuid.UUID


class ReiniciarIn(BaseModel):
    """Entrada do reinício de ciclo administrativo (W3-C15 — RF-009/§6.6).

    Reiniciar é "Ação administrativa: Reiniciar Ciclo" (§6.6): só CONFIRMAÇÃO —
    SEM assinatura desenhada E SEM motivo (DP-2), ao contrário de Cancelar (motivo
    obrigatório) e de Reprovar (assinatura). Daí o corpo carregar APENAS a
    ``idempotency_key`` por operação (RNF-015: reenvio converge, sem duplicar nem
    incrementar o ciclo duas vezes). O ator + data/hora ficam gravados na
    movimentação pelo motor (RNF-006)."""

    idempotency_key: uuid.UUID


class AcaoDisponivelOut(BaseModel):
    """Uma ação do fluxo de escaneamento que o ator logado pode executar AGORA
    (W3-C12/DP-3) — orienta a tela de confirmação (assinar / Aprovar / Reprovar).

    ``exige_motivo`` é ``True`` para Reprovar: a UI mostra o campo de motivo."""

    acao: Acao
    exige_motivo: bool
    estado_destino: EstadoProva


class MovimentacaoOut(BaseModel):
    """Uma movimentação do histórico (W3-C13) — uma transição registrada.

    ``ator_nome`` é o responsável resolvido (DP-2b); ``tem_assinatura`` é só o SELO
    de que houve comprovante desenhado (DP-2c — o C13 não expõe a imagem). A imagem
    da assinatura (``bytea``) NUNCA trafega aqui."""

    id: str
    estado_origem: EstadoProva
    estado_destino: EstadoProva
    acao: Acao
    ator_id: str
    ator_nome: str | None
    ciclo: int
    motivo: str | None
    tem_assinatura: bool
    created_at: datetime | None

    @classmethod
    def de_dominio(cls, item: MovimentacaoComAtor) -> Self:
        m = item.movimentacao
        return cls(
            id=m.id,
            estado_origem=m.estado_origem,
            estado_destino=m.estado_destino,
            acao=m.acao,
            ator_id=m.ator_id,
            ator_nome=item.ator_nome,
            ciclo=m.ciclo,
            motivo=m.motivo,
            tem_assinatura=m.assinatura_ref is not None,
            created_at=m.created_at,
        )


class TimelineOut(BaseModel):
    """Insumo da Timeline visual (W3-C13): histórico + esqueleto da rota.

    ``etapas_canonicas`` é a sequência de estados do caminho NORMAL da rota,
    DERIVADA das ``transition_rules`` do C11 (DP-1 — fonte única, não duplica a
    §6). O frontend a usa como esqueleto (etapas percorridas/atual/futuras),
    sobrepõe ``movimentacoes`` (asc) e agrupa por ``ciclo`` (DP-3). ``criada_em``
    carimba o nó inicial ``CRIADA`` (a prova nasce nesse estado — não há
    movimentação para ele)."""

    rota: Rota
    estado_atual: EstadoProva
    ciclo_atual: int
    criada_em: datetime | None
    etapas_canonicas: list[EstadoProva]
    movimentacoes: list[MovimentacaoOut]

    @classmethod
    def de_dominio(cls, t: TimelineProva) -> Self:
        return cls(
            rota=t.rota,
            estado_atual=t.estado_atual,
            ciclo_atual=t.ciclo_atual,
            criada_em=t.criada_em,
            etapas_canonicas=list(t.etapas_canonicas),
            movimentacoes=[MovimentacaoOut.de_dominio(m) for m in t.movimentacoes],
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=PaginaProvasOut)
async def listar(
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
    # Busca (RF-013): nome E/OU requerimento. Filtros combináveis (RF-014).
    busca: Annotated[str | None, Query(max_length=200)] = None,
    cliente: Annotated[str | None, Query(max_length=200)] = None,
    # status aceita MÚLTIPLOS valores (W4-C16): ?status=a&status=b → "qualquer um"
    # (IN). Um único valor segue funcionando (compat. C07). ``alias`` mantém o nome
    # ``status`` na query string.
    status_filtro: Annotated[list[EstadoProva] | None, Query(alias="status")] = None,
    rota: Rota | None = None,
    vendedor_id: uuid.UUID | None = None,
    criada_de: date | None = None,
    criada_ate: date | None = None,
    finalizada_de: date | None = None,
    finalizada_ate: date | None = None,
    # Filtro "Atrasadas" (W4-C16/DP-6): destino do clique no card de Atrasadas do
    # Dashboard. Reusa a regra de horas úteis + limiar do C09 no backend.
    atrasada: Annotated[bool, Query()] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAXIMO)] = PAGE_SIZE_PADRAO,
) -> PaginaProvasOut:
    """Listagem paginada server-side (RNF-019), ordenada por ``created_at`` desc.

    Acessível a todos os perfis; o ESCOPO de dado (Vendedor as próprias, Motorista
    as "Em Trânsito") é da RLS de ``provas`` (claims propagados — ADR-008). Query
    fora do escopo retorna simplesmente 0 registros (anti-enumeração)."""
    pagina = await service.listar(
        FiltrosProvas(
            busca=busca,
            cliente=cliente,
            status=tuple(status_filtro) if status_filtro else (),
            rota=rota,
            vendedor_id=str(vendedor_id) if vendedor_id is not None else None,
            criada_de=criada_de,
            criada_ate=criada_ate,
            finalizada_de=finalizada_de,
            finalizada_ate=finalizada_ate,
            atrasada=atrasada,
            page=page,
            page_size=page_size,
        )
    )
    return PaginaProvasOut(
        items=[ProvaListagemOut.de_dominio(i) for i in pagina.items],
        total=pagina.total,
        page=pagina.page,
        page_size=pagina.page_size,
    )


@router.get("/vendedores", response_model=list[VendedorRefOut])
async def vendedores(
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
) -> list[VendedorRefOut]:
    """Vendedores em escopo (distintos das provas visíveis) para o dropdown de
    filtro — alimenta o "Vendedor: Todos" sem vazar nomes fora do escopo."""
    return [VendedorRefOut(id=v.id, nome=v.nome) for v in await service.vendedores()]


@router.post("", response_model=ProvaOut, status_code=status.HTTP_201_CREATED)
async def criar(
    service: Annotated[ProvasService, Depends(get_provas_service)],
    # multipart/form-data: campos obrigatórios do RF-001. ``pattern=r"\S"``
    # exige ao menos um caractere não-branco (Pydantic v2 usa re.search);
    # requerimento é numérico ancorado (decisão da sessão: texto de dígitos,
    # preserva zeros à esquerda). Rota ausente → 422 (validation_error).
    nome: Annotated[str, Form(min_length=1, max_length=200, pattern=r"\S")],
    requerimento: Annotated[str, Form(min_length=1, max_length=50, pattern=r"^\d{1,50}$")],
    cliente: Annotated[str, Form(min_length=1, max_length=200, pattern=r"\S")],
    vendedor_id: Annotated[uuid.UUID, Form()],
    rota: Annotated[Rota, Form()],
    arte: UploadFile,
    # Chave de idempotência gerada pelo cliente (RNF-015): reenvio após
    # resposta perdida converge para a prova já criada em vez de duplicar.
    prova_id: Annotated[uuid.UUID | None, Form()] = None,
) -> ProvaOut:
    """Criação ATÔMICA da prova (RNF-017): arte no R2 + INSERT com código único.

    Lê no MÁXIMO 10 MB + 1 byte do upload para a MEMÓRIA do processo; o teto
    do corpo inteiro da requisição (anti-DoS, inclusive pré-auth) é do
    ``BodyLimitMiddleware``.
    """
    conteudo = await arte.read(ARTE_TAMANHO_MAXIMO + 1)
    prova = await service.criar(
        CriarProva(
            nome=nome,
            requerimento=requerimento,
            cliente=cliente,
            vendedor_id=str(vendedor_id),
            rota=rota,
            prova_id=str(prova_id) if prova_id is not None else None,
        ),
        arte=conteudo,
        arte_content_type_declarado=arte.content_type,
    )
    return ProvaOut.de_dominio(prova)


@router.post("/identificar", response_model=ProvaDetalheOut)
async def identificar(
    body: IdentificarIn,
    service: Annotated[ProvasIdentificacaoService, Depends(get_identificacao_service)],
) -> ProvaDetalheOut:
    """Identifica a prova pelo QR ou pelo código manual (RF-004/RF-005) — a ponte
    física→digital. UNIVERSAL-em-escopo (Matriz §7 "Escanear"); o ESCOPO de dado é
    da RLS de ``provas`` (claims propagados — ADR-008).

    Anti-enumeração (RN-014): código inválido, inexistente E fora do escopo →
    MESMO 404 genérico (``prova_nao_encontrada``). Rate limiting: 30 tentativas/
    ator/minuto → 429 (``limite_de_tentativas``). Idempotente quanto ao mecanismo:
    QR e digitação resolvem o MESMO registro pelo mesmo ``resolver_prova()``. Só
    IDENTIFICA — a transição é do C11 e a assinatura do C12 (DP-2): o cliente leva
    a prova resolvida à tela de confirmação.
    """
    return ProvaDetalheOut.de_dominio(await service.identificar(body.codigo))


@router.get("/{prova_id}/acoes-disponiveis", response_model=list[AcaoDisponivelOut])
async def acoes_disponiveis(
    prova_id: uuid.UUID,
    service: Annotated[ProvasTransicaoService, Depends(get_transicao_service)],
) -> list[AcaoDisponivelOut]:
    """Ações do fluxo de escaneamento que o ator logado pode executar na prova
    AGORA (W3-C12/DP-3) — orienta a tela de confirmação (assinar automaticamente
    vs Aprovar/Reprovar vs bloqueio genérico). Reusa as regras do C11
    (``transicoes_de`` + ``autoriza``), sem duplicar a §6; Cancelar/Reiniciar
    (C14/C15) NÃO entram (têm UI própria).

    Lista vazia = não é a vez do ator → a UI mostra o bloqueio genérico, SEM
    revelar quem é o próximo (RN-014). Prova fora do escopo / inexistente → 404
    genérico (anti-enumeração — a RLS escopa a leitura)."""
    transicoes = await service.acoes_disponiveis(str(prova_id))
    return [
        AcaoDisponivelOut(acao=t.acao, exige_motivo=t.exige_motivo, estado_destino=t.estado_destino)
        for t in transicoes
    ]


@router.post("/{prova_id}/transicoes", response_model=ProvaDetalheOut)
async def transicionar(
    prova_id: uuid.UUID,
    body: TransicaoIn,
    service: Annotated[ProvasTransicaoService, Depends(get_transicao_service)],
) -> ProvaDetalheOut:
    """Executa uma transição da máquina de estados (W3-C11) gravando a assinatura
    desenhada como comprovante (W3-C12/RN-003) — o "confirmar" do fluxo
    identificar → assinar → confirmar (§6/RF-007). ATÔMICA (RNF-017): a assinatura
    e a movimentação nascem/falham JUNTAS. IDEMPOTENTE (RNF-015): reenvio com a
    mesma ``idempotency_key`` converge (sem recriar a assinatura).

    Erros: assinatura malformada/ inválida → 422; transição não definida → 422;
    perfil não autorizado → 403 (genérico, sem revelar o próximo ator — RN-014);
    prova fora do escopo / inexistente → 404 genérico (anti-enumeração); chave
    reusada para outra operação → 409. Quem dispara Cancelar/Reiniciar pela UI é
    o C14/C15 — todos INVOCAM este endpoint.
    """
    item = await service.executar(
        prova_id=str(prova_id),
        acao=body.acao,
        assinatura_imagem=_decodificar_assinatura(body.assinatura),
        idempotency_key=str(body.idempotency_key),
        motivo=body.motivo,
    )
    return ProvaDetalheOut.de_dominio(item)


@router.post("/{prova_id}/cancelar", response_model=ProvaDetalheOut)
async def cancelar(
    prova_id: uuid.UUID,
    body: CancelarIn,
    service: Annotated[ProvasTransicaoService, Depends(get_cancelamento_service)],
) -> ProvaDetalheOut:
    """Cancela uma prova (W3-C14 — RF-011/§6.6/RN-005): ação ADMINISTRATIVA,
    exclusiva do 3Studio (flag ``administrador`` — ADR-064), disponível em qualquer
    estado ATIVO. Terminal e IRREVERSÍVEL: a prova vira ``Cancelada`` e não pode ser
    reativada (cria-se uma nova prova se preciso); o histórico é preservado.

    INVOCA o motor de transição do C11 (``executar`` com ``acao=cancelar``) — fonte
    ÚNICA de mudança de status (ADR-062): atômico, idempotente, gravando a
    movimentação (ator + data/hora + motivo) no log imutável (RNF-006). SEM
    assinatura desenhada (``assinatura_imagem=None`` — DP-2): a movimentação nasce
    com ``assinatura_ref`` NULL (ADR-066).

    Acesso em DUAS camadas: a borda (``get_cancelamento_service``) já barra o
    não-admin → 403; o motor revalida (``Autorizacao.ADMIN``). Erros: motivo ausente
    → 422 (schema/domínio); prova já Cancelada/Recebida-Clicheria (terminal) →
    transição indefinida → 422; prova fora do escopo / inexistente → 404 genérico
    (anti-enumeração); chave reusada para outra operação → 409.
    """
    item = await service.executar(
        prova_id=str(prova_id),
        acao=Acao.CANCELAR,
        assinatura_imagem=None,
        idempotency_key=str(body.idempotency_key),
        motivo=body.motivo,
    )
    return ProvaDetalheOut.de_dominio(item)


@router.post("/{prova_id}/reiniciar", response_model=ProvaDetalheOut)
async def reiniciar(
    prova_id: uuid.UUID,
    body: ReiniciarIn,
    service: Annotated[ProvasTransicaoService, Depends(get_reinicio_service)],
) -> ProvaDetalheOut:
    """Reinicia o ciclo de uma prova reprovada (W3-C15 — RF-009/§6.6/RN-006): ação
    ADMINISTRATIVA, exclusiva do 3Studio (flag ``administrador`` — ADR-064),
    disponível SÓ em ``Reprovada pelo Vendedor``. Volta o status a ``Criada``,
    PRESERVA a rota (imutável) e o histórico integral do ciclo anterior, e
    INCREMENTA ``ciclo_atual`` — a MESMA prova ganha um novo ciclo (mesmo código/QR/
    etiqueta).

    INVOCA o motor de transição do C11 (``executar`` com ``acao=reiniciar_ciclo``) —
    fonte ÚNICA de mudança de status (ADR-062): a transição (``reprovada_vendedor``
    → ``criada``) e o incremento de ``ciclo_atual`` caem na MESMA transação atômica
    (RNF-017 — juntos ou nenhum), gravando UMA movimentação (ator + data/hora) no
    log imutável (RNF-006). SEM assinatura desenhada E SEM motivo (DP-2): a
    movimentação nasce com ``assinatura_ref`` NULL (ADR-066).

    Acesso em DUAS camadas: a borda (``get_reinicio_service``) já barra o não-admin
    → 403; o motor revalida (``Autorizacao.ADMIN``). Erros: prova fora de
    ``Reprovada pelo Vendedor`` → transição indefinida → 422; prova fora do escopo /
    inexistente → 404 genérico (anti-enumeração); chave reusada para outra operação
    → 409. Reenvio com a mesma chave converge (200) sem reincrementar o ciclo.
    """
    item = await service.executar(
        prova_id=str(prova_id),
        acao=Acao.REINICIAR_CICLO,
        assinatura_imagem=None,
        idempotency_key=str(body.idempotency_key),
        motivo=None,
    )
    return ProvaDetalheOut.de_dominio(item)


@router.get("/{prova_id}", response_model=ProvaDetalheOut)
async def detalhe(
    prova_id: uuid.UUID,
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
) -> ProvaDetalheOut:
    """Detalhe de UMA prova (W2-C08) — página UNIVERSAL escopada pela RLS.

    Acessível a qualquer perfil ativo; o ESCOPO é da RLS de ``provas`` (claims
    propagados — ADR-008). Prova inexistente e prova fora do escopo retornam o
    MESMO 404 genérico (anti-enumeração — CLAUDE.md §11): a UI redireciona para a
    listagem e mostra um toast, sem revelar se a prova existe.
    """
    return ProvaDetalheOut.de_dominio(await service.obter(str(prova_id)))


@router.get("/{prova_id}/movimentacoes", response_model=TimelineOut)
async def movimentacoes(
    prova_id: uuid.UUID,
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
) -> TimelineOut:
    """Histórico de movimentações + esqueleto da rota para a Timeline (W3-C13).

    Página UNIVERSAL escopada pela RLS — MESMO gate/escopo do detalhe (Matriz §7):
    qualquer perfil ativo, dados escopados pela RLS de ``movimentacoes`` (espelha
    ``provas``). Prova inexistente e prova fora do escopo retornam o MESMO 404
    genérico (anti-enumeração — CLAUDE.md §11). ``etapas_canonicas`` deriva das
    regras do C11 (DP-1 — não duplica a §6); ``movimentacoes`` vêm em ordem
    cronológica, com o responsável resolvido e o selo de assinatura (sem a imagem).
    """
    return TimelineOut.de_dominio(await service.obter_movimentacoes(str(prova_id)))


@router.get("/{prova_id}/arte")
async def arte(
    prova_id: uuid.UUID,
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
) -> Response:
    """PROXY da arte do R2 privado (W2-C08/DP-5) — escopado pela RLS.

    O backend lê o objeto do R2 e streama os bytes: a key do R2 NUNCA é exposta
    ao cliente e não há URL pública. Fora do escopo / inexistente → MESMO 404
    genérico (a prova é resolvida antes de tocar o storage). ``Cache-Control:
    private`` permite cache só no navegador do próprio usuário."""
    dados, content_type = await service.obter_arte(str(prova_id))
    return Response(
        content=dados,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/{prova_id}/etiqueta.pdf")
async def etiqueta(
    prova_id: uuid.UUID,
    service: Annotated[ProvasConsultaService, Depends(get_provas_consulta_service)],
) -> Response:
    """Etiqueta PDF sob demanda (RF-003) — 95 x 55 mm, com o código em destaque.

    UNIVERSAL-em-escopo (DP-8): qualquer perfil que ENXERGA a prova (RLS) pode
    imprimir a etiqueta dela. Prova inexistente e prova fora do escopo retornam o
    MESMO 404 genérico (anti-enumeração — a RLS não distingue e a borda também não).
    """
    pdf, codigo = await service.gerar_etiqueta(str(prova_id))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="etiqueta-{codigo}.pdf"'},
    )


__all__ = ["router"]
