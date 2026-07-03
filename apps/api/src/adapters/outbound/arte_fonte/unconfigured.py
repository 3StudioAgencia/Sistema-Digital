"""Stand-in da fonte de arte quando o servidor de arquivos não está configurado.

Mesma filosofia do ``UnconfiguredStorage``/``UnconfiguredRequerimentoReader``: a app
sobe sem o share (dev/CI/offline); o readiness reporta a fonte "down" e qualquer
leitura real levanta ``ArteFonteError`` (503), com mensagem acionável.
"""

from src.application.ports.arte_fonte import ArteFonteError, ArteFontePort, ArteSelecionada

_MSG = (
    "Servidor de arquivos de artes não configurado: defina ARTE_SHARE_BASE no "
    "ambiente para habilitar a criação de provas por requerimento."
)


class UnconfiguredArteFonte(ArteFontePort):
    """Fonte inerte: recusa leituras e reporta o servidor de arquivos indisponível."""

    def obter_arte(
        self,
        cod_vend_fat: int,
        cod_cliente: int,
        cod_req_art: int,
        anexo_imagem: str | None,
    ) -> ArteSelecionada:
        raise ArteFonteError(_MSG)

    def health(self) -> bool:
        return False


__all__ = ["UnconfiguredArteFonte"]
