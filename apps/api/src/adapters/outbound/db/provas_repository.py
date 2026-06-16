"""Repositório SQLAlchemy de provas — implementação da porta (W2-C06).

Participa da transação do ``SqlAlchemyUnitOfWork`` (mesma ``AsyncSession``);
NUNCA faz commit — a fronteira transacional é do caso de uso (RNF-017). A
sessão vem de ``abrir_sessao_rls``: o escopo das leituras é da RLS.
"""

from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, Select, bindparam, func, select, text, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.db.models import ProvaRow
from src.application.ports.provas_repository import (
    CodigoJaExisteError,
    FiltrosProvas,
    PaginaProvas,
    ProvaJaExisteError,
    ProvasRepositoryPort,
)
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
        ciclo_atual=row.ciclo_atual,
        arte_key=row.arte_key,
        arte_content_type=row.arte_content_type,
        created_at=row.created_at,
        updated_at=row.updated_at,
        finalizada_em=row.finalizada_em,
    )


def _escapar_like(termo: str) -> str:
    r"""Escapa curingas do LIKE — busca por texto literal, nunca padrão."""
    return termo.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


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
            texto = str(exc.orig)
            # Colisão do código único: sinal de RETRY do serviço (DP-3) — o
            # cliente nunca escolhe o código, então isto não é erro de negócio.
            if "uq_provas_codigo" in texto:
                raise CodigoJaExisteError(prova.codigo) from exc
            # PK repetida = chave de idempotência já persistida (RNF-015):
            # uma requisição idêntica venceu a corrida; o serviço converge.
            # ("provas_pkey" é o nome default do PG; "pk_provas" o da convenção.)
            if "provas_pkey" in texto or "pk_provas" in texto:
                raise ProvaJaExisteError(prova.id) from exc
            raise
        # eager_defaults: created_at/updated_at/ciclo_atual vêm no RETURNING do INSERT.
        prova.created_at = row.created_at
        prova.updated_at = row.updated_at
        prova.ciclo_atual = row.ciclo_atual

    async def get(self, prova_id: str) -> Prova | None:
        row = await self._session.get(ProvaRow, prova_id)
        return _para_dominio(row) if row is not None else None

    async def obter_para_transicao(self, prova_id: str) -> Prova | None:
        # Lock pessimista (DP-2): serializa transições concorrentes da mesma prova.
        # Escopado pela RLS (sessão com claims) — fora do escopo retorna None e o
        # serviço dá o mesmo 404 do inexistente (anti-enumeração).
        stmt = select(ProvaRow).where(ProvaRow.id == prova_id).with_for_update()
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _para_dominio(row) if row is not None else None

    async def atualizar_status(
        self,
        prova_id: str,
        novo_status: EstadoProva,
        finalizada_em: datetime | None,
        quando: datetime,
    ) -> None:
        # UPDATE só das colunas da transição (status/finalizada_em/updated_at) — as
        # únicas com GRANT a authenticated (W3-C11); rota e ciclo_atual intocados.
        # A RLS de UPDATE por perfil escopa a escrita; o commit é do caso de uso.
        stmt = (
            update(ProvaRow)
            .where(ProvaRow.id == prova_id)
            .values(status=novo_status, finalizada_em=finalizada_em, updated_at=quando)
        )
        await self._session.execute(stmt)

    async def buscar_por_codigo(self, codigo: str) -> Prova | None:
        # Resolve por código único (índice ``uq_provas_codigo`` — RNF-019),
        # escopado pela RLS da sessão: fora do escopo a linha simplesmente não
        # retorna (None), e o serviço dá o mesmo 404 do inexistente
        # (anti-enumeração). O código já chega normalizado/validado do serviço.
        stmt = select(ProvaRow).where(ProvaRow.codigo == codigo)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _para_dominio(row) if row is not None else None

    async def listar(self, filtros: FiltrosProvas) -> PaginaProvas:
        condicoes = self._condicoes(filtros)
        # Contagem + página na MESMA sessão (sem N+1 — RNF-022), filtradas pela
        # RLS de provas (a sessão carrega os claims). Índices do C06 (RNF-019).
        total_stmt = select(func.count()).select_from(ProvaRow)
        page_stmt: Select[tuple[ProvaRow]] = select(ProvaRow)
        for cond in condicoes:
            total_stmt = total_stmt.where(cond)
            page_stmt = page_stmt.where(cond)
        total = (await self._session.execute(total_stmt)).scalar_one()
        page_stmt = (
            # Mais recentes primeiro (design); ``id`` desempata para ordenação
            # estável entre páginas do scroll infinito.
            page_stmt.order_by(ProvaRow.created_at.desc(), ProvaRow.id)
            .offset((filtros.page - 1) * filtros.page_size)
            .limit(filtros.page_size)
        )
        rows = (await self._session.execute(page_stmt)).scalars().all()
        return PaginaProvas(
            items=[_para_dominio(r) for r in rows],
            total=total,
            page=filtros.page,
            page_size=filtros.page_size,
        )

    async def vendedor_ids_distintos(self) -> list[str]:
        stmt = select(ProvaRow.vendedor_id).distinct()
        rows = (await self._session.execute(stmt)).scalars().all()
        return [str(r) for r in rows]

    async def nomes_de_vendedores(self, ids: list[str]) -> dict[str, str]:
        if not ids:
            return {}
        # Projeção SECURITY DEFINER (DP-7): resolve nomes fora da RLS de usuarios,
        # expondo só id+nome de vendedores (e só os do escopo do chamador). Vive no
        # schema ``private`` (não exposto pela Data API — migration 0011). Param
        # tipado como uuid[] (asyncpg).
        stmt = text("SELECT id, nome FROM private.nomes_de_vendedores(:ids)").bindparams(
            bindparam("ids", value=ids, type_=ARRAY(PgUuid(as_uuid=False)))
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(r.id): r.nome for r in rows}

    @staticmethod
    def _condicoes(filtros: FiltrosProvas) -> list[ColumnElement[bool]]:
        condicoes: list[ColumnElement[bool]] = []
        if filtros.busca:
            padrao = f"%{_escapar_like(filtros.busca)}%"
            # RF-013: busca por nome E/OU número de requerimento.
            condicoes.append(
                ProvaRow.nome.ilike(padrao, escape="\\")
                | ProvaRow.requerimento.ilike(padrao, escape="\\")
            )
        if filtros.cliente:
            padrao = f"%{_escapar_like(filtros.cliente)}%"
            condicoes.append(ProvaRow.cliente.ilike(padrao, escape="\\"))
        if filtros.status is not None:
            condicoes.append(ProvaRow.status == filtros.status)
        if filtros.rota is not None:
            condicoes.append(ProvaRow.rota == filtros.rota)
        if filtros.vendedor_id is not None:
            condicoes.append(ProvaRow.vendedor_id == filtros.vendedor_id)
        # Períodos: limites de DIA inclusivos. ``< (data + 1 dia)`` cobre o dia
        # inteiro do limite superior e mantém o uso do índice (RNF-019).
        if filtros.criada_de is not None:
            condicoes.append(ProvaRow.created_at >= filtros.criada_de)
        if filtros.criada_ate is not None:
            condicoes.append(ProvaRow.created_at < filtros.criada_ate + timedelta(days=1))
        # finalizada_em é NULL até o C11 popular: o range exclui naturalmente as
        # provas sem carimbo (NULL nas comparações).
        if filtros.finalizada_de is not None:
            condicoes.append(ProvaRow.finalizada_em >= filtros.finalizada_de)
        if filtros.finalizada_ate is not None:
            condicoes.append(ProvaRow.finalizada_em < filtros.finalizada_ate + timedelta(days=1))
        return condicoes


__all__ = ["SqlAlchemyProvasRepository"]
