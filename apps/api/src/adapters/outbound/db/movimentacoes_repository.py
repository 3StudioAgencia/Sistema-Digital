"""Repositório SQLAlchemy de movimentações — log append-only (W3-C11).

Participa da transação do ``SqlAlchemyUnitOfWork`` (mesma ``AsyncSession``);
NUNCA faz commit — a fronteira é do caso de uso (RNF-017). A sessão vem de
``abrir_sessao_rls``: o escopo é da RLS (espelha ``provas``).
"""

from sqlalchemy import bindparam, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.db.models import MovimentacaoRow
from src.application.ports.movimentacoes_repository import (
    IdempotenciaJaRegistradaError,
    MovimentacoesRepositoryPort,
)
from src.domain.movimentacoes import Movimentacao
from src.domain.provas import EstadoProva
from src.domain.state_machine.enums import Acao


def _para_dominio(row: MovimentacaoRow) -> Movimentacao:
    return Movimentacao(
        id=row.id,
        prova_id=row.prova_id,
        estado_origem=EstadoProva(row.estado_origem),
        estado_destino=EstadoProva(row.estado_destino),
        acao=Acao(row.acao),
        ator_id=row.ator_id,
        idempotency_key=row.idempotency_key,
        ciclo=row.ciclo,
        motivo=row.motivo,
        assinatura_ref=row.assinatura_ref,
        created_at=row.created_at,
    )


class SqlAlchemyMovimentacoesRepository(MovimentacoesRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def registrar(self, mov: Movimentacao) -> Movimentacao:
        row = MovimentacaoRow(
            id=mov.id,
            prova_id=mov.prova_id,
            estado_origem=mov.estado_origem,
            estado_destino=mov.estado_destino,
            acao=mov.acao,
            ator_id=mov.ator_id,
            ciclo=mov.ciclo,
            motivo=mov.motivo,
            assinatura_ref=mov.assinatura_ref,
            idempotency_key=mov.idempotency_key,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # Colisão da chave de idempotência: corrida que escapou do pré-check
            # sob o lock da prova (ex.: mesma chave reusada em prova diferente).
            if "uq_movimentacoes_idempotency_key" in str(exc.orig):
                raise IdempotenciaJaRegistradaError(mov.idempotency_key) from exc
            raise
        # eager_defaults: id (se não veio) e created_at vêm no RETURNING do INSERT.
        mov.created_at = row.created_at
        return mov

    async def buscar_por_idempotencia(self, idempotency_key: str) -> Movimentacao | None:
        stmt = select(MovimentacaoRow).where(
            MovimentacaoRow.idempotency_key == idempotency_key
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _para_dominio(row) if row is not None else None

    async def listar_por_prova(self, prova_id: str) -> list[Movimentacao]:
        # Índice composto (prova_id, created_at) — RNF-019/RNF-022. ``id`` desempata
        # para ordem estável quando dois eventos colidem no mesmo instante. A RLS
        # (movimentacoes_select_por_prova_visivel) escopa: fora do escopo → vazio.
        stmt = (
            select(MovimentacaoRow)
            .where(MovimentacaoRow.prova_id == prova_id)
            .order_by(MovimentacaoRow.created_at.asc(), MovimentacaoRow.id.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_para_dominio(r) for r in rows]

    async def nomes_de_atores(self, ids: list[str]) -> dict[str, str]:
        if not ids:
            return {}
        # Projeção SECURITY DEFINER (DP-2b): resolve nomes de atores de QUALQUER
        # setor fora da RLS de usuarios, expondo só id+nome e só de atores em provas
        # visíveis ao chamador. Vive no schema ``private`` (não exposto pela Data
        # API — migration 0017). Param tipado como uuid[] (asyncpg).
        stmt = text("SELECT id, nome FROM private.nomes_de_usuarios(:ids)").bindparams(
            bindparam("ids", value=ids, type_=ARRAY(PgUuid(as_uuid=False)))
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(r.id): r.nome for r in rows}


__all__ = ["SqlAlchemyMovimentacoesRepository"]
