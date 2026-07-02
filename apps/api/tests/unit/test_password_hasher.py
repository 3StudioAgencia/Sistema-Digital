"""Testes do adapter de hashing argon2id (autenticação própria). OFFLINE."""

from src.adapters.outbound.auth.argon2_hasher import Argon2PasswordHasher


def test_hash_e_verifica_senha_correta() -> None:
    hasher = Argon2PasswordHasher()
    h = hasher.hash("SenhaForte1")
    assert h != "SenhaForte1"  # nunca em claro
    assert h.startswith("$argon2id$")
    assert hasher.verificar("SenhaForte1", h) is True


def test_verifica_senha_incorreta_retorna_false() -> None:
    hasher = Argon2PasswordHasher()
    h = hasher.hash("SenhaForte1")
    assert hasher.verificar("outra-senha", h) is False


def test_hashes_diferentes_para_mesma_senha() -> None:
    # Salt aleatório: dois hashes da mesma senha diferem, mas ambos verificam.
    hasher = Argon2PasswordHasher()
    a = hasher.hash("SenhaForte1")
    b = hasher.hash("SenhaForte1")
    assert a != b
    assert hasher.verificar("SenhaForte1", a)
    assert hasher.verificar("SenhaForte1", b)


def test_hash_corrompido_nao_levanta() -> None:
    hasher = Argon2PasswordHasher()
    assert hasher.verificar("qualquer", "nao-e-um-hash-valido") is False
