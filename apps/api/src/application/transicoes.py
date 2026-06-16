"""Caso de uso de transição de estado (W3-C11) — o motor que move a prova.

Orquestra a §6 de forma ATÔMICA (RNF-017) e IDEMPOTENTE (RNF-015/DP-2):

1. LOCK pessimista da prova (``SELECT ... FOR UPDATE``) — serializa transições
   concorrentes da MESMA prova. Fora do escopo / inexistente → 404 genérico
   (anti-enumeração — a RLS não distingue, a borda também não).
2. IDEMPOTÊNCIA: já existe movimentação com esta ``idempotency_key``? Mesma
   operação → converge (devolve a prova já no estado destino, sem reaplicar;
   200). Operação diferente sob a mesma chave → 409.
3. VALIDAÇÃO pura (``machine.avaliar_transicao``): indefinida → 422; perfil
   errado → 403; motivo obrigatório ausente → 422.
4. APLICA na MESMA transação: ``status`` (+ ``finalizada_em`` nos terminais) e
   UMA linha em ``movimentacoes`` (append-only). Commit atômico — falha no meio
   → rollback completo, prova nunca fica em estado inconsistente.

NÃO captura assinatura (C12), não desenha timeline (C13), não mexe em
``ciclo_atual`` nem oferece UI de cancelar/reiniciar (C14/C15) — apenas MODELA e
EXECUTA as transições; aquelas camadas INVOCAM este motor.
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from src.application.ports.movimentacoes_repository import (
    IdempotenciaJaRegistradaError,
    MovimentacoesRepositoryPort,
)
from src.application.ports.provas_repository import ProvasRepositoryPort
from src.application.ports.unit_of_work import UnitOfWork
from src.application.provas import ProvaListagem
from src.domain.movimentacoes import Movimentacao, TransicaoIdempotenciaConflitoError
from src.domain.provas import ProvaNaoEncontradaError
from src.domain.state_machine.enums import Acao
from src.domain.state_machine.machine import avaliar_transicao
from src.domain.state_machine.rules import ESTADOS_TERMINAIS
from src.domain.usuarios import Usuario

logger = logging.getLogger("rastreio.transicoes")


class ProvasTransicaoService:
    """Executa uma transição da máquina de estados (uma instância por requisição).

    A sessão por trás de ``repo``/``movs``/``uow`` DEVE vir de ``abrir_sessao_rls``
    (claims propagados): o escopo (Vendedor as próprias, Motorista as operacionais,
    etc.) e a escrita são da RLS — não reimplementados aqui.
    """

    def __init__(
        self,
        repo: ProvasRepositoryPort,
        movs: MovimentacoesRepositoryPort,
        uow: UnitOfWork,
        ator: Usuario,
        relogio: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repo
        self._movs = movs
        self._uow = uow
        # Ator da requisição (setor + flag administrador) — a fábrica já o carregou
        # para o gate de página; o motor o usa para a autorização FINA por ação (§6).
        self._ator = ator
        self._relogio = relogio or (lambda: datetime.now(UTC))

    async def executar(
        self,
        *,
        prova_id: str,
        acao: Acao,
        assinatura_ref: str,
        idempotency_key: str,
        motivo: str | None = None,
    ) -> ProvaListagem:
        """Move a prova conforme a §6, atômica e idempotente. Devolve a prova
        atualizada (+ nome do vendedor) para a borda renderizar o novo estado."""
        async with self._uow:
            prova = await self._repo.obter_para_transicao(prova_id)
            if prova is None:
                raise ProvaNaoEncontradaError()

            existente = await self._movs.buscar_por_idempotencia(idempotency_key)
            if existente is not None:
                # Reenvio: mesma operação converge; chave reusada para outra → 409.
                if existente.prova_id != prova_id or existente.acao is not acao:
                    raise TransicaoIdempotenciaConflitoError()
                logger.info(
                    "transição idempotente convergiu (reenvio)",
                    extra={"event": "transicao_idempotente", "prova_id": prova_id},
                )
                resultado = prova  # a prova já está no estado destino no banco
            else:
                transicao = avaliar_transicao(
                    prova.rota,
                    prova.status,
                    acao,
                    setor=self._ator.setor,
                    administrador=self._ator.administrador,
                    motivo=motivo,
                )
                quando = self._relogio()
                finalizada = quando if transicao.estado_destino in ESTADOS_TERMINAIS else None
                # status + movimentação na MESMA transação (RNF-017).
                await self._repo.atualizar_status(
                    prova_id, transicao.estado_destino, finalizada, quando
                )
                mov = Movimentacao(
                    id=str(uuid.uuid4()),
                    prova_id=prova_id,
                    estado_origem=prova.status,
                    estado_destino=transicao.estado_destino,
                    acao=acao,
                    ator_id=self._ator.id,
                    idempotency_key=idempotency_key,
                    ciclo=prova.ciclo_atual,
                    motivo=motivo.strip() if (transicao.exige_motivo and motivo) else None,
                    assinatura_ref=assinatura_ref,
                )
                try:
                    await self._movs.registrar(mov)
                except IdempotenciaJaRegistradaError as exc:
                    # Corrida que escapou do lock (chave reusada em outra prova) —
                    # converge para conflito, nunca duplica (o rollback é do __aexit__).
                    raise TransicaoIdempotenciaConflitoError() from exc
                await self._uow.commit()
                resultado = replace(
                    prova,
                    status=transicao.estado_destino,
                    finalizada_em=finalizada,
                    updated_at=quando,
                )
                logger.info(
                    "prova transicionada",
                    extra={
                        "event": "prova_transicionada",
                        "prova_id": prova_id,
                        "de": prova.status.value,
                        "para": transicao.estado_destino.value,
                        "acao": acao.value,
                        "ator_id": self._ator.id,
                    },
                )

        nomes = await self._repo.nomes_de_vendedores([resultado.vendedor_id])
        return ProvaListagem(prova=resultado, vendedor_nome=nomes.get(resultado.vendedor_id))


__all__ = ["ProvasTransicaoService"]
