"""Porta do provedor de identidade — Admin API do Supabase Auth (W1-C04).

O backend NUNCA emite tokens (DAT §1.3); esta porta cobre exclusivamente a
GESTÃO de identidades (criar, banir, apagar, metadados) feita pelo administrador
via Admin API — operações que exigem a chave secreta server-only (DP-3/ADR-025).

Os casos de uso falam apenas com esta abstração; o adapter concreto
(``adapters/outbound/identity/supabase_admin.py``) detém o HTTP e a chave.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

# Marca gravada no app_metadata de todo usuário criado POR ESTA API. Permite
# distinguir órfãos de provisionamento (nossos, recuperáveis) de contas criadas
# por fora (dashboard) — que nunca tocamos (ADR-025).
MARCA_PROVISIONAMENTO = "rastreio-api"


class IdentityProviderError(Exception):
    """Falha de comunicação/operacão no provedor. Mapeada a 502 na borda HTTP."""


class IdentityProviderNaoConfigurado(IdentityProviderError):
    """Chave secreta ausente — operações de gestão indisponíveis (503)."""

    def __init__(self) -> None:
        super().__init__("Provedor de identidade não configurado (SUPABASE_SECRET_KEY ausente).")


class EmailJaExisteNoProvedorError(IdentityProviderError):
    """O e-mail já possui conta no Supabase Auth (409 ou adoção de órfão)."""


@dataclass(frozen=True)
class IdentidadeAuth:
    """Visão mínima de um usuário do Supabase Auth usada pelos casos de uso."""

    id: str
    email: str
    app_metadata: Mapping[str, object] = field(default_factory=dict)
    # Idade da conta no provedor — usada pela adoção de órfãos para NUNCA
    # tocar uma criação concorrente em andamento (revisão W1-C04).
    created_at: datetime | None = None

    @property
    def provisionado_por_nos(self) -> bool:
        return self.app_metadata.get("provisionado_por") == MARCA_PROVISIONAMENTO


class IdentityProviderPort(ABC):
    """Operações de Admin API usadas pelo CRUD de usuários.

    Todas server-side e idempotentes onde a semântica permite (RNF-015):
    ``delete_user`` e ``set_banned`` toleram repetição sem efeito colateral.
    """

    @abstractmethod
    async def create_user(self, email: str, senha: str, app_metadata: Mapping[str, object]) -> str:
        """Cria o usuário de autenticação (e-mail já confirmado) e devolve o UUID.

        Levanta ``EmailJaExisteNoProvedorError`` se o e-mail já tiver conta.
        """

    @abstractmethod
    async def delete_user(self, user_id: str) -> None:
        """Remove o usuário de autenticação (compensação de falha parcial)."""

    @abstractmethod
    async def set_banned(self, user_id: str, banned: bool) -> None:
        """Bane/desbane o usuário (bloqueia login e refresh sem apagar nada)."""

    @abstractmethod
    async def update_app_metadata(self, user_id: str, app_metadata: Mapping[str, object]) -> None:
        """Atualiza (merge) o ``app_metadata`` — claims de setor/perfil p/ o C05."""

    @abstractmethod
    async def revoke_sessions(self, user_id: str) -> None:
        """Revoga as sessões ativas (best-effort; tokens vivem até o TTL)."""

    @abstractmethod
    async def find_user_by_email(self, email: str) -> IdentidadeAuth | None:
        """Localiza um usuário de auth pelo e-mail (adoção de órfão/bootstrap)."""


__all__ = [
    "MARCA_PROVISIONAMENTO",
    "EmailJaExisteNoProvedorError",
    "IdentidadeAuth",
    "IdentityProviderError",
    "IdentityProviderNaoConfigurado",
    "IdentityProviderPort",
]
