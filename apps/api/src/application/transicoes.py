"""Caso de uso de transição de estado (W3-C11) + assinatura do fluxo (W3-C12).

Orquestra a §6 de forma ATÔMICA (RNF-017) e IDEMPOTENTE (RNF-015/DP-2):

1. LOCK pessimista da prova (``SELECT ... FOR UPDATE``) — serializa transições
   concorrentes da MESMA prova. Fora do escopo / inexistente → 404 genérico
   (anti-enumeração — a RLS não distingue, a borda também não).
2. IDEMPOTÊNCIA: já existe movimentação com esta ``idempotency_key``? Mesma
   operação → converge (devolve a prova já no estado destino, sem reaplicar nem
   recriar a assinatura; 200). Operação diferente sob a mesma chave → 409.
3. VALIDAÇÃO pura (``machine.avaliar_transicao``): indefinida → 422; perfil
   errado → 403; motivo obrigatório ausente → 422.
4. ASSINATURA (W3-C12/RN-003): para as ações OPERACIONAIS (identificar/aprovar/
   reprovar — ``exige_assinatura``), valida a imagem desenhada
   (``validar_assinatura``) e INSERE a linha ``assinaturas`` ANTES da movimentação
   (a FK aponta para ela). As ações ADMINISTRATIVAS (Cancelar/Reiniciar — §6.6)
   NÃO capturam traço: gravam a movimentação com ``assinatura_ref`` NULL (ADR-066).
5. APLICA na MESMA transação: ``status`` (+ ``finalizada_em`` nos terminais), a
   ``assinaturas`` (quando há) e UMA linha em ``movimentacoes`` (append-only) com
   ``assinatura_ref`` = a assinatura recém-criada (ou NULL). Commit atômico —
   falha no meio → rollback completo: assinatura e movimentação **nascem/falham
   juntas**, a prova nunca fica em estado inconsistente nem com assinatura órfã.

NÃO desenha timeline (C13). O Reinício de Ciclo (W3-C15) é a ÚNICA ação que mexe
em ``ciclo_atual``: ``executar`` o INCREMENTA na MESMA transação da mudança de
status (``incrementa_ciclo`` — DP-1), DEPOIS de carimbar a movimentação com o
ciclo que se encerra (pré-incremento — DP-3). As camadas de UI/ação (Cancelar=C14,
Reiniciar=C15) INVOCAM este motor pelos endpoints dedicados
(``POST /provas/{id}/cancelar`` e ``.../reiniciar`` — ações administrativas sem
assinatura). ``acoes_disponiveis`` reusa as regras do C11 para orientar a tela de
confirmação do C12 (DP-3), sem duplicar a §6.
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from src.application.ports.assinaturas_repository import AssinaturasRepositoryPort
from src.application.ports.audit_log import AuditLogPort
from src.application.ports.event_bus import EventBusPort
from src.application.ports.movimentacoes_repository import (
    IdempotenciaJaRegistradaError,
    MovimentacoesRepositoryPort,
)
from src.application.ports.provas_repository import ProvasRepositoryPort
from src.application.ports.unit_of_work import UnitOfWork
from src.application.provas import ProvaListagem
from src.domain.assinaturas import Assinatura, AssinaturaInvalidaError, validar_assinatura
from src.domain.auditoria import EVENTO_POR_ACAO, NovoEventoAuditoria
from src.domain.movimentacoes import Movimentacao, TransicaoIdempotenciaConflitoError
from src.domain.provas import ProvaNaoEncontradaError
from src.domain.state_machine.enums import Acao
from src.domain.state_machine.machine import (
    autoriza,
    avaliar_transicao,
    exige_assinatura,
    incrementa_ciclo,
    transicoes_de,
)
from src.domain.state_machine.rules import ESTADOS_TERMINAIS, Transicao
from src.domain.usuarios import Usuario

logger = logging.getLogger("rastreio.transicoes")

# Ações do FLUXO de escaneamento (W3-C12): a tela de confirmação só apresenta
# estas. Cancelar/Reiniciar (ações administrativas — C14/C15) também são
# transições da §6 e podem estar autorizadas a um admin, mas têm UI própria e NÃO
# aparecem na descoberta do fluxo de assinatura — senão todo admin escaneando
# qualquer prova ativa seria "o próximo ator" (Cancelar existe em todo estado).
ACOES_FLUXO_ESCANEAMENTO: frozenset[Acao] = frozenset(
    {Acao.IDENTIFICAR_E_ASSINAR, Acao.APROVAR, Acao.REPROVAR}
)


class ProvasTransicaoService:
    """Executa uma transição da máquina de estados (uma instância por requisição).

    A sessão por trás de ``repo``/``movs``/``assinaturas``/``uow`` DEVE vir de
    ``abrir_sessao_rls`` (claims propagados): o escopo (Vendedor as próprias,
    Motorista as operacionais, etc.) e a escrita são da RLS — não reimplementados
    aqui.
    """

    def __init__(
        self,
        repo: ProvasRepositoryPort,
        movs: MovimentacoesRepositoryPort,
        assinaturas: AssinaturasRepositoryPort,
        uow: UnitOfWork,
        ator: Usuario,
        relogio: Callable[[], datetime] | None = None,
        audit: AuditLogPort | None = None,
        eventos: EventBusPort | None = None,
    ) -> None:
        self._repo = repo
        self._movs = movs
        self._assinaturas = assinaturas
        self._uow = uow
        # Ator da requisição (setor + flag administrador) — a fábrica já o carregou
        # para o gate de página; o motor o usa para a autorização FINA por ação (§6).
        self._ator = ator
        self._relogio = relogio or (lambda: datetime.now(UTC))
        # W6-C20: captura do evento no log de auditoria, na MESMA transação da
        # transição (atômica — RNF-017). Opcional: ausente nos testes que só exercem
        # a máquina de estados (logar é efeito colateral, não muda a regra — §3.6).
        self._audit = audit
        # Etapa 3 (realtime): sinal genérico "prova mudou" para o SSE do dashboard,
        # na MESMA transação (só entregue no commit — atômico/idempotente). Opcional:
        # ausente nos testes que não exercem o realtime (efeito colateral — §3.6).
        self._eventos = eventos

    async def acoes_disponiveis(self, prova_id: str) -> tuple[Transicao, ...]:
        """Ações do fluxo de escaneamento que ESTE ator pode executar na prova
        agora (W3-C12/DP-3) — reusa as regras do C11 (``transicoes_de`` +
        ``autoriza``), sem duplicar a §6.

        Cancelar/Reiniciar (C14/C15) NÃO entram (têm UI própria). Tupla vazia = o
        ator não é o próximo (a UI mostra o bloqueio genérico, sem revelar quem é
        — RN-014). Prova fora do escopo / inexistente → 404 genérico
        (anti-enumeração — a RLS escopa a leitura)."""
        prova = await self._repo.get(prova_id)
        if prova is None:
            raise ProvaNaoEncontradaError()
        return tuple(
            t
            for t in transicoes_de(prova.rota, prova.status)
            if t.acao in ACOES_FLUXO_ESCANEAMENTO
            and autoriza(t.perfil_autorizado, self._ator.setor, self._ator.administrador)
        )

    async def executar(
        self,
        *,
        prova_id: str,
        acao: Acao,
        assinatura_imagem: bytes | None,
        idempotency_key: str,
        motivo: str | None = None,
    ) -> ProvaListagem:
        """Move a prova conforme a §6, atômica e idempotente. Ações operacionais
        gravam a assinatura desenhada como comprovante (RN-003); ações
        administrativas (Cancelar/Reiniciar — §6.6) passam ``assinatura_imagem``
        ``None`` e gravam a movimentação sem traço (ADR-066). O Reinício de Ciclo
        (W3-C15) ainda INCREMENTA ``ciclo_atual`` na MESMA transação (DP-1).
        Devolve a prova atualizada (+ nome do vendedor) para a borda renderizar o
        novo estado e o novo ciclo."""
        async with self._uow:
            prova = await self._repo.obter_para_transicao(prova_id)
            if prova is None:
                raise ProvaNaoEncontradaError()

            existente = await self._movs.buscar_por_idempotencia(idempotency_key)
            if existente is not None:
                # Reenvio: mesma operação converge; chave reusada para outra → 409.
                # NÃO recria a assinatura (o comprovante é o da operação original).
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
                # W3-C12 (RN-003): nas ações OPERACIONAIS, valida a imagem desenhada
                # e cria o comprovante ANTES da movimentação (a FK aponta para a
                # assinatura), tudo na MESMA transação — nascem/falham juntas
                # (RNF-017/DP-1). Ações ADMINISTRATIVAS (Cancelar/Reiniciar — §6.6)
                # não capturam traço: ``assinatura_ref`` fica NULL (ADR-066/W3-C14).
                assinatura_ref: str | None = None
                if exige_assinatura(acao):
                    if assinatura_imagem is None:  # contrato: operacional exige traço
                        raise AssinaturaInvalidaError("Assinatura obrigatória para esta ação.")
                    content_type = validar_assinatura(assinatura_imagem)
                    assinatura = await self._assinaturas.registrar(
                        Assinatura(
                            id=str(uuid.uuid4()),
                            prova_id=prova_id,
                            ator_id=self._ator.id,
                            imagem=assinatura_imagem,
                            content_type=content_type,
                        )
                    )
                    assinatura_ref = assinatura.id
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
                # W3-C15/DP-1: o Reinício de Ciclo abre um NOVO ciclo — incrementa
                # ``ciclo_atual`` na MESMA transação, DEPOIS de carimbar a
                # movimentação (acima) com ``prova.ciclo_atual`` (o ciclo que se
                # encerra — DP-3). Transição e incremento nascem/falham juntos
                # (RNF-017). Idempotente: o reenvio cai no ramo ``existente`` acima
                # e NÃO reincrementa (a prova relida já traz o ciclo novo).
                ciclo_resultante = prova.ciclo_atual
                if incrementa_ciclo(acao):
                    ciclo_resultante = await self._repo.incrementar_ciclo(prova_id)
                # W6-C20: registra o evento no log de auditoria na MESMA transação
                # (atômico — nasce/falha junto com a movimentação). Só no ramo de
                # transição NOVA: o reenvio idempotente cai no ramo ``existente`` e
                # NÃO duplica o evento. ``mov.motivo`` já vem stripado/condicional.
                if self._audit is not None:
                    await self._audit.registrar(
                        NovoEventoAuditoria(
                            evento=EVENTO_POR_ACAO[acao],
                            prova_id=prova_id,
                            prova_codigo=prova.codigo,
                            prova_cliente=prova.cliente,
                            prova_requerimento=prova.requerimento,
                            acao=acao,
                            estado_origem=prova.status,
                            estado_destino=transicao.estado_destino,
                            ciclo=prova.ciclo_atual,
                            motivo=mov.motivo,
                        )
                    )
                # Etapa 3 (realtime): sinaliza "prova mudou" na MESMA transação — o
                # pg_notify só é ENTREGUE no COMMIT (descarta em rollback), então é
                # atômico com a mudança de status e só ocorre neste ramo de transição
                # NOVA (o reenvio idempotente converge no ramo ``existente`` acima e
                # NÃO re-sinaliza — evita refetch à toa em todos os navegadores).
                if self._eventos is not None:
                    await self._eventos.publicar_mudanca_de_prova()
                await self._uow.commit()
                resultado = replace(
                    prova,
                    status=transicao.estado_destino,
                    finalizada_em=finalizada,
                    updated_at=quando,
                    ciclo_atual=ciclo_resultante,
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
                        "assinatura_id": assinatura_ref,
                        "ciclo": ciclo_resultante,
                    },
                )

        nomes = await self._repo.nomes_de_vendedores([resultado.vendedor_id])
        return ProvaListagem(prova=resultado, vendedor_nome=nomes.get(resultado.vendedor_id))


__all__ = ["ACOES_FLUXO_ESCANEAMENTO", "ProvasTransicaoService"]
