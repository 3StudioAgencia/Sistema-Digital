"""Adapter de ``ArteFontePort`` sobre o servidor de arquivos (UNC/SMB ou local).

Lê a imagem oficial do requerimento em
``<base>/<COD_VEND_FAT>/<COD_CLIEN>/<COD_REQ_ART>/VERSAO/`` (a base é o
``STUDIO_TRANSICAO``). SOMENTE LEITURA. A escolha da imagem é determinística:

1. o arquivo nomeado por ``anexo_imagem`` (o que o ERP marca como versão atual);
2. fallback: a maior versão ``_V{n}`` no nome; empate → mais recente por data.

A subpasta ``ANEXO\\`` (anexo do cliente) é IGNORADA de propósito — só a ``VERSAO\\``
tem a prova. Distingue "share fora do ar" (``ArteFonteError`` → 503) de "sem imagem
utilizável" (``ArteNaoDisponivelError`` → 422).
"""

import logging
import re
from pathlib import Path

from src.application.ports.arte_fonte import ArteFonteError, ArteFontePort, ArteSelecionada
from src.domain.provas import detectar_tipo_imagem
from src.domain.requerimentos import ArteNaoDisponivelError

logger = logging.getLogger("rastreio.arte_fonte")

_EXTENSOES = frozenset({".jpg", ".jpeg", ".png"})
_VERSAO_RE = re.compile(r"_V(\d+)", re.IGNORECASE)
_SUBPASTA_VERSAO = "VERSAO"
_MSG_INFRA = "Falha ao acessar o servidor de arquivos de artes."


def _versao_de(nome: str) -> int:
    """Número da versão a partir do sufixo ``_V{n}`` do nome (ou -1 se ausente)."""
    achado = _VERSAO_RE.search(nome)
    return int(achado.group(1)) if achado else -1


class SistemaDeArquivosArteFonte(ArteFontePort):
    """Leitor read-only da arte no servidor de arquivos do estúdio."""

    def __init__(self, base: str, tamanho_maximo_bytes: int) -> None:
        self._base = Path(base)
        self._max = tamanho_maximo_bytes

    def _pasta_versao(self, cod_vend_fat: int, cod_cliente: int, cod_req_art: int) -> Path:
        return (
            self._base
            / str(cod_vend_fat)
            / str(cod_cliente)
            / str(cod_req_art)
            / _SUBPASTA_VERSAO
        )

    def obter_arte(
        self,
        cod_vend_fat: int,
        cod_cliente: int,
        cod_req_art: int,
        anexo_imagem: str | None,
    ) -> ArteSelecionada:
        versao = self._pasta_versao(cod_vend_fat, cod_cliente, cod_req_art)
        try:
            pasta_existe = versao.is_dir()
        except OSError as exc:  # share/host inacessível
            raise ArteFonteError(_MSG_INFRA) from exc
        if not pasta_existe:
            raise ArteNaoDisponivelError()
        try:
            imagens = [
                p for p in versao.iterdir() if p.is_file() and p.suffix.lower() in _EXTENSOES
            ]
        except OSError as exc:
            raise ArteFonteError(_MSG_INFRA) from exc
        if not imagens:
            raise ArteNaoDisponivelError()
        return self._ler(self._escolher(imagens, anexo_imagem))

    def _escolher(self, imagens: list[Path], anexo_imagem: str | None) -> Path:
        if anexo_imagem:
            alvo = anexo_imagem.strip().lower()
            for p in imagens:
                if p.name.lower() == alvo:
                    return p  # a versão oficial apontada pelo ERP
        # Fallback: maior versão _V{n}; empate resolvido pela mais recente (mtime).
        def chave(p: Path) -> tuple[int, float]:
            try:
                mtime = p.stat().st_mtime
            except OSError:
                mtime = 0.0
            return (_versao_de(p.name), mtime)

        return max(imagens, key=chave)

    def _ler(self, caminho: Path) -> ArteSelecionada:
        try:
            tamanho = caminho.stat().st_size
        except OSError as exc:
            raise ArteFonteError(_MSG_INFRA) from exc
        if tamanho > self._max:
            logger.warning(
                "imagem de arte excede o teto configurado",
                extra={
                    "event": "arte_fonte_excede_teto",
                    "arquivo": caminho.name,
                    "tamanho": tamanho,
                    "teto": self._max,
                },
            )
            raise ArteNaoDisponivelError()
        try:
            dados = caminho.read_bytes()
        except OSError as exc:
            raise ArteFonteError(_MSG_INFRA) from exc
        tipo = detectar_tipo_imagem(dados)
        if tipo is None:  # extensão JPG/PNG mas conteúdo não é imagem válida
            raise ArteNaoDisponivelError()
        return ArteSelecionada(conteudo=dados, content_type=tipo, nome_arquivo=caminho.name)

    def health(self) -> bool:
        try:
            if self._base.is_dir():
                return True
        except OSError:
            pass
        logger.warning(
            "health check do servidor de arquivos de artes falhou",
            extra={"event": "arte_fonte_health_failed", "base": str(self._base)},
        )
        return False


__all__ = ["SistemaDeArquivosArteFonte"]
