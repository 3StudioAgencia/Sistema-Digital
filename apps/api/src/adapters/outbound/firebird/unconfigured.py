"""Stand-in do leitor do ERP quando o Firebird não está configurado.

Mesma filosofia do ``UnconfiguredStorage``: a app SOBE sem o ERP (dev/CI/offline)
e o readiness reporta o ERP como "down" — degradação clara em vez de crash no
boot. Qualquer consulta real levanta ``RequerimentoReaderError`` (503 na borda).
"""

from src.application.ports.requerimentos import (
    RequerimentoReaderError,
    RequerimentoReaderPort,
)
from src.domain.requerimentos import RequerimentoArte

_MSG = (
    "ERP (Firebird) não configurado: defina FIREBIRD_DATABASE/USER/PASSWORD no "
    "ambiente para habilitar a criação de provas por requerimento."
)


class UnconfiguredRequerimentoReader(RequerimentoReaderPort):
    """Leitor inerte: recusa consultas e reporta o ERP indisponível no readiness."""

    def buscar(self, cod_req_art: int) -> RequerimentoArte | None:
        raise RequerimentoReaderError(_MSG)

    def health(self) -> bool:
        return False


__all__ = ["UnconfiguredRequerimentoReader"]
