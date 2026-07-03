"""Porta da FONTE da arte (servidor de arquivos do estúdio) — SOMENTE LEITURA.

Distinta da ``StoragePort`` (destino: onde a app GRAVA o snapshot da arte): esta é
a ORIGEM read-only — o servidor de arquivos do estúdio (``\\\\host\\Artes\\
STUDIO_TRANSICAO\\<fat>\\<clien>\\<req>\\VERSAO\\``), populado pelo fluxo de arte
legado. A app apenas LÊ a imagem oficial do requerimento; nunca escreve lá.

SÍNCRONA (IO de disco/SMB bloqueante) — despachada via ``asyncio.to_thread``, como a
``StoragePort``. Dois modos de falha bem separados: ``ArteFonteError`` (infra: share
fora do ar → 503) e ``ArteNaoDisponivelError`` (negócio: sem imagem utilizável → 422).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ArteFonteError(Exception):
    """Falha de INFRAESTRUTURA ao acessar o servidor de arquivos (share inacessível,
    permissão, IO). Mapeada a 503 — indisponibilidade clara, nunca 500 opaco."""


@dataclass(frozen=True)
class ArteSelecionada:
    """A imagem escolhida do requerimento: bytes + tipo detectado + nome de origem."""

    conteudo: bytes
    content_type: str
    nome_arquivo: str


class ArteFontePort(ABC):
    """Contrato de LEITURA (somente) da arte oficial do requerimento no servidor."""

    @abstractmethod
    def obter_arte(
        self,
        cod_vend_fat: int,
        cod_cliente: int,
        cod_req_art: int,
        anexo_imagem: str | None,
    ) -> ArteSelecionada:
        """Lê a imagem OFICIAL do requerimento na subpasta ``VERSAO\\``.

        Preferência: o arquivo nomeado em ``anexo_imagem`` (o que o ERP marca como a
        versão atual); fallback: a maior versão ``_V{n}`` / mais recente. Valida
        JPG/PNG por magic bytes. Levanta ``ArteNaoDisponivelError`` (domínio) se não
        houver imagem utilizável; ``ArteFonteError`` em falha de infraestrutura."""

    @abstractmethod
    def health(self) -> bool:
        """``True`` se o servidor de arquivos (base) está acessível. Nunca escreve."""


__all__ = ["ArteFonteError", "ArteFontePort", "ArteSelecionada"]
