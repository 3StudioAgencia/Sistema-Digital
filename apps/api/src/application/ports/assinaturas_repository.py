"""Porta do repositório de assinaturas (W3-C12) — o comprovante de cada movimentação.

Append-only (RN-003/RNF-006): só ``registrar`` (INSERT) e leitura por id. NUNCA
update/delete (o trigger + a ausência de GRANT garantem no banco). A escrita
participa da transação corrente do ``UnitOfWork`` — o commit é do caso de uso
(RNF-017), JUNTO com a movimentação (nascem/falham juntas). A sessão vem de
``abrir_sessao_rls``: o escopo é da RLS (espelha ``provas``).
"""

from abc import ABC, abstractmethod

from src.domain.assinaturas import Assinatura


class AssinaturasRepositoryPort(ABC):
    """Persistência append-only das assinaturas digitais."""

    @abstractmethod
    async def registrar(self, assinatura: Assinatura) -> Assinatura:
        """Insere a assinatura na transação corrente (flush, sem commit).

        Preenche ``id``/``created_at`` a partir do RETURNING. Inserida ANTES da
        movimentação (a FK ``movimentacoes.assinatura_ref`` aponta para ela)."""

    @abstractmethod
    async def obter(self, assinatura_id: str) -> Assinatura | None:
        """Busca a assinatura por id, escopada pela RLS (espelha ``provas``).

        Alimenta o proxy de leitura da Timeline (C13). Fora do escopo → ``None``."""


__all__ = ["AssinaturasRepositoryPort"]
