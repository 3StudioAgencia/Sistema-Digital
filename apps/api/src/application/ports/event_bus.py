"""Porta de publicação de eventos do realtime (etapa 3 da migração Supabase->local).

No molde de ``AuditLogPort``: um efeito colateral ATÔMICO plugado nos casos de uso
que mudam o estado de uma prova (criação C06, transição C11, cancelamento C14,
reinício C15). A implementação (``PgNotifyEventBus``) emite um ``NOTIFY`` do
Postgres na MESMA transação do caso de uso — o Postgres só ENTREGA a notificação
no COMMIT (descarta em rollback), então:

- é ATÔMICO com a mutação de domínio (RNF-017): rollback não vaza evento;
- é IDEMPOTENTE (RNF-015): o chamador só publica no ramo que DE FATO muda o estado
  (transição nova / criação) — nunca num reenvio que converge, senão dispararia um
  refetch desnecessário em todos os navegadores conectados (thundering herd).

Mão única e payload GENÉRICO (o navegador rebusca a agregação escopada pela RLS):
ver ``domain/eventos.py``.
"""

from abc import ABC, abstractmethod


class EventBusPort(ABC):
    """Publica o sinal genérico "uma prova mudou".

    É a única operação necessária para o realtime do dashboard: o evento não
    carrega dado — o navegador rebusca ``GET /dashboard`` (escopado pela RLS)."""

    @abstractmethod
    async def publicar_mudanca_de_prova(self) -> None:
        """Emite o sinal na transação corrente do chamador (sem commit próprio).

        Só deve ser chamado no ramo que de fato muda o estado (criação, transição
        nova). O commit é do caso de uso; o Postgres entrega a notificação apenas
        se o commit ocorrer."""


__all__ = ["EventBusPort"]
