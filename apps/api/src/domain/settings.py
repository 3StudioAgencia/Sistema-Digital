"""Domínio de configurações do sistema (W2-C09) — RF-022, RN-008, RN-011, US-016.

Camada interna da arquitetura hexagonal (CLAUDE.md §5.2): apenas stdlib. Modelo
chave-valor (DP-1): os DEFAULTS e a VALIDAÇÃO por chave conhecida vivem AQUI
(fonte única); a tabela ``system_settings`` guarda só as SOBRESCRITAS. A leitura
efetiva sobrepõe a sobrescrita ao default.

Fronteira de cálculo (DP-4): este módulo só ARMAZENA o tempo de atraso; quem
computa "Atrasada" em horas úteis (RN-008, janela comercial fixa seg-sex 07-18,
RNF-011) é o C16 (Dashboard). O template de etiqueta (RN-011) espelha os 5
parâmetros que o C06 expõe (``EtiquetaTemplate``) — DP-5: "personalizado"
sobrescreve esses 5 campos, "padrão" usa os defaults; nada de editor/upload
totalmente custom (fora do v1.0).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.domain.usuarios import ErroDeDominio


class ConfiguracaoInvalidaError(ErroDeDominio):
    """Valor fora do contrato da chave (ou chave desconhecida). Mapeada a 422.

    A validação dura é na ESCRITA; a leitura efetiva é tolerante (degradação
    graciosa — ``efetivar_config_etiqueta``)."""

    codigo = "configuracao_invalida"


# ---------------------------------------------------------------------------
# Chaves conhecidas (RF-022)
# ---------------------------------------------------------------------------
CHAVE_DELAY = "delay_horas_uteis"
CHAVE_ETIQUETA = "etiqueta_template"

# Tempo de atraso (RF-022a/RN-008/US-016): inteiro positivo em horas úteis.
DELAY_PADRAO = 48
DELAY_MINIMO = 1
DELAY_MAXIMO = 9999

# Template de etiqueta (RF-022b/RN-011 — DP-5).
ETIQUETA_MODO_PADRAO = "padrao"
ETIQUETA_MODO_PERSONALIZADO = "personalizado"
ETIQUETA_MODOS = (ETIQUETA_MODO_PADRAO, ETIQUETA_MODO_PERSONALIZADO)
# Fontes core do fpdf2 (sem embedding) — espelha o que o gerador do C06 aceita.
FONTES_ETIQUETA = ("helvetica", "times", "courier")


@dataclass(frozen=True)
class ConfiguracaoEtiqueta:
    """Configuração EFETIVA do template de etiqueta (DP-5).

    Espelha 1:1 os 5 parâmetros de ``EtiquetaTemplate`` (C06); um teste garante a
    sincronia dos defaults. ``modo`` decide se as sobrescritas valem
    (``personalizado``) ou se o gerador usa o template padrão (``padrao``)."""

    modo: str = ETIQUETA_MODO_PADRAO
    largura: float = 95.0
    altura: float = 55.0
    margem: float = 3.0
    fonte: str = "helvetica"
    qr_zona_quieta_modulos: int = 2

    @property
    def personalizado(self) -> bool:
        return self.modo == ETIQUETA_MODO_PERSONALIZADO


# Default da chave da etiqueta como dict (valor JSONB armazenável).
ETIQUETA_PADRAO: dict[str, Any] = {
    "modo": ConfiguracaoEtiqueta().modo,
    "largura": ConfiguracaoEtiqueta().largura,
    "altura": ConfiguracaoEtiqueta().altura,
    "margem": ConfiguracaoEtiqueta().margem,
    "fonte": ConfiguracaoEtiqueta().fonte,
    "qr_zona_quieta_modulos": ConfiguracaoEtiqueta().qr_zona_quieta_modulos,
}


# ---------------------------------------------------------------------------
# Validadores por chave (ESCRITA — estritos)
# ---------------------------------------------------------------------------
def _validar_int(valor: Any, *, minimo: int, maximo: int, nome: str) -> int:
    # bool é subclasse de int — recusa explicitamente (True/False não é quantidade).
    if isinstance(valor, bool):
        raise ConfiguracaoInvalidaError(f"{nome} deve ser um número inteiro.")
    if isinstance(valor, float):
        if not valor.is_integer():
            raise ConfiguracaoInvalidaError(f"{nome} deve ser um número inteiro.")
        valor = int(valor)
    if not isinstance(valor, int):
        raise ConfiguracaoInvalidaError(f"{nome} deve ser um número inteiro.")
    if valor < minimo or valor > maximo:
        raise ConfiguracaoInvalidaError(f"{nome} deve estar entre {minimo} e {maximo}.")
    return valor


def _validar_float(valor: Any, *, minimo: float, maximo: float, nome: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        raise ConfiguracaoInvalidaError(f"{nome} deve ser um número.")
    convertido = float(valor)
    if convertido < minimo or convertido > maximo:
        raise ConfiguracaoInvalidaError(f"{nome} deve estar entre {minimo:g} e {maximo:g}.")
    return convertido


def validar_delay(valor: Any) -> int:
    """RF-022a/RN-008: inteiro positivo em horas úteis (padrão 48)."""
    return _validar_int(
        valor, minimo=DELAY_MINIMO, maximo=DELAY_MAXIMO, nome="Tempo de atraso (horas úteis)"
    )


def validar_etiqueta(valor: Any) -> dict[str, Any]:
    """RF-022b/RN-011 (DP-5): modo + os 5 parâmetros do template do C06."""
    if not isinstance(valor, dict):
        raise ConfiguracaoInvalidaError("Configuração de etiqueta inválida.")
    modo = valor.get("modo", ETIQUETA_MODO_PADRAO)
    if modo not in ETIQUETA_MODOS:
        raise ConfiguracaoInvalidaError("Modo do template deve ser 'padrao' ou 'personalizado'.")
    fonte = valor.get("fonte", ETIQUETA_PADRAO["fonte"])
    if fonte not in FONTES_ETIQUETA:
        raise ConfiguracaoInvalidaError(f"Fonte deve ser uma de: {', '.join(FONTES_ETIQUETA)}.")
    return {
        "modo": modo,
        "largura": _validar_float(
            valor.get("largura", ETIQUETA_PADRAO["largura"]),
            minimo=40.0,
            maximo=300.0,
            nome="Largura (mm)",
        ),
        "altura": _validar_float(
            valor.get("altura", ETIQUETA_PADRAO["altura"]),
            minimo=20.0,
            maximo=300.0,
            nome="Altura (mm)",
        ),
        "margem": _validar_float(
            valor.get("margem", ETIQUETA_PADRAO["margem"]),
            minimo=0.0,
            maximo=20.0,
            nome="Margem (mm)",
        ),
        "fonte": fonte,
        "qr_zona_quieta_modulos": _validar_int(
            valor.get("qr_zona_quieta_modulos", ETIQUETA_PADRAO["qr_zona_quieta_modulos"]),
            minimo=0,
            maximo=10,
            nome="Zona quieta do QR (módulos)",
        ),
    }


# ---------------------------------------------------------------------------
# Registro de chaves conhecidas
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SettingSpec:
    """Contrato de uma chave conhecida: default + descrição + validador."""

    chave: str
    default: Any
    descricao: str
    validar: Callable[[Any], Any]


SETTINGS: dict[str, SettingSpec] = {
    CHAVE_DELAY: SettingSpec(
        chave=CHAVE_DELAY,
        default=DELAY_PADRAO,
        descricao=(
            "Uma prova digital sem movimentação por mais que esse tempo é considerada atrasada."
        ),
        validar=validar_delay,
    ),
    CHAVE_ETIQUETA: SettingSpec(
        chave=CHAVE_ETIQUETA,
        default=dict(ETIQUETA_PADRAO),
        descricao="Template da etiqueta imprimível: layout padrão ou personalizado.",
        validar=validar_etiqueta,
    ),
}


def chaves_conhecidas() -> list[str]:
    return list(SETTINGS.keys())


def validar_setting(chave: str, valor: Any) -> Any:
    """Valida ``valor`` contra o contrato de ``chave`` (chave desconhecida → 422)."""
    spec = SETTINGS.get(chave)
    if spec is None:
        raise ConfiguracaoInvalidaError(f"Configuração desconhecida: {chave}.")
    return spec.validar(valor)


def default_de(chave: str) -> Any:
    """Default da chave (cópia defensiva p/ defaults mutáveis, ex.: a etiqueta)."""
    spec = SETTINGS.get(chave)
    if spec is None:
        raise ConfiguracaoInvalidaError(f"Configuração desconhecida: {chave}.")
    return dict(spec.default) if isinstance(spec.default, dict) else spec.default


def efetivar_config_etiqueta(armazenado: Any | None) -> ConfiguracaoEtiqueta:
    """Configuração EFETIVA da etiqueta a partir do valor armazenado (ou None).

    LEITURA tolerante (degradação graciosa — uma etiqueta sempre sai): valores
    ausentes/inválidos caem no default. A validação dura é na escrita
    (``validar_etiqueta``)."""
    dados = dict(ETIQUETA_PADRAO)
    if isinstance(armazenado, dict):
        for campo in dados:
            if campo in armazenado:
                dados[campo] = armazenado[campo]
    try:
        normalizado = validar_etiqueta(dados)
    except ConfiguracaoInvalidaError:
        return ConfiguracaoEtiqueta()  # default seguro
    return ConfiguracaoEtiqueta(
        modo=normalizado["modo"],
        largura=normalizado["largura"],
        altura=normalizado["altura"],
        margem=normalizado["margem"],
        fonte=normalizado["fonte"],
        qr_zona_quieta_modulos=normalizado["qr_zona_quieta_modulos"],
    )


__all__ = [
    "CHAVE_DELAY",
    "CHAVE_ETIQUETA",
    "DELAY_MAXIMO",
    "DELAY_MINIMO",
    "DELAY_PADRAO",
    "ETIQUETA_MODOS",
    "ETIQUETA_MODO_PADRAO",
    "ETIQUETA_MODO_PERSONALIZADO",
    "ETIQUETA_PADRAO",
    "FONTES_ETIQUETA",
    "SETTINGS",
    "ConfiguracaoEtiqueta",
    "ConfiguracaoInvalidaError",
    "SettingSpec",
    "chaves_conhecidas",
    "default_de",
    "efetivar_config_etiqueta",
    "validar_delay",
    "validar_etiqueta",
    "validar_setting",
]
