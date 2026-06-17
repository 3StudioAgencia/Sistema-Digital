"""Porta do repositorio de Relatorios gerenciais (W5-C17).

Uma operacao por ABA (DP-6): cada uma agrega a aba inteira em poucas consultas
SET-BASED (sem N+1 — RNF-022), sob a RLS de ``provas``/``usuarios`` (claims
propagados). O escopo nao muda nada na pratica — Relatorios e "Exclusivo 3Studio"
(flag admin), e o admin enxerga tudo (Matriz §7) — mas a sessao RLS e mantida por
consistencia/defesa em profundidade. Leitura PURA (nao participa de escrita).

Cada metodo recebe os MESMOS ``FiltrosRelatorio`` (barra compartilhada — DP-4) e
so a aba pedida e computada (lazy — o endpoint roteia uma aba por requisicao).
"""

from abc import ABC, abstractmethod

from src.domain.relatorios import (
    FiltrosRelatorio,
    RelatorioClicheria,
    RelatorioGeral,
    RelatorioStudio,
    RelatorioVendedores,
)


class RelatoriosRepositoryPort(ABC):
    @abstractmethod
    async def geral(self, filtros: FiltrosRelatorio) -> RelatorioGeral: ...

    @abstractmethod
    async def studio(self, filtros: FiltrosRelatorio) -> RelatorioStudio: ...

    @abstractmethod
    async def vendedores(self, filtros: FiltrosRelatorio) -> RelatorioVendedores: ...

    @abstractmethod
    async def clicheria(self, filtros: FiltrosRelatorio) -> RelatorioClicheria: ...


__all__ = ["RelatoriosRepositoryPort"]
