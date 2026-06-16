"""Porta do repositório de movimentações — o log imutável de transições (W3-C11).

Append-only (RNF-006): só ``registrar`` (INSERT) e leituras. NUNCA update/delete
(o trigger + a ausência de GRANT garantem no banco). Escritas participam da
transação corrente do ``UnitOfWork`` — o commit é do caso de uso (RNF-017). A
sessão vem de ``abrir_sessao_rls``: o escopo é da RLS (espelha ``provas``).
"""

from abc import ABC, abstractmethod

from src.domain.movimentacoes import Movimentacao


class IdempotenciaJaRegistradaError(Exception):
    """Colisão da constraint ``uq_movimentacoes_idempotency_key`` no INSERT — a
    chave já foi persistida por uma requisição que venceu a corrida (rede de
    segurança da idempotência; o caso de uso já checa a chave sob o lock da
    prova). O serviço converge/conflita, nunca duplica (RNF-015)."""


class MovimentacoesRepositoryPort(ABC):
    """Persistência do log append-only de transições."""

    @abstractmethod
    async def registrar(self, mov: Movimentacao) -> Movimentacao:
        """Insere a movimentação na transação corrente (flush, sem commit).

        Preenche ``id``/``created_at`` a partir do RETURNING. A constraint
        ``uq_movimentacoes_idempotency_key`` é a rede de segurança da idempotência
        (RNF-015): o caso de uso já checa a chave antes (sob o lock da prova), mas
        uma colisão de corrida que escape vira ``IntegrityError``."""

    @abstractmethod
    async def buscar_por_idempotencia(self, idempotency_key: str) -> Movimentacao | None:
        """Busca a movimentação por ``idempotency_key`` (RNF-015/DP-2).

        Reenvio da MESMA transição (mesma chave) → devolve a movimentação já
        gravada, e o caso de uso converge (200 idempotente) sem reaplicar. Escopada
        pela RLS (espelha ``provas``)."""

    @abstractmethod
    async def listar_por_prova(self, prova_id: str) -> list[Movimentacao]:
        """Histórico de UMA prova em ordem cronológica (W3-C13/DP-2).

        Alimenta a Timeline: lê pelo índice ``ix_movimentacoes_prova_id_created_at``
        (sem N+1 — RNF-022), ordenado por ``created_at`` asc (``id`` desempata para
        ordem estável quando dois eventos colidem no instante). Escopada pela RLS
        (``movimentacoes_select_por_prova_visivel`` espelha ``provas``): só retorna
        algo se o ator enxerga a prova — fora do escopo → lista vazia."""

    @abstractmethod
    async def nomes_de_atores(self, ids: list[str]) -> dict[str, str]:
        """Mapa ``ator_id -> nome`` via ``private.nomes_de_usuarios`` (W3-C13/DP-2b).

        Projeção SECURITY DEFINER que resolve o nome de QUALQUER setor (não só
        Vendedor — o ator de uma movimentação pode ser 3Studio/Motorista/Clicheria),
        expondo só id+nome e só de atores em provas VISÍVEIS ao chamador. Resolve o
        "responsável" de cada etapa sem ampliar a Matriz §7 (espelha a filosofia de
        ``nomes_de_vendedores``)."""


__all__ = ["IdempotenciaJaRegistradaError", "MovimentacoesRepositoryPort"]
