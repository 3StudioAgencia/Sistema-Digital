"""Porta do repositorio do Dashboard (W4-C16).

Uma unica operacao: ``contadores()`` devolve TODOS os contadores do painel
(incluindo o breakdown de "Atrasadas" por vendedor + total) numa CONSULTA UNICA,
sob a RLS de ``provas`` (claims propagados) — cada perfil ve so os seus numeros
(Matriz §7). Sem N+1 (RNF-022); minimo de idas ao banco (RNF-020). Leitura pura —
nao participa de nenhuma transacao de escrita.
"""

from abc import ABC, abstractmethod

from src.domain.dashboard import ContadoresDashboard


class DashboardRepositoryPort(ABC):
    @abstractmethod
    async def contadores(self) -> ContadoresDashboard:
        """Agrega os contadores do painel numa consulta unica, escopada pela RLS.

        Le o delay (C09), computa o instante-limite de atraso (horas uteis — DP-4)
        e conta/agrega numa so ida ao banco. O breakdown de "Atrasadas" resolve os
        nomes dos vendedores pela projecao SECURITY DEFINER escopada (sem ampliar a
        Matriz §7), ordenado por contagem desc.
        """


__all__ = ["DashboardRepositoryPort"]
