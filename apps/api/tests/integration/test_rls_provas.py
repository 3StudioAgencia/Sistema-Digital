"""RLS de ``provas`` (W2-C06) contra Postgres real (@db) — fecha a pendência do C05.

Exercita as policies como o banco as verá em produção (``SET LOCAL ROLE
authenticated`` + ``request.jwt.claims`` — ADR-008) e valida a Matriz §7 a
nível de DADO, SEM depender da máquina de estados do C11 (as provas são
semeadas como owner já nos status alvo, inclusive os "Em Trânsito"):

- 3Studio e Clicheria veem TODAS;
- Vendedor vê APENAS as suas (``vendedor_id``), em qualquer status;
- Motorista vê APENAS as "Em Trânsito" (os três contextos "Com Motorista");
- flag admin vê todas (releitura ADR-023 — quem cria precisa enxergar);
- query direta fora do escopo retorna ZERO registros (critério §6.6);
- INSERT é exclusivo de admin; UPDATE/DELETE nem têm GRANT (C11/C14);
- o trigger torna a rota imutável MESMO para o owner (RN-007/DP-5);
- o role de runtime não-owner existe e é NOBYPASSRLS (ADR-034 item 3).
"""

import datetime as dt
import json
import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from src.domain.provas import EstadoProva, Rota, gerar_codigo
from src.domain.usuarios import Setor

pytestmark = pytest.mark.db


def _claims(sub: str, setor: str, administrador: bool) -> str:
    return json.dumps(
        {
            "sub": sub,
            "user_id": sub,
            "setor": setor,
            "administrador": administrador,
            "role": "authenticated",
            "aud": "authenticated",
        }
    )


async def _autenticar(conn: AsyncConnection, sub: str, setor: str, admin: bool) -> None:
    await conn.execute(
        text("SELECT set_config('request.jwt.claims', :c, true)"),
        {"c": _claims(sub, setor, admin)},
    )
    await conn.execute(text("SET LOCAL ROLE authenticated"))


async def _seed_usuario(
    engine: AsyncEngine, *, setor: str, administrador: bool = False, localizacao: str | None = None
) -> str:
    uid = str(uuid.uuid4())
    if setor == "vendedor" and localizacao is None:
        localizacao = "matriz"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id, 'U', :email, :setor, :loc, :adm)"
            ),
            {
                "id": uid,
                "email": f"{uid}@x.z",
                "setor": setor,
                "loc": localizacao,
                "adm": administrador,
            },
        )
    return uid


async def _seed_prova(
    engine: AsyncEngine, *, vendedor_id: str, status: str = "criada", rota: str = "matriz"
) -> str:
    """Insere uma prova como OWNER (bypass) já no status alvo — sem C11."""
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, "
                "rota, status, arte_key, arte_content_type) VALUES (:id, :codigo, 'P', '1', "
                "'C', :vendedor, :rota, :status, 'provas/x/arte.png', 'image/png')"
            ),
            {
                "id": uid,
                "codigo": gerar_codigo(dt.datetime.now(tz=dt.UTC)),
                "vendedor": vendedor_id,
                "rota": rota,
                "status": status,
            },
        )
    return uid


async def _provas_visiveis(engine: AsyncEngine, *, sub: str, setor: str, admin: bool) -> set[str]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor, admin)
            rows = (await conn.execute(text("SELECT id FROM provas"))).scalars().all()
        finally:
            await trans.rollback()
    return {str(r) for r in rows}


