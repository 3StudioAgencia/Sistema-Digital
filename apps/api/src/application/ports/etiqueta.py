"""Porta de geração da etiqueta imprimível (RF-003/RN-011 — W2-C06).

Síncrona pela mesma razão da ``StoragePort``: a renderização é CPU-bound e o
caso de uso a despacha para thread (``asyncio.to_thread``), mantendo o event
loop livre sem acoplar a interface à lib concreta (fpdf2 no adapter).
"""

from abc import ABC, abstractmethod

from src.domain.provas import Prova
from src.domain.settings import ConfiguracaoEtiqueta


class EtiquetaPort(ABC):
    """Gera a etiqueta PDF padronizada da prova (template padrão — DP-1/DP-2)."""

    @abstractmethod
    def gerar_pdf(
        self, prova: Prova, vendedor_nome: str, config: ConfiguracaoEtiqueta | None = None
    ) -> bytes:
        """PDF no tamanho físico exato (95 x 55 mm) com os campos do RF-003:
        nome, requerimento, vendedor, rota, QR Code e o código em destaque.

        ``config`` (W2-C09 — RN-011): quando ``personalizado``, sobrescreve os
        parâmetros do template; ``None``/``padrao`` usa o template padrão."""


__all__ = ["EtiquetaPort"]
