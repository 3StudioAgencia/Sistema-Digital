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

from src.application.ports.etiqueta import EtiquetaPort
from src.application.ports.provas_repository import (
    CodigoJaExisteError,
    FiltrosProvas,
    ProvaJaExisteError,
    ProvasRepositoryPort,
)
from src.application.ports.settings_repository import SettingsRepositoryPort
from src.application.ports.storage import StorageObjectNotFound, StoragePort
from src.application.ports.unit_of_work import UnitOfWork
from src.application.ports.usuarios_repository import UsuariosRepositoryPort
from src.domain.provas import (
    EXTENSAO_POR_TIPO,
    CriacaoDivergenteError,
    Prova,
    ProvaNaoEncontradaError,
    Rota,
    gerar_codigo,
    validar_arte,
    validar_vendedor,
)
from src.domain.settings import CHAVE_ETIQUETA, ConfiguracaoEtiqueta, efetivar_config_etiqueta

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
    ) -> None:
        self._repo = repo
        self._usuarios_repo = usuarios_repo
        self._storage = storage
        self._uow = uow
        self._relogio = relogio or (lambda: datetime.now(UTC))

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
        """Remove a arte do R2 após falha no INSERT (delete idempotente). Engole
        a própria falha (com CRITICAL) para o erro ORIGINAL chegar ao chamador —
        o pior caso é um objeto órfão MARCADO em log, nunca uma prova órfã."""
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
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._etiqueta = etiqueta
        self._settings_repo = settings_repo

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


__all__ = [
    "MAX_TENTATIVAS_CODIGO",
    "CriarProva",
    "GeracaoDeCodigoEsgotadaError",
    "PaginaProvasListagem",
    "ProvaListagem",
    "ProvasConsultaService",
    "ProvasService",
    "VendedorRef",
]
