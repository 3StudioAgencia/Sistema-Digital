"""TEMPORARY audit harness (Wave 3 audit — read-only, DISPOSABLE).

NOT production code, NOT part of the suite. Standalone async script that drives
the REAL endpoints against the test Postgres to produce empirical evidence for
the audit checks the existing suite does NOT cover:

- C4  concurrency: two concurrent transitions on the SAME prova do not corrupt
      state (the FOR UPDATE lock serializes; one wins, the other is rejected/
      converges coherently; exactly one movimentacao per applied transition).
- A3  terminal states (recebida_clicheria, cancelada) reject every action (422).
- G1  cancel from a terminal state is rejected (422), not silently accepted.

Run:  TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/rastreio_test \
      uv run python -m audit.run_audit
"""

import asyncio
import base64
import datetime as dt
import os
import uuid
from typing import Any

import httpx
import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from src.adapters.inbound.http.auth import JwtVerifier
from src.domain.provas import gerar_codigo
from src.infrastructure.config import Settings, coerce_asyncpg_url
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeStorage, make_client, ping_ok

HS256_SECRET = "segredo-integracao-nunca-em-producao"
ASSINATURA_PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16).decode()
URL = coerce_asyncpg_url(
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/rastreio_test")
)

_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, evidence: str) -> None:
    _results.append((name, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {evidence}")


def _token(sub: str, setor: str, admin: bool = False) -> str:
    now = dt.datetime.now(tz=dt.UTC)
    return jwt.encode(
        {
            "sub": sub, "user_id": sub, "email": "x@y.z", "setor": setor,
            "administrador": admin, "role": "authenticated", "aud": "authenticated",
            "iat": now, "exp": now + dt.timedelta(hours=1),
        },
        HS256_SECRET, algorithm="HS256",
    )


def _auth(sub: str, setor: str, admin: bool = False) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(sub, setor, admin)}"}


async def _seed_usuario(engine: Any, setor: str, admin: bool = False) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id,'U',:email,:setor,:loc,:adm)"
            ),
            {"id": uid, "email": f"{uid}@x.z", "setor": setor, "loc": loc, "adm": admin},
        )
    return uid


async def _seed_prova(engine: Any, vendedor_id: str, status: str = "criada", rota: str = "matriz") -> str:
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type) VALUES (:id,:codigo,'P','1','C',:v,:rota,"
                ":status,'provas/x/arte.png','image/png')"
            ),
            {"id": uid, "codigo": gerar_codigo(dt.datetime.now(tz=dt.UTC)), "v": vendedor_id,
             "rota": rota, "status": status},
        )
    return uid


async def _count(engine: Any, table: str, prova_id: str) -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(
            text(f"SELECT count(*) FROM {table} WHERE prova_id = :p"), {"p": prova_id})).scalar_one())


async def _status(engine: Any, prova_id: str) -> str:
    async with engine.connect() as conn:
        return str((await conn.execute(
            text("SELECT status FROM provas WHERE id = :p"), {"p": prova_id})).scalar_one())


def _body(acao: str, motivo: str | None = None, idem: str | None = None) -> dict[str, Any]:
    b: dict[str, Any] = {"acao": acao, "assinatura": ASSINATURA_PNG_B64,
                         "idempotency_key": idem or str(uuid.uuid4())}
    if motivo is not None:
        b["motivo"] = motivo
    return b


