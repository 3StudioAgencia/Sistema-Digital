"""UnconfiguredStorage: a app sobe sem storage, mas falha com mensagem acionável no uso."""

import pytest
from src.adapters.outbound.storage.unconfigured import UnconfiguredStorage
from src.application.ports.storage import StorageError


@pytest.fixture
def storage() -> UnconfiguredStorage:
    return UnconfiguredStorage()


def test_health_sempre_false(storage: UnconfiguredStorage) -> None:
    assert storage.health() is False


@pytest.mark.parametrize(
    "operacao",
    [
        lambda s: s.upload("k", b"v", "image/png"),
        lambda s: s.download("k"),
        lambda s: s.delete("k"),
    ],
)
def test_uso_real_falha_com_instrucao_de_configuracao(
    storage: UnconfiguredStorage, operacao: object
) -> None:
    with pytest.raises(StorageError, match="STORAGE_DIR"):
        operacao(storage)  # type: ignore[operator]
