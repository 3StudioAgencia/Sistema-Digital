"""Porta do limitador de tentativas — controle de abuso por ator (W3-C10).

O backend é stateless e sem Redis (R$ 0, free tier — CLAUDE.md §3): o estado do
contador vive no Postgres (migration 0014), na MESMA sessão RLS do request. A
porta abstrai a contagem por janela fixa; o caso de uso decide o limite (RN-014).
Implementação concreta em ``adapters/outbound/db/rate_limiter.py``.
"""

from abc import ABC, abstractmethod


class RateLimiterPort(ABC):
    """Contador de tentativas por ator corrente (escopo da RLS)."""

    @abstractmethod
    async def registrar_e_contar(self, chave: str) -> int:
        """Registra UMA tentativa do ator corrente sob ``chave`` na janela fixa de
        1 minuto e devolve a contagem ACUMULADA nela (já incluindo esta).

        Escrita na transação corrente — a PERSISTÊNCIA (commit) é do caso de uso,
        que a confirma ANTES de resolver para que a tentativa conte mesmo quando a
        resolução falha (ex.: 404 anti-enumeração). A linha é sempre do próprio
        ator (``app_current_user_id`` + RLS): um ator nunca incrementa o contador
        de outro.
        """


__all__ = ["RateLimiterPort"]
