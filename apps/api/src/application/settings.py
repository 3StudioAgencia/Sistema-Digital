"""Casos de uso de configurações do sistema (W2-C09) — RF-022, RN-008, RN-011, US-016.

Modelo chave-valor (DP-1): os DEFAULTS e a validação por chave vivem no domínio
(``src/domain/settings.py``); a tabela guarda só SOBRESCRITAS. A leitura efetiva
sobrepõe a sobrescrita ao default.

Imediatismo (US-016): NÃO há cache (DP-4) — toda leitura vai fresca ao Postgres
(linha única indexada, RNF-020). Salvar reflete na próxima leitura por
construção, sem invalidação.

Escrita exclusiva do 3Studio (DP-3): o gate (``Recurso.CONFIGURACOES``) é da
borda (``get_settings_service``) + RLS de escrita admin-only — defesa em
profundidade. A sessão por trás de ``repo``/``uow`` DEVE vir de ``abrir_sessao_rls``.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.application.ports.settings_repository import SettingsRepositoryPort
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.settings import (
    CHAVE_ETIQUETA,
    SETTINGS,
    ConfiguracaoEtiqueta,
    default_de,
    efetivar_config_etiqueta,
    validar_setting,
)

logger = logging.getLogger("rastreio.settings")


@dataclass(frozen=True)
class Configuracao:
    """Configuração para apresentação: valor EFETIVO + default + metadados."""

    chave: str
    valor: Any
    default: Any
    descricao: str
    atualizado_em: datetime | None
    atualizado_por: str | None


class SettingsService:
    """Fachada dos casos de uso de configurações (uma instância por requisição)."""

    def __init__(self, repo: SettingsRepositoryPort, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def listar(self) -> list[Configuracao]:
        """Todas as chaves conhecidas com o valor EFETIVO (sobrescrita ou default)."""
        armazenadas = {r.chave: r for r in await self._repo.carregar()}
        configs: list[Configuracao] = []
        for chave, spec in SETTINGS.items():
            registro = armazenadas.get(chave)
            configs.append(
                Configuracao(
                    chave=chave,
                    valor=registro.valor if registro is not None else default_de(chave),
                    default=default_de(chave),
                    descricao=spec.descricao,
                    atualizado_em=registro.atualizado_em if registro is not None else None,
                    atualizado_por=registro.atualizado_por if registro is not None else None,
                )
            )
        return configs

    async def salvar(self, chave: str, valor: Any, atualizado_por: str | None) -> Configuracao:
        """Valida (422 em chave/valor inválidos) e grava (idempotente — RNF-015)."""
        normalizado = validar_setting(chave, valor)
        async with self._uow:
            registro = await self._repo.salvar(chave, normalizado, atualizado_por)
            await self._uow.commit()
        logger.info(
            "configuracao atualizada",
            extra={
                "event": "configuracao_atualizada",
                "key": chave,
                "atualizado_por": atualizado_por,
            },
        )
        spec = SETTINGS[chave]
        return Configuracao(
            chave=chave,
            valor=registro.valor,
            default=default_de(chave),
            descricao=spec.descricao,
            atualizado_em=registro.atualizado_em,
            atualizado_por=registro.atualizado_por,
        )

    async def obter_config_etiqueta(self) -> ConfiguracaoEtiqueta:
        """Configuração efetiva do template de etiqueta (consumida pelo C06)."""
        registro = await self._repo.obter(CHAVE_ETIQUETA)
        return efetivar_config_etiqueta(registro.valor if registro is not None else None)


__all__ = ["Configuracao", "SettingsService"]
