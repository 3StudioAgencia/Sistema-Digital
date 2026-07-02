"""Porta de hashing de senha (autenticação própria — migração Supabase->local)."""

from abc import ABC, abstractmethod


class PasswordHasherPort(ABC):
    """Hashing e verificação de senha. O algoritmo (argon2id) vive no adapter."""

    @abstractmethod
    def hash(self, senha: str) -> str:
        """Deriva o hash (PHC string) a persistir em ``auth_credentials.senha_hash``."""

    @abstractmethod
    def verificar(self, senha: str, hash_armazenado: str) -> bool:
        """True se ``senha`` casa com o hash; False caso contrário (NUNCA levanta)."""

    @abstractmethod
    def verificar_falso(self, senha: str) -> None:
        """Verificação que SEMPRE falha, só para gastar o mesmo tempo de um verify
        real quando o e-mail não existe (anti-timing/anti-enumeração no login)."""


__all__ = ["PasswordHasherPort"]
