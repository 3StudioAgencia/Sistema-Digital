"""Repositório SQLAlchemy de provas — implementação da porta (W2-C06).

Participa da transação do ``SqlAlchemyUnitOfWork`` (mesma ``AsyncSession``);
NUNCA faz commit — a fronteira transacional é do caso de uso (RNF-017). A
sessão vem de ``abrir_sessao_rls``: o escopo das leituras é da RLS.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.db.models import ProvaRow
from src.application.ports.provas_repository import CodigoJaExisteError, ProvasRepositoryPort
from src.domain.provas import EstadoProva, Prova, Rota


def _para_dominio(row: ProvaRow) -> Prova:
    return Prova(
        id=row.id,
        codigo=row.codigo,
        nome=row.nome,
        requerimento=row.requerimento,
        cliente=row.cliente,
        vendedor_id=row.vendedor_id,
        rota=Rota(row.rota),
        status=EstadoProva(row.status),
        arte_key=row.arte_key,
        arte_content_type=row.arte_content_type,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyProvasRepository(ProvasRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, prova: Prova) -> None:
        row = ProvaRow(
            id=prova.id,
            codigo=prova.codigo,
            nome=prova.nome,
            requerimento=prova.requerimento,
            cliente=prova.cliente,
            vendedor_id=prova.vendedor_id,
            rota=prova.rota,
            status=prova.status,
            arte_key=prova.arte_key,
            arte_content_type=prova.arte_content_type,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # Colisão do código único: sinal de RETRY do serviço (DP-3) — o
            # cliente nunca escolhe o código, então isto não é erro de negócio.
            if "uq_provas_codigo" in str(exc.orig):
                raise CodigoJaExisteError(prova.codigo) from exc
            raise
        # eager_defaults: created_at/updated_at vêm no RETURNING do INSERT.
        prova.created_at = row.created_at
        prova.updated_at = row.updated_at

    async def get(self, prova_id: str) -> Prova | None:
        row = await self._session.get(ProvaRow, prova_id)
        return _para_dominio(row) if row is not None else None


__all__ = ["SqlAlchemyProvasRepository"]