async def main() -> None:
    engine = create_async_engine(URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE movimentacoes, assinaturas, provas, usuarios, system_settings, "
            "rate_limit_contadores"))

    settings = Settings(_env_file=None, app_env="test", database_url=URL, migrations_database_url=URL)  # type: ignore[call-arg]
    client = make_client(
        settings, FakeStorage(), ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )

    vendedor = await _seed_usuario(engine, "vendedor")
    clicheria = await _seed_usuario(engine, "clicheria")
    admin = await _seed_usuario(engine, "studio", admin=True)

    async with client as c:
        # --- C4a: concurrent DISTINCT-key transitions on same prova (race) -----
        p = await _seed_prova(engine, vendedor, "criada", "matriz")
        h = _auth(vendedor, "vendedor")
        r1, r2 = await asyncio.gather(
            c.post(f"/provas/{p}/transicoes", json=_body("identificar_e_assinar"), headers=h),
            c.post(f"/provas/{p}/transicoes", json=_body("identificar_e_assinar"), headers=h),
        )
        codes = sorted([r1.status_code, r2.status_code])
        movs = await _count(engine, "movimentacoes", p)
        st = await _status(engine, p)
        check(
            "C4a concurrency (distinct keys) — exactly one applies, no corruption",
            codes == [200, 422] and movs == 1 and st == "retirada_vendedor",
            f"status_codes={codes} movimentacoes={movs} final_status={st} "
            f"(bodies: {r1.json().get('error',{}).get('code', r1.json().get('status'))!r},"
            f" {r2.json().get('error',{}).get('code', r2.json().get('status'))!r})",
        )

        # --- C4b: concurrent SAME-key double submit (idempotent under lock) -----
        p = await _seed_prova(engine, vendedor, "criada", "matriz")
        key = str(uuid.uuid4())
        r1, r2 = await asyncio.gather(
            c.post(f"/provas/{p}/transicoes", json=_body("identificar_e_assinar", idem=key), headers=h),
            c.post(f"/provas/{p}/transicoes", json=_body("identificar_e_assinar", idem=key), headers=h),
        )
        codes = sorted([r1.status_code, r2.status_code])
        movs = await _count(engine, "movimentacoes", p)
        sigs = await _count(engine, "assinaturas", p)
        check(
            "C4b concurrency (same key) — converges, exactly one movimentacao+assinatura",
            codes == [200, 200] and movs == 1 and sigs == 1,
            f"status_codes={codes} movimentacoes={movs} assinaturas={sigs} final={await _status(engine,p)}",
        )

        # --- A3: terminal states reject every action (422) ---------------------
        term_recebida = await _seed_prova(engine, vendedor, "recebida_clicheria", "matriz")
        term_cancelada = await _seed_prova(engine, vendedor, "cancelada", "matriz")
        r_ident = await c.post(f"/provas/{term_recebida}/transicoes",
                               json=_body("identificar_e_assinar"), headers=_auth(clicheria, "clicheria"))
        r_cancel_term = await c.post(f"/provas/{term_recebida}/cancelar",
                                     json={"motivo": "x", "idempotency_key": str(uuid.uuid4())},
                                     headers=_auth(admin, "studio", True))
        r_cancel_cancelada = await c.post(f"/provas/{term_cancelada}/cancelar",
                                          json={"motivo": "x", "idempotency_key": str(uuid.uuid4())},
                                          headers=_auth(admin, "studio", True))
        check(
            "A3 terminal recebida_clicheria — identificar rejected 422",
            r_ident.status_code == 422 and r_ident.json()["error"]["code"] == "transicao_invalida",
            f"code={r_ident.status_code} body={r_ident.json().get('error',{}).get('code')}",
        )
        check(
            "G1 cancel from terminal (recebida_clicheria) rejected 422 (not accepted)",
            r_cancel_term.status_code == 422,
            f"code={r_cancel_term.status_code} body={r_cancel_term.json().get('error',{}).get('code')}"
            f" status_after={await _status(engine, term_recebida)}",
        )
        check(
            "RN-005 cancel of already-cancelada rejected 422 (irreversible/terminal)",
            r_cancel_cancelada.status_code == 422,
            f"code={r_cancel_cancelada.status_code} body={r_cancel_cancelada.json().get('error',{}).get('code')}",
        )

    await engine.dispose()

    ok = sum(1 for _, k, _ in _results if k)
    print(f"\n=== AUDIT DYNAMIC RESULT: {ok}/{len(_results)} checks PASS ===")
    if ok != len(_results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
