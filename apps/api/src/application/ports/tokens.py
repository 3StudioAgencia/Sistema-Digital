"""Porta do emissor de access token (JWT) — autenticação própria.

O backend agora EMITE tokens (revoga a regra "PyJWT só verifica, nunca emite",
que era premissa do Supabase Auth — ver ADR da migração). A assinatura (ES256) e
a FORMA dos claims vivem no adapter concreto.
"""

from abc import ABC, abstractmethod


class TokenIssuerPort(ABC):
    """Emite o access token assinado com o contrato de claims da RLS/gates."""

    @abstractmethod
    def emitir_access(
        self, *, sub: str, email: str | None, setor: str, administrador: bool
    ) -> str:
        """Emite o access token (JWT) do usuário identificado por ``sub``."""


__all__ = ["TokenIssuerPort"]
