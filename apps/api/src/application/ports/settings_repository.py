"""Porta do repositório de configurações do sistema (W2-C09).

Persiste apenas as SOBRESCRITAS das chaves conhecidas (os defaults e a validação
vivem no domínio — ``src/domain/settings.py``). A sessão por trás DEVE vir de
``abrir_sessao_rls``: a escrita é 3Studio-only pela RLS (defesa em profundidade).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RegistroConfiguracao:
    """Linha persistida de configuração (sobrescrita de uma chave conhecida)."""

    chave: str
    valor: Any
    atualizado_em: datetime
    atualizado_por: str | None


class SettingsRepositoryPort(ABC):
    """Persistência das sobrescritas de configuração."""

    @abstractmethod
    async def carregar(self) -> list[RegistroConfiguracao]:
        """Todas as sobrescritas persistidas (tabela pequena — uma leitura)."""

    @abstractmethod
    async def obter(self, chave: str) -> RegistroConfiguracao | None:
        """Sobrescrita de UMA chave, ou ``None`` quando não há (usa-se o default)."""

    @abstractmethod
    async def salvar(
        self, chave: str, valor: Any, atualizado_por: str | None
    ) -> RegistroConfiguracao:
        """Upsert idempotente (RNF-015) do valor JÁ validado; devolve a linha gravada."""


__all__ = ["RegistroConfiguracao", "SettingsRepositoryPort"]
