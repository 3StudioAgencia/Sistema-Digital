"""Adapter de leitura do ERP legado (Firebird) — implementa ``RequerimentoReaderPort``.

SOMENTE LEITURA (regra inegociável do projeto): TODA transação é aberta em modo
``READ`` (``TraAccessMode.READ``) — o motor Firebird REJEITA qualquer escrita, que
é defesa em profundidade sobre a regra "nunca escrever no Firebird". Síncrono (o
driver é bloqueante); os handlers async o despacham via ``asyncio.to_thread``.

Uma conexão CURTA por chamada: o driver não é seguro para compartilhar uma conexão
entre as threads do threadpool, e a criação de provas (único consumidor) é de baixo
volume — abrir/fechar por lookup troca micro-latência por simplicidade e segurança.
"""

import logging
from typing import TYPE_CHECKING, Any

from firebird.driver import TPB, Isolation, TraAccessMode, connect, driver_config

from src.application.ports.requerimentos import (
    RequerimentoReaderError,
    RequerimentoReaderPort,
)
from src.domain.requerimentos import RequerimentoArte

if TYPE_CHECKING:
    from src.infrastructure.config import Settings

logger = logging.getLogger("rastreio.firebird")

# Resolve o requerimento no ERP em UMA consulta (LEFT JOIN: um vendedor/cliente
# ausente não some com o requerimento). Parametrizada (``?``) — nunca interpolada.
_SQL_BUSCAR = (
    "SELECT r.COD_REQ_ART, r.PRODART, r.COD_VENDE, v.NOMVEN, v.COD_VEND_FAT, "
    "       r.COD_CLIEN, c.CLIENTE, r.ANEXO_IMAGEM "
    "FROM TB_REQ_ARTE r "
    "LEFT JOIN TB_VENDEDOR v ON v.COD_VENDE = r.COD_VENDE "
    "LEFT JOIN TB_CLIENTES c ON c.COD_CLIEN = r.COD_CLIEN "
    "WHERE r.COD_REQ_ART = ?"
)

_SQL_HEALTH = "SELECT 1 FROM RDB$DATABASE"

# A biblioteca-cliente (fbclient.dll) é configurada UMA vez por processo (setting
# global do driver). Guardamos para não reconfigurar a cada conexão.
_client_library_configurada = False


def _texto(valor: Any) -> str | None:
    """Normaliza um campo textual do ERP: ``None`` para ausente/vazio, sem espaços."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _mapear(row: Any) -> RequerimentoArte:
    """Tupla do cursor → value object do domínio (ordem = ``_SQL_BUSCAR``)."""
    return RequerimentoArte(
        cod_req_art=int(row[0]),
        nome=_texto(row[1]),
        cod_vendedor=int(row[2]),
        nome_vendedor=_texto(row[3]),
        cod_vend_fat=None if row[4] is None else int(row[4]),
        cod_cliente=int(row[5]),
        nome_cliente=_texto(row[6]),
        anexo_imagem=_texto(row[7]),
    )


class FirebirdRequerimentoReader(RequerimentoReaderPort):
    """Leitor read-only do ERP via firebird-driver (Firebird 3+/4)."""

    def __init__(
        self,
        database: str,
        user: str,
        password: str,
        charset: str = "WIN1252",
        client_library: str | None = None,
    ) -> None:
        self._database = database
        self._user = user
        self._password = password
        self._charset = charset
        self._client_library = client_library

    @classmethod
    def from_settings(cls, settings: "Settings") -> "FirebirdRequerimentoReader":
        """Constrói a partir do ambiente (tudo-ou-nada validado no ``Settings``)."""
        if (
            settings.firebird_database is None
            or settings.firebird_user is None
            or settings.firebird_password is None
        ):
            raise RequerimentoReaderError(
                "Firebird não configurado — defina FIREBIRD_DATABASE/USER/PASSWORD."
            )
        return cls(
            database=settings.firebird_database,
            user=settings.firebird_user,
            password=settings.firebird_password.get_secret_value(),
            charset=settings.firebird_charset,
            client_library=settings.firebird_client_library,
        )

    def _conectar(self) -> Any:
        global _client_library_configurada
        if self._client_library and not _client_library_configurada:
            # Aponta a fbclient.dll do servidor instalado (setting global do driver).
            driver_config.fb_client_library.value = self._client_library
            _client_library_configurada = True
        return connect(
            self._database,
            user=self._user,
            password=self._password,
            charset=self._charset,
        )

    def _ler_um(self, con: Any, sql: str, params: tuple[object, ...]) -> Any:
        """Executa ``sql`` numa transação READ ONLY e devolve a 1ª linha (ou ``None``).

        A transação READ ONLY é o reforço da regra do projeto: mesmo que um SQL
        acidental tentasse escrever, o motor rejeitaria."""
        tpb = TPB(access_mode=TraAccessMode.READ, isolation=Isolation.SNAPSHOT)
        transacao = con.transaction_manager(tpb.get_buffer())
        transacao.begin()
        try:
            cursor = transacao.cursor()
            cursor.execute(sql, params)
            return cursor.fetchone()
        finally:
            # Read-only: o commit não persiste nada — só encerra a transação.
            transacao.commit()

    def buscar(self, cod_req_art: int) -> RequerimentoArte | None:
        try:
            con = self._conectar()
        except Exception as exc:
            raise RequerimentoReaderError("Falha ao conectar ao ERP (Firebird).") from exc
        try:
            row = self._ler_um(con, _SQL_BUSCAR, (cod_req_art,))
        except Exception as exc:
            raise RequerimentoReaderError("Falha ao ler o requerimento no ERP.") from exc
        finally:
            con.close()
        return None if row is None else _mapear(row)

    def health(self) -> bool:
        try:
            con = self._conectar()
        except Exception:
            logger.warning(
                "ERP (Firebird) inacessível no readiness",
                extra={"event": "erp_health_down", "fase": "conexao"},
            )
            return False
        try:
            self._ler_um(con, _SQL_HEALTH, ())
            return True
        except Exception:
            logger.warning(
                "ERP (Firebird) respondeu com erro no readiness",
                extra={"event": "erp_health_down", "fase": "consulta"},
            )
            return False
        finally:
            con.close()


__all__ = ["FirebirdRequerimentoReader"]
