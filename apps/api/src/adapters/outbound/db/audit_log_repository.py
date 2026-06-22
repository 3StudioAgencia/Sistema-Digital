"""Repositório SQLAlchemy do Log de Auditoria (W6-C20).

Uma classe que implementa as DUAS portas (escrita + leitura) sobre a MESMA
``AsyncSession`` (vinda de ``abrir_sessao_rls`` — escopo/role da RLS):

- ESCRITA (``AuditLogPort.registrar``): enriquece o evento com IP/User-Agent/origem/
  request_id do contexto da requisição (ContextVars do middleware) e delega à função
  ``private.audit_log_append`` (SECURITY DEFINER) — a ÚNICA porta de escrita (INSERT
  direto é revogado). Participa da transação corrente; NUNCA faz commit (RNF-017).
- LEITURA (``AuditoriaRepositoryPort``): listagem paginada/filtrada (sem N+1 — o nome
  do ator vem por LEFT JOIN a ``usuarios``, que o admin enxerga), atores distintos e
  a verificação do chain (``private.audit_log_verificar``). Sob a RLS
  ``audit_log_select_admin`` (3Studio-only).
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import ColumnElement, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.db.models import AuditLogRow, UsuarioRow
from src.application.ports.audit_log import AuditLogPort, AuditoriaRepositoryPort
from src.domain.auditoria import (
    AtorRef,
    EventoAuditoria,
    FiltrosAuditoria,
    NovoEventoAuditoria,
    PaginaAuditoria,
    RegistroAuditoria,
    ResultadoIntegridade,
    rotulo_origem,
)
from src.domain.provas import EstadoProva
from src.domain.state_machine.enums import Acao
from src.domain.usuarios import Setor
from src.infrastructure.logging import client_ip_var, request_id_var, user_agent_var

# Chamada da função de escrita: invoca a função UMA vez (efeito = INSERT) e ignora
# o retorno (o registro é fire-and-forget dentro da transação do chamador). CAST do
# uuid em SQL (NULL-safe) — o ``::`` logo após um bind confunde o parser do text().
_SQL_APPEND = text(
    "SELECT private.audit_log_append("
    ":evento, CAST(:prova_id AS uuid), :prova_codigo, :prova_cliente, :prova_requerimento, "
    ":acao, :estado_origem, :estado_destino, :ciclo, :motivo, :ip, :origem_user_agent, "
    ":origem_rotulo, :request_id)"
)
_SQL_VERIFICAR = text("SELECT intacto, total, quebrou_em FROM private.audit_log_verificar()")


def _escapar_like(termo: str) -> str:
    r"""Escapa curingas do LIKE — busca por texto literal (igual ao C07/C17)."""
    return termo.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def _inicio_utc(dia: date) -> datetime:
    """Meia-noite UTC do dia — limite do filtro de período (convenção UTC do C07)."""
    return datetime(dia.year, dia.month, dia.day, tzinfo=UTC)


def _para_dominio(row: AuditLogRow, ator_nome: str | None) -> RegistroAuditoria:
    return RegistroAuditoria(
        id=row.id,
        seq=row.seq,
        evento=EventoAuditoria(row.evento),
        ator_id=row.ator_id,
        ator_nome=ator_nome,
        ator_setor=Setor(row.ator_setor) if row.ator_setor is not None else None,
        prova_id=row.prova_id,
        prova_codigo=row.prova_codigo,
        prova_cliente=row.prova_cliente,
        prova_requerimento=row.prova_requerimento,
        acao=Acao(row.acao) if row.acao is not None else None,
        estado_origem=EstadoProva(row.estado_origem) if row.estado_origem is not None else None,
        estado_destino=EstadoProva(row.estado_destino) if row.estado_destino is not None else None,
        ciclo=row.ciclo,
        motivo=row.motivo,
        ip=row.ip,
        origem=row.origem_rotulo,
        created_at=row.created_at,
        hash=row.hash,
    )


class SqlAlchemyAuditLogRepository(AuditLogPort, AuditoriaRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------- escrita (captura)
    async def registrar(self, evento: NovoEventoAuditoria) -> None:
        ua = user_agent_var.get()
        await self._session.execute(
            _SQL_APPEND,
            {
                "evento": evento.evento.value,
                "prova_id": evento.prova_id,
                "prova_codigo": evento.prova_codigo,
                "prova_cliente": evento.prova_cliente,
                "prova_requerimento": evento.prova_requerimento,
                "acao": evento.acao.value if evento.acao is not None else None,
                "estado_origem": (
                    evento.estado_origem.value if evento.estado_origem is not None else None
                ),
                "estado_destino": (
                    evento.estado_destino.value if evento.estado_destino is not None else None
                ),
                "ciclo": evento.ciclo,
                "motivo": evento.motivo,
                "ip": client_ip_var.get(),
                "origem_user_agent": ua,
                "origem_rotulo": rotulo_origem(ua),
                "request_id": request_id_var.get(),
            },
        )

    # ----------------------------------------------------------------- leitura (C20)
    def _condicoes(self, filtros: FiltrosAuditoria) -> list[ColumnElement[bool]]:
        conds: list[ColumnElement[bool]] = []
        if filtros.eventos:
            conds.append(AuditLogRow.evento.in_(list(filtros.eventos)))
        if filtros.ator_id:
            conds.append(AuditLogRow.ator_id == filtros.ator_id)
        if filtros.busca:
            termo = f"%{_escapar_like(filtros.busca)}%"
            conds.append(
                or_(
                    AuditLogRow.motivo.ilike(termo, escape="\\"),
                    AuditLogRow.prova_cliente.ilike(termo, escape="\\"),
                    AuditLogRow.prova_requerimento.ilike(termo, escape="\\"),
                )
            )
        if filtros.de is not None:
            conds.append(AuditLogRow.created_at >= _inicio_utc(filtros.de))
        if filtros.ate is not None:
            conds.append(AuditLogRow.created_at < _inicio_utc(filtros.ate) + timedelta(days=1))
        return conds

    async def listar(self, filtros: FiltrosAuditoria) -> PaginaAuditoria:
        f = filtros.saneados()
        conds = self._condicoes(f)

        total = (
            await self._session.execute(
                select(func.count()).select_from(AuditLogRow).where(*conds)
            )
        ).scalar_one()

        ordem = AuditLogRow.seq.desc() if f.ordem == "recentes" else AuditLogRow.seq.asc()
        # LEFT JOIN a usuarios resolve o nome do ator numa ÚNICA consulta (sem N+1 —
        # RNF-022); o chamador é admin, então a RLS de usuarios não restringe.
        stmt = (
            select(AuditLogRow, UsuarioRow.nome)
            .outerjoin(UsuarioRow, UsuarioRow.id == AuditLogRow.ator_id)
            .where(*conds)
            .order_by(ordem)
            .offset((f.page - 1) * f.page_size)
            .limit(f.page_size)
        )
        linhas = (await self._session.execute(stmt)).all()
        items = [_para_dominio(row, nome) for row, nome in linhas]
        return PaginaAuditoria(items=items, total=int(total), page=f.page, page_size=f.page_size)

    async def atores(self) -> list[AtorRef]:
        # Atores distintos do log + nome (LEFT JOIN a usuarios — admin vê todos).
        stmt = (
            select(AuditLogRow.ator_id, UsuarioRow.nome)
            .outerjoin(UsuarioRow, UsuarioRow.id == AuditLogRow.ator_id)
            .distinct()
            .order_by(UsuarioRow.nome.asc())
        )
        linhas = (await self._session.execute(stmt)).all()
        return [AtorRef(id=ator_id, nome=nome) for ator_id, nome in linhas]

    async def verificar(self) -> ResultadoIntegridade:
        row = (await self._session.execute(_SQL_VERIFICAR)).one()
        return ResultadoIntegridade(
            intacto=bool(row.intacto),
            total=int(row.total),
            quebrou_em=int(row.quebrou_em) if row.quebrou_em is not None else None,
        )


__all__ = ["SqlAlchemyAuditLogRepository"]
