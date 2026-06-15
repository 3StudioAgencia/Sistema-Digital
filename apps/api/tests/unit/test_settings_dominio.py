"""Registro de configurações do domínio (W2-C09) — validação por chave + defaults.

Roda offline (domínio puro). Cobre RF-022/RN-008/RN-011 e a fronteira da DP-5
(o template "personalizado" sobrescreve os 5 campos do C06).
"""

import pytest
from src.domain.settings import (
    CHAVE_DELAY,
    CHAVE_ETIQUETA,
    DELAY_MAXIMO,
    DELAY_PADRAO,
    ETIQUETA_PADRAO,
    ConfiguracaoEtiqueta,
    ConfiguracaoInvalidaError,
    chaves_conhecidas,
    default_de,
    efetivar_config_etiqueta,
    validar_delay,
    validar_etiqueta,
    validar_setting,
)


def test_chaves_conhecidas_sao_as_duas_da_sessao() -> None:
    assert set(chaves_conhecidas()) == {CHAVE_DELAY, CHAVE_ETIQUETA}


def test_default_do_delay_e_48() -> None:
    assert default_de(CHAVE_DELAY) == DELAY_PADRAO == 48


def test_delay_aceita_inteiro_positivo() -> None:
    assert validar_delay(72) == 72
    assert validar_delay(1) == 1
    assert validar_delay(DELAY_MAXIMO) == DELAY_MAXIMO


def test_delay_float_inteiro_e_coagido() -> None:
    assert validar_delay(48.0) == 48


@pytest.mark.parametrize("valor", [0, -1, DELAY_MAXIMO + 1])
def test_delay_fora_do_intervalo_e_rejeitado(valor: int) -> None:
    with pytest.raises(ConfiguracaoInvalidaError):
        validar_delay(valor)


@pytest.mark.parametrize("valor", [True, False, "48", 48.5, None, [], {}])
def test_delay_de_tipo_invalido_e_rejeitado(valor: object) -> None:
    # bool é subclasse de int — precisa ser recusado explicitamente.
    with pytest.raises(ConfiguracaoInvalidaError):
        validar_delay(valor)


def test_etiqueta_default_normaliza_para_o_padrao() -> None:
    normalizado = validar_etiqueta(dict(ETIQUETA_PADRAO))
    assert normalizado["modo"] == "padrao"
    assert normalizado["fonte"] == "helvetica"
    assert normalizado["largura"] == 95.0


def test_etiqueta_personalizado_valido() -> None:
    normalizado = validar_etiqueta(
        {"modo": "personalizado", "largura": 100, "altura": 60, "fonte": "times"}
    )
    assert normalizado["modo"] == "personalizado"
    assert normalizado["largura"] == 100.0  # int coagido a float
    assert normalizado["fonte"] == "times"


@pytest.mark.parametrize(
    "patch",
    [
        {"modo": "qualquer"},
        {"fonte": "comic-sans"},
        {"largura": 10.0},  # < 40 mm
        {"altura": 999.0},  # > 300 mm
        {"margem": 50.0},  # > 20 mm
        {"qr_zona_quieta_modulos": 99},
        {"qr_zona_quieta_modulos": 2.5},
    ],
)
def test_etiqueta_invalida_e_rejeitada(patch: dict[str, object]) -> None:
    valor = {**ETIQUETA_PADRAO, **patch}
    with pytest.raises(ConfiguracaoInvalidaError):
        validar_etiqueta(valor)


def test_etiqueta_nao_dict_e_rejeitada() -> None:
    with pytest.raises(ConfiguracaoInvalidaError):
        validar_etiqueta("padrao")


def test_validar_setting_chave_desconhecida_e_422() -> None:
    with pytest.raises(ConfiguracaoInvalidaError):
        validar_setting("chave_que_nao_existe", 1)


def test_default_de_retorna_copia_defensiva_do_dict() -> None:
    a = default_de(CHAVE_ETIQUETA)
    a["largura"] = -1
    b = default_de(CHAVE_ETIQUETA)
    assert b["largura"] == 95.0  # mutação não vaza para o registro


def test_efetivar_config_etiqueta_sem_armazenado_e_o_default() -> None:
    config = efetivar_config_etiqueta(None)
    assert config == ConfiguracaoEtiqueta()
    assert not config.personalizado


def test_efetivar_config_etiqueta_sobrepoe_o_armazenado() -> None:
    config = efetivar_config_etiqueta({"modo": "personalizado", "largura": 120})
    assert config.personalizado
    assert config.largura == 120.0
    assert config.altura == 55.0  # campo ausente cai no default


def test_efetivar_config_etiqueta_tolera_valor_corrompido() -> None:
    """Leitura é tolerante (degradação graciosa): lixo → default seguro."""
    assert efetivar_config_etiqueta({"largura": "abacaxi"}) == ConfiguracaoEtiqueta()
    assert efetivar_config_etiqueta("nada-disso") == ConfiguracaoEtiqueta()
