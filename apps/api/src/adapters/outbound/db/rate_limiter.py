"""Limitador de tentativas em Postgres — implementação da porta (W3-C10).

Janela FIXA de 1 minuto, UMA linha por ``(user_id, chave)``: o upsert atômico
(``INSERT ... ON CONFLICT DO UPDATE``) incrementa dentro da janela vigente e
RESETA ao virar o minuto — o armazenamento fica limitado ao nº de atores, sem job
de limpeza.

O ``user_id`` vem de ``public.app_current_user_id()`` (claims propagados — ADR-008),
NUNCA de parâmetro: a RLS (``rate_limit_contadores_self``) garante que o ator só
toca a própria linha. Roda na sessão de request (``authenticated``); fora dela o
guarda *fail-closed* da sessão levanta (W1-A-001). Participa da transação corrente
— o commit é do caso de uso (RNF-017), que o confirma antes de resolver a prova.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.rate_limiter import RateLimiterPort

# Upsert atômico: insere a 1ª tentativa do minuto OU incrementa a janela vigente;
# se a linha é de um minuto anterior, RESETA para 1 (nova janela). As referências
# a ``rate_limit_contadores.*`` no DO UPDATE são os valores ANTIGOS da linha;
# ``now()`` é o início da transação (estável nas duas ocorrências). RETURNING traz
# a contagem já com esta tentativa.
_UPSERT = text(
    """
    INSERT INTO rate_limit_contadores (user_id, chave, janela_inicio, contador)
    VALUES (public.app_current_user_id(), :chave, date_trunc('minute', now()), 1)
    ON CONFLICT (user_id, chave) DO UPDATE SET
        contador = CASE
            WHEN rate_limit_contadores.janela_inicio = date_trunc('minute', now())
            THEN rate_limit_contadores.contador + 1
            ELSE 1
        END,
        janela_inicio = date_trunc('minute', now())
    RETURNING contador
    """
)


class SqlAlchemyRateLimiter(RateLimiterPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def registrar_e_contar(self, chave: str) -> int:
        result = await self._session.execute(_UPSERT, {"chave": chave})
        return int(result.scalar_one())


__all__ = ["SqlAlchemyRateLimiter"]
