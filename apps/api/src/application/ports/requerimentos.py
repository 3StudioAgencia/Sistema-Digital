"""Porta de leitura do ERP legado (requerimentos de arte — Firebird).

SÍNCRONA pela mesma razão da ``StoragePort``: o driver concreto (firebird-driver)
é bloqueante; os handlers async despacham via ``asyncio.to_thread``, mantendo o
event loop livre sem acoplar a interface ao driver.

CONTRATO DE SOMENTE LEITURA: nenhum método escreve no ERP — regra inegociável do
projeto. O adapter concreto reforça isso abrindo transações em modo ``READ`` (o
motor Firebird rejeita qualquer escrita).
"""

from abc import ABC, abstractmethod

from src.domain.requerimentos import RequerimentoArte


class RequerimentoReaderError(Exception):
    """Falha de INFRAESTRUTURA ao ler o ERP (conexão, credencial, timeout, driver).

    Mapeada a 503 na borda (indisponibilidade clara, nunca 500 opaco) — mesma
    filosofia da ``StorageError``. Jamais decorre de escrita: o acesso é read-only."""


class RequerimentoReaderPort(ABC):
    """Contrato de LEITURA (somente) de requerimentos de arte no ERP legado."""

    @abstractmethod
    def buscar(self, cod_req_art: int) -> RequerimentoArte | None:
        """Dados do requerimento por ``COD_REQ_ART`` — ``None`` se inexistente.

        Levanta ``RequerimentoReaderError`` em falha de infraestrutura (nunca
        confunde "não existe" com "ERP fora do ar")."""

    @abstractmethod
    def health(self) -> bool:
        """``True`` se o ERP está acessível (readiness). Nunca escreve."""


__all__ = ["RequerimentoReaderError", "RequerimentoReaderPort"]
