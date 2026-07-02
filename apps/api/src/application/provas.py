"""Casos de uso de provas digitais (W2-C06) — RF-001/002/003, RN-007, US-001.

Criação ATÔMICA (RNF-017) com a arte no R2 (porta do C01), na ordem que não
deixa órfãos nem segura conexão de banco atravessando IO externo:

1. valida arte (magic bytes) e vendedor (setor Vendedor ativo) — leituras;
2. fecha a transação de leitura (a conexão não fica idle-in-transaction
   durante o upload — mesmo princípio do ``UsuariosService``);
3. faz o upload da arte no R2 sob chave derivada do ``id`` da prova (gerado
   pela aplicação — estável entre retries de colisão de código);
4. INSERT + COMMIT com retry de colisão do código (DP-3); qualquer falha após
   o upload COMPENSA o objeto no R2 (delete idempotente, CRITICAL se a própria
   compensação falhar — RNF-024).

Resultado: prova órfã nunca existe (o commit só acontece com a arte já no R2);
o pior caso é um objeto órfão no R2, marcado em log para limpeza.

Idempotência (RNF-015): o cliente envia o ``prova_id`` (UUID gerado no form)
como CHAVE DE IDEMPOTÊNCIA. Reenvio após resposta perdida (timeout/abort com o
INSERT já commitado) CONVERGE para a prova existente — mesmos dados → devolve a
prova já criada (a arte regrava a MESMA key, put idempotente); dados diferentes
sob a mesma chave → 409 (``CriacaoDivergenteError``), nunca duplicata nem
sobrescrita silenciosa. Sem ``prova_id`` (clientes antigos), o id é gerado aqui
e cada POST cria uma prova nova.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.ports.audit_log import AuditLogPort
from src.application.ports.etiqueta import EtiquetaPort
from src.application.ports.event_bus import EventBusPort
from src.application.ports.movimentacoes_repository import MovimentacoesRepositoryPort
from src.application.ports.provas_repository import (
    CodigoJaExisteError,
    FiltrosProvas,
    ProvaJaExisteError,
    ProvasRepositoryPort,
)
from src.application.ports.rate_limiter import RateLimiterPort
from src.application.ports.settings_repository import SettingsRepositoryPort
from src.application.ports.storage import StorageObjectNotFound, StoragePort
from src.application.ports.unit_of_work import UnitOfWork
from src.application.ports.usuarios_repository import UsuariosRepositoryPort
from src.domain.auditoria import EventoAuditoria, NovoEventoAuditoria
from src.domain.movimentacoes import Movimentacao
from src.domain.provas import (
    EXTENSAO_POR_TIPO,
    CriacaoDivergenteError,
    EstadoProva,
    LimiteDeTentativasError,
    Prova,
    ProvaNaoEncontradaError,
    Rota,
    gerar_codigo,
    normalizar_codigo,
    validar_arte,
    validar_codigo,
    validar_vendedor,
)
from src.domain.settings import CHAVE_ETIQUETA, ConfiguracaoEtiqueta, efetivar_config_etiqueta
from src.domain.state_machine.machine import sequencia_canonica

logger = logging.getLogger("rastreio.provas")

# Tentativas de geração do código em colisão (DP-3). Com 31^6 ≈ 887 milhões de
# combinações por mês, esgotar 5 tentativas indica problema sistêmico (relógio,
# RNG) — vira erro interno alto, não silêncio.
MAX_TENTATIVAS_CODIGO = 5


class GeracaoDeCodigoEsgotadaError(Exception):
    """Colisões consecutivas além do plausível — erro INTERNO (500), nunca 422."""


@dataclass(frozen=True)
class CriarProva:
    """Comando de criação — payload já validado em FORMA pela borda HTTP.

    ``prova_id`` é a chave de idempotência gerada pelo CLIENTE (RNF-015): o
    mesmo form reenviado carrega o mesmo UUID e converge. Opcional — sem ela,
    o serviço gera o id e cada POST cria uma prova nova.
    """

    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    rota: Rota
    prova_id: str | None = None


class ProvasService:
    """Fachada dos casos de uso de provas (uma instância por requisição).

    A sessão por trás de ``repo``/``uow`` DEVE vir de ``abrir_sessao_rls`` — o
    escopo de leitura (Vendedor as próprias, Motorista as "Em Trânsito") é da
    RLS, não reimplementado aqui.
    """

    def __init__(
        self,
        repo: ProvasRepositoryPort,
        usuarios_repo: UsuariosRepositoryPort,
        storage: StoragePort,
        uow: UnitOfWork,
        relogio: Callable[[], datetime] | None = None,
        audit: AuditLogPort | None = None,
        eventos: EventBusPort | None = None,
    ) -> None:
        self._repo = repo
        self._usuarios_repo = usuarios_repo
        self._storage = storage
        self._uow = uow
        self._relogio = relogio or (lambda: datetime.now(UTC))
        # W6-C20: captura "criou_prova" no log de auditoria, na MESMA transação do
        # INSERT da prova (atômica). Opcional: ausente nos testes de criação que não
        # exercem auditoria (logar é efeito colateral — não muda a regra; §3.6).
        self._audit = audit
        # Etapa 3 (realtime): sinal genérico "prova mudou" para o SSE do dashboard,
        # na MESMA transação do INSERT (só entregue no commit). Opcional: ausente nos
        # testes que não exercem o realtime (efeito colateral — §3.6).
        self._eventos = eventos

    # ------------------------------------------------------------------- criar
    async def criar(
        self, cmd: CriarProva, arte: bytes, arte_content_type_declarado: str | None
    ) -> Prova:
        """Cria a prova no estado ``CRIADA`` na rota selecionada (US-001)."""
        tipo = validar_arte(arte, arte_content_type_declarado)
        vendedor = await self._usuarios_repo.get(cmd.vendedor_id)
        validar_vendedor(vendedor)

        prova_id = cmd.prova_id or str(uuid.uuid4())
        # Idempotência (RNF-015): reenvio após resposta perdida converge ANTES
        # de qualquer upload — não regrava a arte nem toca o banco de novo.
        if cmd.prova_id is not None:
            existente = await self._repo.get(prova_id)
            if existente is not None:
                return self._convergir(existente, cmd)

        # Libera a conexão da leitura antes do IO externo (idle-in-transaction).
        await self._uow.rollback()

        arte_key = f"provas/{prova_id}/arte{EXTENSAO_POR_TIPO[tipo]}"
        # Porta síncrona (boto3) fora do event loop — mesmo padrão do readiness.
        await asyncio.to_thread(self._storage.upload, arte_key, arte, tipo)

        try:
            prova = await self._inserir_com_retry(cmd, prova_id, arte_key, tipo)
        except ProvaJaExisteError:
            # Corrida da idempotência: uma requisição idêntica venceu entre o
            # pré-check e o INSERT. SEM compensação — a arte_key pertence à
            # prova existente (o put regravou os mesmos bytes).
            existente = await self._repo.get(prova_id)
            if existente is None:  # pragma: no cover — PK violada e linha sumiu
                raise
            return self._convergir(existente, cmd)
        except Exception:
            await self._compensar_arte(arte_key)
            raise

        logger.info(
            "prova criada",
            extra={
                "event": "prova_criada",
                "prova_id": prova.id,
                "codigo": prova.codigo,
                "rota": prova.rota.value,
                "vendedor_id": prova.vendedor_id,
            },
        )
        return prova

    @staticmethod
    def _convergir(existente: Prova, cmd: CriarProva) -> Prova:
        """Resolução da chave de idempotência repetida (RNF-015).

        Mesmos dados → devolve a prova já criada (reenvio legítimo). Dados
        diferentes sob a mesma chave → 409: o cliente renova a chave quando o
        form muda; divergência aqui é bug/abuso, nunca sobrescrita.
        """
        coincide = (
            existente.nome == cmd.nome.strip()
            and existente.requerimento == cmd.requerimento.strip()
            and existente.cliente == cmd.cliente.strip()
            and existente.vendedor_id == cmd.vendedor_id
            and existente.rota is cmd.rota
        )
        if not coincide:
            raise CriacaoDivergenteError()
        logger.info(
            "criação idempotente convergiu (reenvio após resposta perdida)",
            extra={"event": "prova_criacao_idempotente", "prova_id": existente.id},
        )
        return existente

    async def _inserir_com_retry(
        self, cmd: CriarProva, prova_id: str, arte_key: str, tipo: str
    ) -> Prova:
        """INSERT atômico com retry de colisão do código único (DP-3).

        A colisão aborta a transação no Postgres — cada tentativa é uma
        transação NOVA (o ``async with`` faz rollback ao sair com exceção).
        """
        for _ in range(MAX_TENTATIVAS_CODIGO):
            prova = Prova(
                id=prova_id,
                codigo=gerar_codigo(self._relogio()),
                nome=cmd.nome.strip(),
                requerimento=cmd.requerimento.strip(),
                cliente=cmd.cliente.strip(),
                vendedor_id=cmd.vendedor_id,
                rota=cmd.rota,
                arte_key=arte_key,
                arte_content_type=tipo,
            )
            try:
                async with self._uow:
                    await self._repo.add(prova)
                    if self._audit is not None:
                        await self._audit.registrar(
                            NovoEventoAuditoria(
                                evento=EventoAuditoria.CRIOU_PROVA,
                                prova_id=prova.id,
                                prova_codigo=prova.codigo,
                                prova_cliente=prova.cliente,
                                prova_requerimento=prova.requerimento,
                            )
                        )
                    # Etapa 3 (realtime): sinaliza "prova mudou" na MESMA transação
                    # do INSERT — só entregue no commit (atômico). A criação nasce
                    # ``CRIADA`` e alimenta o contador "Criadas hoje" do dashboard.
                    if self._eventos is not None:
                        await self._eventos.publicar_mudanca_de_prova()
                    await self._uow.commit()
            except CodigoJaExisteError:
                logger.warning(
                    "colisão de código de prova — regenerando",
                    extra={"event": "codigo_colisao", "prova_id": prova_id},
                )
                continue
            return prova
        raise GeracaoDeCodigoEsgotadaError(
            f"{MAX_TENTATIVAS_CODIGO} colisões consecutivas de código de prova."
        )

    async def _compensar_arte(self, arte_key: str) -> None:
        try:
            await asyncio.to_thread(self._storage.delete, arte_key)
            logger.warning(
                "compensação executada: arte removida do R2 após falha no banco",
                extra={"event": "compensacao_arte", "arte_key": arte_key},
            )
        except Exception:
            logger.critical(
                "compensação FALHOU: arte órfã no R2 (limpeza manual)",
                exc_info=True,
                extra={"event": "compensacao_arte_falhou", "arte_key": arte_key},
            )


# ---------------------------------------------------------------------------
# Leitura / listagem (W2-C07) + detalhe/arte/etiqueta (W2-C08)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VendedorRef:
    """Vendedor para o dropdown de filtro (id + nome resolvido)."""

    id: str
    nome: str


@dataclass(frozen=True)
class ProvaListagem:
    """Linha da listagem: a prova + o NOME do vendedor (join de apresentação).

    ``vendedor_nome`` é resolvido por ``nomes_de_vendedores`` (DP-7) e pode ser
    ``None`` no caso impossível-mas-seguro de o vendedor sumir do projetor.
    """

    prova: Prova
    vendedor_nome: str | None


@dataclass(frozen=True)
class PaginaProvasListagem:
    items: list[ProvaListagem]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class MovimentacaoComAtor:
    """Uma movimentação + o NOME do responsável (W3-C13/DP-2b).

    ``ator_nome`` é resolvido por ``nomes_de_atores`` (projeção SECURITY DEFINER) e
    pode ser ``None`` no caso impossível-mas-seguro de o ator sumir do projetor."""

    movimentacao: Movimentacao
    ator_nome: str | None


@dataclass(frozen=True)
class TimelineProva:
    """Insumo da Timeline (W3-C13): o histórico da prova + o esqueleto da rota.

    ``etapas_canonicas`` é a sequência de estados do caminho normal da rota
    (DERIVADA de ``TRANSITION_RULES`` — DP-1; a §6 não é duplicada). O frontend
    sobrepõe ``movimentacoes`` (ordenadas asc) ao esqueleto, destaca ``estado_atual``
    e agrupa por ``ciclo`` (DP-3). ``criada_em`` carimba o nó inicial ``CRIADA``
    (que não é uma movimentação — a prova nasce nesse estado)."""

    rota: Rota
    estado_atual: EstadoProva
    ciclo_atual: int
    criada_em: datetime | None
    etapas_canonicas: tuple[EstadoProva, ...]
    movimentacoes: list[MovimentacaoComAtor]


class ProvasConsultaService:
    """Casos de uso de LEITURA de provas (W2-C07 listagem + W2-C08 detalhe/arte/etiqueta).

    Página/detalhe acessíveis a QUALQUER perfil ativo (Matriz §7: ``provas``
    universal); o ESCOPO de dado (Vendedor as próprias, Motorista as "Em Trânsito")
    é da RLS de ``provas`` (C06) — NÃO reimplementado aqui. Prova fora do escopo e
    prova inexistente são o MESMO 404 (anti-enumeração — CLAUDE.md §11).

    ``storage``/``etiqueta`` só são exigidos pelos caminhos de arte/etiqueta (C08);
    são opcionais para manter os testes de listagem (que só usam ``listar``/
    ``vendedores``) sem dublês de IO. A injeção real (DI) sempre os fornece.
    ``settings_repo`` (W2-C09) alimenta a etiqueta com a configuração do template
    (RN-011); ausente → template padrão (degradação graciosa).
    """

    def __init__(
        self,
        repo: ProvasRepositoryPort,
        storage: StoragePort | None = None,
        etiqueta: EtiquetaPort | None = None,
        settings_repo: SettingsRepositoryPort | None = None,
        movs: MovimentacoesRepositoryPort | None = None,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._etiqueta = etiqueta
        self._settings_repo = settings_repo
        # W3-C13: o histórico (Timeline) só é exigido por ``obter_movimentacoes``;
        # opcional para os testes de listagem/detalhe não dublarem o repo de movs.
        self._movs = movs

    # ----------------------------------------------------------------- detalhe
    async def obter(self, prova_id: str) -> ProvaListagem:
        """Detalhe de UMA prova (C08): a prova + o nome do vendedor (DP-7).

        Escopada pela RLS (claims propagados): fora do escopo / inexistente → o
        MESMO ``ProvaNaoEncontradaError`` (404 genérico — anti-enumeração)."""
        prova = await self._repo.get(prova_id)
        if prova is None:
            raise ProvaNaoEncontradaError()
        nomes = await self._repo.nomes_de_vendedores([prova.vendedor_id])
        return ProvaListagem(prova=prova, vendedor_nome=nomes.get(prova.vendedor_id))

    # ---------------------------------------------------------------- timeline
    async def obter_movimentacoes(self, prova_id: str) -> TimelineProva:
        """Histórico + esqueleto da rota para a Timeline (W3-C13/DP-1/DP-2).

        Resolve a prova ANTES (escopada pela RLS) — fora do escopo / inexistente →
        o MESMO 404 genérico (anti-enumeração — igual ao detalhe). Depois lê o
        histórico (escopado pela RLS de ``movimentacoes``) e resolve os nomes dos
        atores numa ÚNICA ida ao projetor (sem N+1 — RNF-022). O caminho canônico
        vem de ``sequencia_canonica`` (DP-1 — fonte única, não duplica a §6)."""
        prova = await self._repo.get(prova_id)
        if prova is None:
            raise ProvaNaoEncontradaError()
        movs_repo = self._movs_obrigatorio()
        movs = await movs_repo.listar_por_prova(prova_id)
        ids = list({m.ator_id for m in movs})
        nomes = await movs_repo.nomes_de_atores(ids) if ids else {}
        return TimelineProva(
            rota=prova.rota,
            estado_atual=prova.status,
            ciclo_atual=prova.ciclo_atual,
            criada_em=prova.created_at,
            etapas_canonicas=sequencia_canonica(prova.rota),
            movimentacoes=[MovimentacaoComAtor(m, nomes.get(m.ator_id)) for m in movs],
        )

    def _movs_obrigatorio(self) -> MovimentacoesRepositoryPort:
        if self._movs is None:  # pragma: no cover — a DI sempre injeta
            raise RuntimeError("MovimentacoesRepositoryPort não configurada no serviço.")
        return self._movs

    async def obter_arte(self, prova_id: str) -> tuple[bytes, str]:
        """Bytes da arte + content-type, para o PROXY de imagem do C08 (DP-5).

        A prova é resolvida (e escopada pela RLS) ANTES de tocar o storage — fora
        do escopo / inexistente → 404 genérico, sem revelar a key do R2. O objeto
        nunca é exposto por URL pública: o backend lê do R2 e streama."""
        prova = await self._repo.get(prova_id)
        if prova is None:
            raise ProvaNaoEncontradaError()
        storage = self._storage_obrigatorio()
        try:
            dados = await asyncio.to_thread(storage.download, prova.arte_key)
        except StorageObjectNotFound as exc:
            # Prova VISÍVEL pela RLS mas objeto ausente no R2 = inconsistência de
            # dado (arte órfã/perdida — a criação é atômica, RNF-017). Vira 404
            # (anti-enumeração: mesmo 404 do inexistente), NUNCA o 503
            # "storage_indisponivel" — que faria o cliente retentar em loop um
            # arquivo que não voltará. Logado para limpeza manual (RNF-024).
            logger.error(
                "arte ausente no R2 para prova visível",
                extra={"event": "arte_ausente", "prova_id": prova.id, "arte_key": prova.arte_key},
            )
            raise ProvaNaoEncontradaError() from exc
        return dados, prova.arte_content_type

    # ---------------------------------------------------------------- etiqueta
    async def gerar_etiqueta(self, prova_id: str) -> tuple[bytes, str]:
        """Etiqueta PDF sob demanda (RF-003) — stateless, nada é armazenado (DP-8).

        Servida pelo caminho UNIVERSAL (qualquer perfil em escopo que enxerga a
        prova pode imprimir a etiqueta dela). Devolve ``(pdf, codigo)``; o código
        nomeia o arquivo no download. Nome do vendedor resolvido por
        ``nomes_de_vendedores`` (DP-7) — funciona para qualquer perfil em escopo;
        fallback ASCII "-" (um travessão derrubaria as fontes core latin-1).
        Prova fora do escopo / inexistente → 404 genérico (anti-enumeração)."""
        prova = await self._repo.get(prova_id)
        if prova is None:
            raise ProvaNaoEncontradaError()
        etiqueta = self._etiqueta_obrigatoria()
        nomes = await self._repo.nomes_de_vendedores([prova.vendedor_id])
        vendedor_nome = nomes.get(prova.vendedor_id) or "-"
        # W2-C09 (RN-011): a etiqueta passa a respeitar a configuração salva do
        # template (padrão/personalizado). Lida na MESMA sessão RLS (leitura
        # authenticated — DP-2); falha na leitura cai no padrão (uma etiqueta
        # sempre sai — mesma filosofia da degradação cp1252 do C06).
        config = await self._config_etiqueta()
        pdf = await asyncio.to_thread(etiqueta.gerar_pdf, prova, vendedor_nome, config)
        return pdf, prova.codigo

    async def _config_etiqueta(self) -> ConfiguracaoEtiqueta | None:
        if self._settings_repo is None:
            return None  # caminhos sem settings (testes) → template padrão
        try:
            registro = await self._settings_repo.obter(CHAVE_ETIQUETA)
        except Exception:
            logger.warning(
                "config da etiqueta indisponível — usando template padrão",
                extra={"event": "config_etiqueta_indisponivel"},
            )
            return None
        return efetivar_config_etiqueta(registro.valor if registro is not None else None)

    def _storage_obrigatorio(self) -> StoragePort:
        if self._storage is None:  # pragma: no cover — a DI sempre injeta
            raise RuntimeError("StoragePort não configurada no serviço de consulta de provas.")
        return self._storage

    def _etiqueta_obrigatoria(self) -> EtiquetaPort:
        if self._etiqueta is None:  # pragma: no cover — a DI sempre injeta
            raise RuntimeError("EtiquetaPort não configurada no serviço de consulta de provas.")
        return self._etiqueta

    async def listar(self, filtros: FiltrosProvas) -> PaginaProvasListagem:
        pagina = await self._repo.listar(filtros.saneados())
        ids = list({p.vendedor_id for p in pagina.items})
        # UMA ida ao projetor de nomes para a página inteira (sem N+1 — RNF-022).
        nomes = await self._repo.nomes_de_vendedores(ids) if ids else {}
        items = [
            ProvaListagem(prova=p, vendedor_nome=nomes.get(p.vendedor_id)) for p in pagina.items
        ]
        return PaginaProvasListagem(
            items=items, total=pagina.total, page=pagina.page, page_size=pagina.page_size
        )

    async def vendedores(self) -> list[VendedorRef]:
        """Vendedores em escopo para o dropdown — distintos das provas visíveis."""
        ids = await self._repo.vendedor_ids_distintos()
        if not ids:
            return []
        nomes = await self._repo.nomes_de_vendedores(ids)
        refs = [VendedorRef(id=i, nome=nomes[i]) for i in ids if i in nomes]
        refs.sort(key=lambda v: v.nome.lower())
        return refs


# ---------------------------------------------------------------------------
# Identificação (W3-C10) — a ponte física→digital (QR/manual → registro)
# ---------------------------------------------------------------------------
# RN-014: 30 tentativas por usuário autenticado por minuto. ``CHAVE_IDENTIFICACAO``
# é o bucket lógico do contador (a tabela é genérica — outros endpoints futuros
# usam outras chaves sem nova migration).
LIMITE_IDENTIFICACAO = 30
CHAVE_IDENTIFICACAO = "identificar"


class ProvasIdentificacaoService:
    """Caso de uso de IDENTIFICAÇÃO da prova (W3-C10) — ``resolver_prova()``.

    QR e digitação manual chegam pelo MESMO método (``identificar``) e resolvem o
    MESMO registro (idempotente quanto ao mecanismo): o QR carrega o próprio
    código (C06), então não há caminho separado. A resolução é escopada pela RLS
    de ``provas`` (claims propagados — ADR-008).

    Segurança (RN-014):
    - ANTI-ENUMERAÇÃO: código malformado, inexistente E fora do escopo retornam o
      MESMO ``ProvaNaoEncontradaError`` (404 genérico) — nada distingue os casos.
    - RATE LIMITING: 30 tentativas/ator/minuto. A tentativa é contada e PERSISTIDA
      (commit) ANTES de resolver, de modo que conte mesmo quando a resolução dá
      404 — senão o rollback do 404 zeraria o contador e furaria o limite.

    Só IDENTIFICA: validar a próxima transição é o C11 e assinar é o C12 (DP-2) —
    o C10 entrega a prova resolvida e o fluxo de confirmação pluga depois.
    """

    def __init__(
        self,
        repo: ProvasRepositoryPort,
        rate_limiter: RateLimiterPort,
        uow: UnitOfWork,
        limite: int = LIMITE_IDENTIFICACAO,
        audit: AuditLogPort | None = None,
    ) -> None:
        self._repo = repo
        self._rate_limiter = rate_limiter
        self._uow = uow
        self._limite = limite
        # W6-C20: captura "escaneou_qr" no log de auditoria após resolução bem-
        # sucedida (eventos sem prova — 404/malformado — não logam: anti-enumeração
        # + ruído). Opcional: ausente nos testes de identificação (efeito colateral).
        self._audit = audit

    async def identificar(self, codigo_bruto: str) -> ProvaListagem:
        """Resolve a prova pelo QR/código manual (RF-004/RF-005), idempotente.

        Nunca loga o código (não vaza o conteúdo escaneado — RNF-024): só o
        ``prova_id`` no sucesso e a contagem no bloqueio.
        """
        # 1. Rate limit ANTES de tudo: conta a tentativa e a PERSISTE já (o 404 da
        #    resolução não pode desfazê-la). Acima do limite → 429.
        contador = await self._rate_limiter.registrar_e_contar(CHAVE_IDENTIFICACAO)
        await self._uow.commit()
        if contador > self._limite:
            logger.warning(
                "limite de identificação excedido",
                extra={"event": "identificacao_rate_limited", "contador": contador},
            )
            raise LimiteDeTentativasError()

        # 2. Normaliza + valida o FORMATO. Malformado é tratado como "não
        #    encontrada" (MESMO 404 — não revela que nem chegou a consultar).
        codigo = normalizar_codigo(codigo_bruto)
        if not validar_codigo(codigo):
            raise ProvaNaoEncontradaError()

        # 3. Resolve pelo código (a RLS escopa): inexistente/fora do escopo → 404.
        prova = await self._repo.buscar_por_codigo(codigo)
        if prova is None:
            raise ProvaNaoEncontradaError()
        # W6-C20: registra "escaneou_qr" só no sucesso (o 404 acima não loga —
        # anti-enumeração RN-014). Append + commit próprio (a contagem do rate limit
        # já foi commitada antes; este é um evento de leitura, não uma mutação
        # atômica de domínio). Idempotente o suficiente: cada scan é um evento.
        if self._audit is not None:
            await self._audit.registrar(
                NovoEventoAuditoria(
                    evento=EventoAuditoria.ESCANEOU_QR,
                    prova_id=prova.id,
                    prova_codigo=prova.codigo,
                    prova_cliente=prova.cliente,
                    prova_requerimento=prova.requerimento,
                )
            )
            await self._uow.commit()
        nomes = await self._repo.nomes_de_vendedores([prova.vendedor_id])
        logger.info(
            "prova identificada",
            extra={"event": "prova_identificada", "prova_id": prova.id},
        )
        return ProvaListagem(prova=prova, vendedor_nome=nomes.get(prova.vendedor_id))


__all__ = [
    "CHAVE_IDENTIFICACAO",
    "LIMITE_IDENTIFICACAO",
    "MAX_TENTATIVAS_CODIGO",
    "CriarProva",
    "GeracaoDeCodigoEsgotadaError",
    "MovimentacaoComAtor",
    "PaginaProvasListagem",
    "ProvaListagem",
    "ProvasConsultaService",
    "ProvasIdentificacaoService",
    "ProvasService",
    "TimelineProva",
    "VendedorRef",
]
