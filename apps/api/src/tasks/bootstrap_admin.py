"""Bootstrap do primeiro administrador (W1-C04; auth própria na migração local).

O guard de admin exige uma linha em ``usuarios`` com ``administrador=true`` — mas
antes do primeiro admin não há como criar ninguém pela app (é o problema do ovo e
da galinha). Esta tarefa cria o admin inicial **com senha**, direto no banco:
faz o UPSERT da linha de domínio (admin ativo) E da CREDENCIAL de login
(``auth_credentials``: e-mail + hash argon2id).

Roda como OWNER (``MIGRATIONS_DATABASE_URL`` — conexão direta): o INSERT direto em
``auth_credentials`` (RLS deny-all) e em ``usuarios`` (RLS admin-only) só passa pelo
owner. NÃO usa ``private.auth_criar_credencial`` — essa função checa ``app_is_admin()``,
que falha sem claims (não há admin ainda).

Idempotente (RNF-015): repetir converge (reusa o id do e-mail existente; RESETA a
senha para a informada).

Execução (a partir de ``apps/api``):
    uv run python -m src.tasks.bootstrap_admin --
        --email admin@dominio --nome "Nome" --senha "SenhaForte1"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.adapters.outbound.auth.argon2_hasher import Argon2PasswordHasher
from src.adapters.outbound.db.models import AuthCredencialRow, UsuarioRow
from src.domain.usuarios import (
    ErroDeDominio,
    Localizacao,
    Setor,
    normalizar_email,
    validar_localizacao,
    validar_senha,
)
from src.infrastructure.config import Settings, get_settings
from src.infrastructure.database import create_direct_engine, create_session_factory
from src.infrastructure.logging import configure_logging, request_id_var

_EVENT = "bootstrap_admin"
logger = logging.getLogger("rastreio.bootstrap_admin")


async def bootstrap_admin(
    settings: Settings,
    email: str,
    nome: str,
    senha: str,
    setor: Setor = Setor.STUDIO,
    localizacao: Localizacao | None = None,
) -> str:
    """Cria/atualiza o admin inicial (domínio + credencial). Devolve o UUID."""
    validar_localizacao(setor, localizacao)
    validar_senha(senha)
    email = normalizar_email(email)
    senha_hash = Argon2PasswordHasher().hash(senha)

    engine = create_direct_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            # Idempotência: reusa o id de um usuário já existente com este e-mail
            # (senão a criação nova viola o unique de e-mail); caso contrário, novo.
            existente = (
                await session.execute(
                    text("SELECT id FROM usuarios WHERE lower(email) = lower(:e)"), {"e": email}
                )
            ).scalar()
            user_id = str(existente) if existente is not None else str(uuid.uuid4())

            usuario_stmt = pg_insert(UsuarioRow).values(
                id=user_id,
                nome=nome.strip(),
                email=email,
                setor=setor,
                localizacao=localizacao,
                administrador=True,
                ativo=True,
            )
            usuario_stmt = usuario_stmt.on_conflict_do_update(
                index_elements=[UsuarioRow.id],
                set_={
                    "nome": usuario_stmt.excluded.nome,
                    "setor": usuario_stmt.excluded.setor,
                    "localizacao": usuario_stmt.excluded.localizacao,
                    "administrador": True,
                    "ativo": True,
                },
            )
            await session.execute(usuario_stmt)

            cred_stmt = pg_insert(AuthCredencialRow).values(
                user_id=user_id, email=email, senha_hash=senha_hash
            )
            cred_stmt = cred_stmt.on_conflict_do_update(
                index_elements=[AuthCredencialRow.user_id],
                set_={"email": email, "senha_hash": cred_stmt.excluded.senha_hash},
            )
            await session.execute(cred_stmt)
            await session.commit()
        return user_id
    finally:
        await engine.dispose()


def run(settings: Settings, email: str, nome: str, senha: str) -> int:
    """Executa o bootstrap com log estruturado e exit code p/ o operador."""
    configure_logging(settings.log_level)
    correlation_id = uuid.uuid4().hex
    token = request_id_var.set(correlation_id)
    try:
        try:
            usuario_id = asyncio.run(bootstrap_admin(settings, email=email, nome=nome, senha=senha))
        except Exception as exc:
            # Tipo + mensagem segura (mensagens próprias; NUNCA a senha/credenciais).
            logger.error(
                "bootstrap de admin falhou",
                extra={
                    "event": _EVENT,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "detail": str(exc) if isinstance(exc, RuntimeError | ErroDeDominio) else None,
                },
            )
            return 1
        logger.info(
            "administrador provisionado",
            extra={"event": _EVENT, "status": "ok", "usuario_id": usuario_id},
        )
        return 0
    finally:
        request_id_var.reset(token)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provisiona o primeiro administrador")
    parser.add_argument("--email", required=True, help="e-mail de login do administrador")
    parser.add_argument("--nome", required=True, help="nome de exibição do administrador")
    parser.add_argument("--senha", required=True, help="senha inicial (mín. 8, com letra e número)")
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
    except Exception as exc:
        configure_logging("INFO")
        logger.error(
            "bootstrap falhou ao carregar configuração",
            extra={"event": _EVENT, "status": "error", "error_type": type(exc).__name__},
        )
        return 1
    return run(settings, email=args.email, nome=args.nome, senha=args.senha)


if __name__ == "__main__":
    sys.exit(main())