@pytest.fixture
async def cenario(usuarios_engine: AsyncEngine) -> dict[str, Any]:
    """Usuários de todos os perfis + provas em status que cobrem cada célula §7."""
    engine = usuarios_engine
    admin_studio = await _seed_usuario(engine, setor="studio", administrador=True)
    vendedor1 = await _seed_usuario(engine, setor="vendedor")
    vendedor2 = await _seed_usuario(engine, setor="vendedor", localizacao="filial")
    motorista = await _seed_usuario(engine, setor="motorista")
    clicheria = await _seed_usuario(engine, setor="clicheria")
    vendedor_admin = await _seed_usuario(engine, setor="vendedor", administrador=True)

    p_criada_v1 = await _seed_prova(engine, vendedor_id=vendedor1)
    p_ida_v1 = await _seed_prova(
        engine, vendedor_id=vendedor1, status="com_motorista_ida_laminacao", rota="lam_matriz"
    )
    p_volta_v2 = await _seed_prova(
        engine, vendedor_id=vendedor2, status="com_motorista_volta_laminacao", rota="lam_matriz"
    )
    p_entrega_v2 = await _seed_prova(
        engine, vendedor_id=vendedor2, status="com_motorista_entrega_final"
    )
    p_aprovada_v2 = await _seed_prova(
        engine, vendedor_id=vendedor2, status="aprovada_vendedor", rota="filial"
    )
    p_clicheria_v1 = await _seed_prova(engine, vendedor_id=vendedor1, status="recebida_clicheria")

    return {
        "engine": engine,
        "admin_studio": admin_studio,
        "vendedor1": vendedor1,
        "vendedor2": vendedor2,
        "motorista": motorista,
        "clicheria": clicheria,
        "vendedor_admin": vendedor_admin,
        "de_v1": {p_criada_v1, p_ida_v1, p_clicheria_v1},
        "de_v2": {p_volta_v2, p_entrega_v2, p_aprovada_v2},
        "em_transito": {p_ida_v1, p_volta_v2, p_entrega_v2},
        "todas": {p_criada_v1, p_ida_v1, p_volta_v2, p_entrega_v2, p_aprovada_v2, p_clicheria_v1},
    }


# ---------------------------------------------------------------------------
# SELECT por perfil (Matriz §7, células de dado)
# ---------------------------------------------------------------------------
async def test_studio_ve_todas(cenario: dict[str, Any]) -> None:
    visiveis = await _provas_visiveis(
        cenario["engine"], sub=cenario["admin_studio"], setor="studio", admin=True
    )
    assert visiveis == cenario["todas"]


async def test_clicheria_ve_todas(cenario: dict[str, Any]) -> None:
    visiveis = await _provas_visiveis(
        cenario["engine"], sub=cenario["clicheria"], setor="clicheria", admin=False
    )
    assert visiveis == cenario["todas"]


async def test_vendedor_ve_apenas_as_proprias_em_qualquer_status(cenario: dict[str, Any]) -> None:
    v1 = await _provas_visiveis(
        cenario["engine"], sub=cenario["vendedor1"], setor="vendedor", admin=False
    )
    v2 = await _provas_visiveis(
        cenario["engine"], sub=cenario["vendedor2"], setor="vendedor", admin=False
    )
    assert v1 == cenario["de_v1"]
    assert v2 == cenario["de_v2"]


async def test_motorista_ve_apenas_as_em_transito(cenario: dict[str, Any]) -> None:
    visiveis = await _provas_visiveis(
        cenario["engine"], sub=cenario["motorista"], setor="motorista", admin=False
    )
    assert visiveis == cenario["em_transito"]  # exatamente os 3 contextos "Com Motorista"


async def test_admin_de_qualquer_setor_ve_todas(cenario: dict[str, Any]) -> None:
    """Releitura ADR-023: o flag admin (mesmo setor vendedor) enxerga tudo."""
    visiveis = await _provas_visiveis(
        cenario["engine"], sub=cenario["vendedor_admin"], setor="vendedor", admin=True
    )
    assert visiveis == cenario["todas"]


async def test_query_direta_fora_do_escopo_retorna_zero(cenario: dict[str, Any]) -> None:
    """Critério §6.6: vendedor sem provas (sub fantasma) → 0 registros."""
    fantasma = str(uuid.uuid4())
    visiveis = await _provas_visiveis(
        cenario["engine"], sub=fantasma, setor="vendedor", admin=False
    )
    assert visiveis == set()


# ---------------------------------------------------------------------------
# Mutações: INSERT só admin; UPDATE/DELETE sem GRANT (C11/C14)
# ---------------------------------------------------------------------------
async def _inserir_como(cenario: dict[str, Any], *, sub: str, setor: str, admin: bool) -> None:
    engine: AsyncEngine = cenario["engine"]
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor, admin)
            await conn.execute(
                text(
                    "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, "
                    "rota, arte_key, arte_content_type) VALUES (:id, :codigo, 'P', '1', 'C', "
                    ":vendedor, 'matriz', 'provas/y/arte.png', 'image/png')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "codigo": gerar_codigo(dt.datetime.now(tz=dt.UTC)),
                    "vendedor": cenario["vendedor1"],
                },
            )
            await trans.commit()
        except BaseException:
            await trans.rollback()
            raise


