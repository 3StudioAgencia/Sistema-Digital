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

Idempotência (RNF-015): o retry de uma criação que FALHOU converge (nada foi
persistido); a proteção contra duplo submit é da UI (botão desabilitado) — cada
POST bem-sucedido cria deliberadamente uma nova prova com código novo.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.ports.etiqueta import EtiquetaPort
from src.application.ports.provas_repository import CodigoJaExisteError, ProvasRepositoryPort
from src.application.ports.storage import StoragePort
from src.application.ports.unit_of_work import UnitOfWork
from src.application.ports.usuarios_repository import UsuariosRepositoryPort
from src.domain.provas import (
    EXTENSAO_POR_TIPO,
    Prova,
    ProvaNaoEncontradaError,
    Rota,
    gerar_codigo,
    validar_arte,
    validar_vendedor,
)

logger = logging.getLogger("rastreio.provas")

# Tentativas de geração do código em colisão (DP-3). Com 31^6 ≈ 887 milhões de
# combinações por mês, esgotar 5 tentativas indica problema sistêmico (relógio,
# RNG) — vira erro interno alto, não silêncio.
MAX_TENTATIVAS_CODIGO = 5


class GeracaoDeCodigoEsgotadaError(Exception):
    """Colisões consecutivas além do plausível — erro INTERNO (500), nunca 422."""


@dataclass(frozen=True)
class CriarProva:
    """Comando de criação — payload já validado em FORMA pela borda HTTP."""

    nome: str
    requerimento: str
    cliente: str
    vendedor_id: str
    rota: Rota


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
        etiqueta: EtiquetaPort,
        uow: UnitOfWork,
        relogio: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repo
        self._usuarios_repo = usuarios_repo
        self._storage = storage
        self._etiqueta = etiqueta
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

        # Libera a conexão da leitura antes do IO externo (idle-in-transaction).
        await self._uow.rollback()

        prova_id = str(uuid.uuid4())
        arte_key = f"provas/{prova_id}/arte{EXTENSAO_POR_TIPO[tipo]}"
        # Porta síncrona (boto3) fora do event loop — mesmo padrão do readiness.
        await asyncio.to_thread(self._storage.upload, arte_key, arte, tipo)

        try:
            prova = await self._inserir_com_retry(cmd, prova_id, arte_key, tipo)
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

    # ---------------------------------------------------------------- etiqueta
    async def gerar_etiqueta(self, prova_id: str) -> tuple[bytes, str]:
        """Etiqueta PDF sob demanda (DP-7) — stateless, nada é armazenado.

        Devolve ``(pdf, codigo)``; o código nomeia o arquivo no download.
        Prova fora do escopo da RLS e prova inexistente são o MESMO 404
        (anti-enumeração — CLAUDE.md §11).
        """
        prova = await self._repo.get(prova_id)
        if prova is None:
            raise ProvaNaoEncontradaError()
        vendedor = await self._usuarios_repo.get(prova.vendedor_id)
        vendedor_nome = vendedor.nome if vendedor is not None else "—"
        pdf = await asyncio.to_thread(self._etiqueta.gerar_pdf, prova, vendedor_nome)
        return pdf, prova.codigo


__all__ = [
    "MAX_TENTATIVAS_CODIGO",
    "CriarProva",
    "GeracaoDeCodigoEsgotadaError",
    "ProvasService",
]
