"""Bootstrap do primeiro administrador (W1-C04).

O guard de admin exige uma linha em ``usuarios`` com ``administrador=true`` —
mas a PRIMEIRA conta (criada no dashboard do Supabase para o C03) não tem linha
de domínio. Esta tarefa fecha o ciclo: localiza o usuário de AUTH pelo e-mail
(Admin API) e faz o UPSERT da linha de domínio como administrador ativo,
sincronizando também o ``app_metadata`` (claims do C05).

Idempotente (RNF-015): repetir converge para o mesmo estado. NÃO cria conta de
auth nem define senha — a conta precisa existir (dashboard); criação com senha
é papel do fluxo normal de cadastro (endpoint POST /usuarios).

Execução (a partir de ``apps/api``, exige SUPABASE_URL + SUPABASE_SECRET_KEY):
    uv run python -m src.tasks.bootstrap_admin -- --email admin@dominio --nome "Nome"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.adapters.outbound.db.models import UsuarioRow
from src.adapters.outbound.identity.supabase_admin import SupabaseAdminIdentityProvider
from src.application.usuarios import montar_app_metadata
from src.domain.usuarios import Localizacao, Setor, validar_localizacao
from src.infrastructure.config import Settings, get_settings
from src.infrastructure.database import create_direct_engine, create_session_factory
from src.infrastructure.logging import configure_logging, request_id_var

_EVENT = "bootstrap_admin"
logger = logging.getLogger("rastreio.bootstrap_admin")


async def bootstrap_admin(
    settings: Settings,
    email: str,
    nome: str,
    setor: Setor = Setor.STUDIO,
    localizacao: Localizacao | None = None,
) -> str:
    """Localiza o auth user e faz o upsert da linha de domínio como admin ativo.

    Devolve o UUID provisionado; LEVANTA com mensagem clara quando a conta de
    auth não existe ou a chave secreta não está configurada.
    """
    validar_localizacao(setor, localizacao)
    if settings.supabase_url is None or settings.supabase_secret_key is None:
        msg = "SUPABASE_URL e SUPABASE_SECRET_KEY são obrigatórias para o bootstrap"
        raise RuntimeError(msg)

    identity = SupabaseAdminIdentityProvider(
        supabase_url=settings.supabase_url,
        secret_key=settings.supabase_secret_key.get_secret_value(),
    )
    engine = create_direct_engine(settings)
    try:
        identidade = await identity.find_user_by_email(email)
        if identidade is None:
            msg = (
                "conta de auth não encontrada para este e-mail — crie o usuário no "
                "dashboard do Supabase (Authentication → Users) antes do bootstrap"
            )
            raise RuntimeError(msg)

        # ORDEM IMPORTA (revisão W1-C04): a linha de domínio nasce ANTES de a
        # conta receber a marca de provisionamento no app_metadata. Se a marca
        # viesse primeiro e o INSERT falhasse, a conta do primeiro admin viraria
        # candidata à adoção de órfão (delete) numa criação concorrente.
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            stmt = pg_insert(UsuarioRow).values(
                id=identidade.id,
                nome=nome.strip(),
                email=identidade.email,
                setor=setor,
                localizacao=localizacao,
                administrador=True,
                ativo=True,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[UsuarioRow.id],
                set_={
                    "nome": stmt.excluded.nome,
                    "setor": stmt.excluded.setor,
                    "localizacao": stmt.excluded.localizacao,
                    "administrador": True,
                    "ativo": True,
                },
            )
            await session.execute(stmt)
            await session.commit()

        await identity.update_app_metadata(
            identidade.id, montar_app_metadata(setor, administrador=True)
        )
        # O bootstrap deixa o admin UTILIZÁVEL: se a conta estava banida (ex.:
        # desativada no passado), desfaz o ban — coerente com ativo=true.
        await identity.set_banned(identidade.id, banned=False)
        return identidade.id
    finally:
        await identity.aclose()
        await engine.dispose()


def run(settings: Settings, email: str, nome: str) -> int:
    """Executa o bootstrap com log estruturado e exit code p/ o operador."""
    configure_logging(settings.log_level)
    correlation_id = uuid.uuid4().hex
    token = request_id_var.set(correlation_id)
    try:
        try:
            usuario_id = asyncio.run(bootstrap_admin(settings, email=email, nome=nome))
        except Exception as exc:
            # Tipo + mensagem segura (mensagens próprias; nunca credenciais).
            logger.error(
                "bootstrap de admin falhou",
                extra={
                    "event": _EVENT,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "detail": str(exc) if isinstance(exc, RuntimeError) else None,
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
    parser.add_argument("--email", required=True, help="e-mail da conta JÁ criada no Supabase")
    parser.add_argument("--nome", required=True, help="nome de exibição do administrador")
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
    return run(settings, email=args.email, nome=args.nome)


if __name__ == "__main__":
    sys.exit(main())
