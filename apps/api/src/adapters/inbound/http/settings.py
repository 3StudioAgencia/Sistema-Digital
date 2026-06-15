"""Endpoints de configurações do sistema (W2-C09) — RF-022, RN-008, RN-011, US-016.

Exclusivo do 3Studio (Matriz §7 — flag administrador): gate
``Recurso.CONFIGURACOES`` em ``get_settings_service`` (uma sessão RLS por
requisição) + RLS de escrita admin-only (defesa em profundidade). Prefixo real
``/settings`` (convenção do projeto: sem ``/api`` — igual a ``/provas``).

Modelo chave-valor (DP-1): ``valor`` é heterogêneo (inteiro do tempo de atraso,
objeto do template de etiqueta) — daí o tipo ``Any`` nos DTOs. A validação por
chave é do domínio (``validar_setting``) e devolve 422 em chave/valor inválidos.
"""

from datetime import datetime
from typing import Annotated, Any, Self

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.adapters.inbound.http.auth import AuthenticatedUser, get_current_user
from src.adapters.inbound.http.dependencies import get_settings_service
from src.application.settings import Configuracao, SettingsService

router = APIRouter(prefix="/settings", tags=["configuracoes"])


class ConfiguracaoOut(BaseModel):
    """Configuração: valor EFETIVO (sobrescrita ou default) + default + metadados."""

    chave: str
    valor: Any
    default: Any
    descricao: str
    atualizado_em: datetime | None
    atualizado_por: str | None

    @classmethod
    def de_dominio(cls, c: Configuracao) -> Self:
        return cls(
            chave=c.chave,
            valor=c.valor,
            default=c.default,
            descricao=c.descricao,
            atualizado_em=c.atualizado_em,
            atualizado_por=c.atualizado_por,
        )


class AtualizarConfiguracaoIn(BaseModel):
    """Corpo do PUT: o novo valor da chave (validado por chave no domínio)."""

    valor: Any


@router.get("", response_model=list[ConfiguracaoOut])
async def listar(
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> list[ConfiguracaoOut]:
    """Lista as configurações conhecidas (valor efetivo + default). 3Studio-only."""
    return [ConfiguracaoOut.de_dominio(c) for c in await service.listar()]


@router.put("/{chave}", response_model=ConfiguracaoOut)
async def salvar(
    chave: str,
    body: AtualizarConfiguracaoIn,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ConfiguracaoOut:
    """Salva uma configuração (validação por chave; 3Studio-only).

    Idempotente (PUT — RNF-015): mesmo valor → mesmo resultado. Imediato (US-016):
    sem cache (DP-4), a próxima leitura — inclusive o consumo server-side da
    etiqueta (C06) e do dashboard (C16) — reflete o novo valor."""
    return ConfiguracaoOut.de_dominio(await service.salvar(chave, body.valor, user.sub))


__all__ = ["router"]
