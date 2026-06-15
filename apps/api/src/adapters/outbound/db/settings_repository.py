"""Repositório SQLAlchemy de configurações — implementação da porta (W2-C09).

Participa da transação da ``AsyncSession``; NUNCA faz commit — a fronteira é do
caso de uso (RNF-017). A sessão vem de ``abrir_sessao_rls``: a escrita é filtrada
pela RLS de ``system_settings`` (admin-only — DP-2/DP-3), a leitura é aberta a
qualquer autenticado.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.db.models import SystemSettingRow
from src.application.ports.settings_repository import (
    RegistroConfiguracao,
    SettingsRepositoryPort,
)


def _para_registro(row: SystemSettingRow) -> RegistroConfiguracao:
    return RegistroConfiguracao(
        chave=row.key,
        valor=row.value,
        atualizado_em=row.updated_at,
        atualizado_por=row.updated_by,
    )


class SqlAlchemySettingsRepository(SettingsRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def carregar(self) -> list[RegistroConfiguracao]:
        rows = (await self._session.execute(select(SystemSettingRow))).scalars().all()
        return [_para_registro(r) for r in rows]

    async def obter(self, chave: str) -> RegistroConfiguracao | None:
        row = await self._session.get(SystemSettingRow, chave)
        return _para_registro(row) if row is not None else None

    async def salvar(
        self, chave: str, valor: Any, atualizado_por: str | None
    ) -> RegistroConfiguracao:
        # Upsert idempotente (RNF-015): grava/atualiza a sobrescrita e devolve o
        # ``updated_at`` do servidor (RETURNING). Sem commit — a fronteira é da UoW.
        stmt = (
            pg_insert(SystemSettingRow)
            .values(key=chave, value=valor, updated_by=atualizado_por, updated_at=func.now())
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": valor, "updated_by": atualizado_por, "updated_at": func.now()},
            )
            .returning(SystemSettingRow.updated_at)
        )
        atualizado_em = (await self._session.execute(stmt)).scalar_one()
        return RegistroConfiguracao(
            chave=chave, valor=valor, atualizado_em=atualizado_em, atualizado_por=atualizado_por
        )


__all__ = ["SqlAlchemySettingsRepository"]