async def test_admin_insere_e_nao_admin_e_bloqueado(cenario: dict[str, Any]) -> None:
    await _inserir_como(cenario, sub=cenario["admin_studio"], setor="studio", admin=True)
    for setor in ("vendedor", "motorista", "clicheria"):
        with pytest.raises(DBAPIError):  # WITH CHECK de provas_insert_admin viola
            await _inserir_como(
                cenario,
                sub=cenario[setor + ("1" if setor == "vendedor" else "")],
                setor=setor,
                admin=False,
            )


async def test_update_como_authenticated_nao_tem_grant(cenario: dict[str, Any]) -> None:
    """Privilégio mínimo (DP-6): UPDATE chega no C11 — hoje nem GRANT existe."""
    engine: AsyncEngine = cenario["engine"]
    alvo = next(iter(cenario["todas"]))
    with pytest.raises(DBAPIError, match=r"permission denied|InsufficientPrivilege"):
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                await _autenticar(conn, cenario["admin_studio"], "studio", True)
                await conn.execute(
                    text("UPDATE provas SET nome = 'X' WHERE id = :id"), {"id": alvo}
                )
            finally:
                await trans.rollback()


# ---------------------------------------------------------------------------
# Imutabilidade da rota (RN-007/DP-5) — trigger vale até para o OWNER
# ---------------------------------------------------------------------------
async def test_update_de_rota_e_rejeitado_pelo_trigger(cenario: dict[str, Any]) -> None:
    engine: AsyncEngine = cenario["engine"]
    alvo = next(iter(cenario["todas"]))
    with pytest.raises(DBAPIError, match="imutavel"):
        async with engine.begin() as conn:  # owner: RLS/grants não se aplicam
            await conn.execute(
                text("UPDATE provas SET rota = 'filial' WHERE id = :id"), {"id": alvo}
            )


async def test_update_idempotente_de_rota_e_de_outras_colunas_passa(
    cenario: dict[str, Any],
) -> None:
    engine: AsyncEngine = cenario["engine"]
    alvo = next(iter(cenario["todas"]))
    async with engine.begin() as conn:
        # rota = rota (mesmo valor): IS DISTINCT FROM deixa passar (idempotência)
        await conn.execute(text("UPDATE provas SET rota = rota WHERE id = :id"), {"id": alvo})
        # demais colunas seguem atualizáveis (o C11 fará as transições de status)
        await conn.execute(
            text("UPDATE provas SET status = 'aprovada_vendedor' WHERE id = :id"), {"id": alvo}
        )


# ---------------------------------------------------------------------------
# Sincronização de enums e role de runtime (ADR-034 item 3)
# ---------------------------------------------------------------------------
async def test_enums_do_banco_espelham_o_dominio(cenario: dict[str, Any]) -> None:
    engine: AsyncEngine = cenario["engine"]
    async with engine.connect() as conn:
        for tipo, esperado in (
            ("rota_enum", [r.value for r in Rota]),
            ("status_prova_enum", [e.value for e in EstadoProva]),
            ("setor_enum", [s.value for s in Setor]),
        ):
            rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT e.enumlabel FROM pg_enum e "
                            "JOIN pg_type t ON t.oid = e.enumtypid "
                            "WHERE t.typname = :tipo ORDER BY e.enumsortorder"
                        ),
                        {"tipo": tipo},
                    )
                )
                .scalars()
                .all()
            )
            assert list(rows) == esperado


async def test_runtime_role_existe_nobypassrls_e_membro_de_authenticated(
    cenario: dict[str, Any],
) -> None:
    engine: AsyncEngine = cenario["engine"]
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT rolcanlogin, rolinherit, rolbypassrls, rolsuper "
                    "FROM pg_roles WHERE rolname = 'rastreio_runtime'"
                )
            )
        ).one()
        assert row.rolbypassrls is False  # NUNCA bypassa a RLS
        assert row.rolsuper is False
        assert row.rolinherit is False  # só age via SET ROLE authenticated
        membro = (
            await conn.execute(
                text(
                    "SELECT 1 FROM pg_auth_members m "
                    "JOIN pg_roles r ON r.oid = m.roleid "
                    "JOIN pg_roles g ON g.oid = m.member "
                    "WHERE r.rolname = 'authenticated' AND g.rolname = 'rastreio_runtime'"
                )
            )
        ).scalar_one_or_none()
        assert membro == 1
