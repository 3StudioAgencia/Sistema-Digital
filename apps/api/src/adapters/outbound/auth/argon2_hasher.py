"""Adapter de hashing de senha — argon2id (argon2-cffi).

argon2id é o padrão recomendado (vencedor da Password Hashing Competition):
resistente a GPU/ASIC e a side-channels. Os parâmetros default do argon2-cffi
(time_cost/memory_cost/parallelism) são seguros para 2024+ e ficam embutidos no
próprio hash (PHC string), então a verificação é auto-descritiva.
"""

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError, VerifyMismatchError

from src.application.ports.password_hasher import PasswordHasherPort

# Instância e hash-dummy calculados UMA vez na importação do módulo. O dummy é um
# hash argon2id válido de um valor fixo — usado por ``verificar_falso`` para
# gastar ~o mesmo tempo de um verify real quando o e-mail não existe (o valor por
# trás do hash é irrelevante; argon2 é one-way, não vaza nada).
_PH = PasswordHasher()
_DUMMY_HASH = _PH.hash("timing-parity-dummy")


class Argon2PasswordHasher(PasswordHasherPort):
    """Uma instância por processo (``PasswordHasher`` é stateless/thread-safe)."""

    def __init__(self) -> None:
        self._ph = _PH

    def hash(self, senha: str) -> str:
        return self._ph.hash(senha)

    def verificar(self, senha: str, hash_armazenado: str) -> bool:
        try:
            self._ph.verify(hash_armazenado, senha)
        except (VerifyMismatchError, InvalidHashError, Argon2Error):
            # Senha errada, hash corrompido/de outro esquema: negação limpa,
            # nunca uma exceção que vaze para o caller (fail-closed).
            return False
        return True

    def verificar_falso(self, senha: str) -> None:
        try:
            self._ph.verify(_DUMMY_HASH, senha)
        except (VerifyMismatchError, InvalidHashError, Argon2Error):
            pass


__all__ = ["Argon2PasswordHasher"]
