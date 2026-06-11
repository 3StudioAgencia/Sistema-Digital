"""Domínio de usuários (W1-C04): política de senha, RN-009 e enums canônicos."""

import pytest
from src.domain.usuarios import (
    Localizacao,
    LocalizacaoInvalidaError,
    SenhaFracaError,
    Setor,
    Usuario,
    normalizar_email,
    validar_localizacao,
    validar_senha,
)


# ---------------------------------------------------------------------------
# Política de senha (RF-018): min. 8, com letra e número
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("senha", ["abcdef12", "A1bcdefg", "12345678a", "x9" * 4])
def test_senha_valida(senha: str) -> None:
    validar_senha(senha)  # não levanta


@pytest.mark.parametrize(
    "senha",
    [
        "a1b2c3",  # curta (< 8)
        "12345678",  # sem letra
        "abcdefgh",  # sem número
        "",  # vazia
        "       1",  # espaços não são letras
    ],
)
def test_senha_invalida(senha: str) -> None:
    with pytest.raises(SenhaFracaError):
        validar_senha(senha)


# ---------------------------------------------------------------------------
# RN-009: localização obrigatória p/ Vendedor; indevida para os demais
# ---------------------------------------------------------------------------
def test_vendedor_exige_localizacao() -> None:
    with pytest.raises(LocalizacaoInvalidaError):
        validar_localizacao(Setor.VENDEDOR, None)


@pytest.mark.parametrize("loc", [Localizacao.MATRIZ, Localizacao.FILIAL])
def test_vendedor_com_localizacao_ok(loc: Localizacao) -> None:
    validar_localizacao(Setor.VENDEDOR, loc)


@pytest.mark.parametrize("setor", [Setor.STUDIO, Setor.MOTORISTA, Setor.CLICHERIA])
def test_nao_vendedor_nao_pode_ter_localizacao(setor: Setor) -> None:
    with pytest.raises(LocalizacaoInvalidaError):
        validar_localizacao(setor, Localizacao.MATRIZ)


@pytest.mark.parametrize("setor", [Setor.STUDIO, Setor.MOTORISTA, Setor.CLICHERIA])
def test_nao_vendedor_sem_localizacao_ok(setor: Setor) -> None:
    validar_localizacao(setor, None)


# ---------------------------------------------------------------------------
# Glossário canônico (CLAUDE.md §6): membro MAIÚSCULO, valor lowercase
# ---------------------------------------------------------------------------
def test_enums_sincronizados_com_postgres() -> None:
    assert [s.value for s in Setor] == ["studio", "vendedor", "motorista", "clicheria"]
    assert [loc.value for loc in Localizacao] == ["matriz", "filial"]


def test_normalizar_email() -> None:
    assert normalizar_email("  Mario.Souza@Estudio.COM.br ") == "mario.souza@estudio.com.br"


def test_usuario_com_devolve_copia_alterada() -> None:
    original = Usuario(id="u1", nome="Ana", email="a@b.c", setor=Setor.STUDIO)
    alterado = original.com(nome="Ana Maria", administrador=True)
    assert original.nome == "Ana"
    assert original.administrador is False
    assert alterado.nome == "Ana Maria"
    assert alterado.administrador is True
    assert alterado.id == original.id
