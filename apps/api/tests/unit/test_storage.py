"""StoragePort: roundtrip upload/download comprovado via porta (critério §5.2).

O adapter real (``FilesystemStorage``) é exercitado contra um diretório temporário;
o ``FakeStorage`` (dublê da suíte) é validado junto para garantir o mesmo contrato.
"""

import shutil
from pathlib import Path

import pytest
from src.adapters.outbound.storage.filesystem_storage import FilesystemStorage
from src.application.ports.storage import StorageError, StorageObjectNotFound, StoragePort

from tests.conftest import FakeStorage


@pytest.fixture
def filesystem(tmp_path: Path) -> FilesystemStorage:
    return FilesystemStorage(str(tmp_path / "artes"))


@pytest.fixture
def fake() -> FakeStorage:
    return FakeStorage()


@pytest.mark.parametrize("impl", ["filesystem", "fake"])
class TestContratoDaPorta:
    """Mesmo contrato para o adapter real (disco) e para o dublê da suíte."""

    @pytest.fixture
    def storage(self, impl: str, request: pytest.FixtureRequest) -> StoragePort:
        result: StoragePort = request.getfixturevalue(impl)
        return result

    def test_upload_e_download_devolvem_o_mesmo_conteudo(self, storage: StoragePort) -> None:
        conteudo = b"\x89PNG fake-art-bytes"
        key = storage.upload("provas/2026/06/arte.png", conteudo, "image/png")

        assert key == "provas/2026/06/arte.png"
        assert storage.download(key) == conteudo

    def test_reupload_da_mesma_key_substitui_o_objeto(self, storage: StoragePort) -> None:
        storage.upload("k", b"v1", "image/png")
        storage.upload("k", b"v2", "image/png")
        assert storage.download("k") == b"v2"

    def test_download_de_key_inexistente_levanta_not_found(self, storage: StoragePort) -> None:
        with pytest.raises(StorageObjectNotFound):
            storage.download("nao-existe.png")

    def test_delete_e_idempotente(self, storage: StoragePort) -> None:
        storage.upload("k", b"v", "image/png")
        storage.delete("k")
        storage.delete("k")  # segunda remoção não levanta erro
        with pytest.raises(StorageObjectNotFound):
            storage.download("k")

    def test_health_ok(self, storage: StoragePort) -> None:
        assert storage.health() is True


class TestFilesystemEspecifico:
    def test_grava_arquivo_no_disco_sob_a_base(self, tmp_path: Path) -> None:
        base = tmp_path / "artes"
        storage = FilesystemStorage(str(base))
        storage.upload("provas/abc/arte.jpg", b"conteudo", "image/jpeg")
        assert (base / "provas" / "abc" / "arte.jpg").read_bytes() == b"conteudo"

    def test_health_false_quando_base_some(self, tmp_path: Path) -> None:
        base = tmp_path / "artes"
        storage = FilesystemStorage(str(base))
        shutil.rmtree(base)  # base removida após criada → readiness reporta down
        assert storage.health() is False

    def test_key_com_traversal_e_rejeitada(self, tmp_path: Path) -> None:
        storage = FilesystemStorage(str(tmp_path / "artes"))
        with pytest.raises(StorageError):
            storage.upload("../fora-da-base.txt", b"x", "application/octet-stream")
