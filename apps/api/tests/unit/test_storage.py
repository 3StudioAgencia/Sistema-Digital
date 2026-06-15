"""StoragePort: roundtrip upload/download comprovado via porta (critério §5.2).

O adapter real (R2Storage/boto3) é exercitado contra o S3 do `moto` — mesma
API S3-compatível do R2, sem rede. O FakeStorage (dublê da suíte) é validado
junto para garantir que se comporta como a porta promete.
"""

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws
from src.adapters.outbound.storage.r2_storage import R2Storage
from src.application.ports.storage import StorageError, StorageObjectNotFound, StoragePort
from src.infrastructure.config import Settings

from tests.conftest import FakeStorage

BUCKET = "rastreio-artes-test"


@pytest.fixture
def r2_storage() -> Iterator[R2Storage]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield R2Storage(client=client, bucket=BUCKET)


@pytest.fixture
def fake() -> FakeStorage:
    return FakeStorage()


@pytest.mark.parametrize("impl", ["r2_storage", "fake"])
class TestContratoDaPorta:
    """Mesmo contrato para o adapter real (moto) e para o dublê da suíte."""

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


class TestR2Especifico:
    def test_health_false_para_bucket_inexistente(self) -> None:
        with mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            storage = R2Storage(client=client, bucket="bucket-que-nao-existe")
            assert storage.health() is False

    def test_from_settings_sem_r2_configurado_falha_com_mensagem_acionavel(self) -> None:
        s = Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url="postgresql+asyncpg://u:p@h/db",
            migrations_database_url="postgresql+asyncpg://u:p@h/db",
        )
        with pytest.raises(StorageError, match="R2 não configurado"):
            R2Storage.from_settings(s)

    def test_from_settings_define_timeouts_explicitos(self) -> None:
        """Calibração W2-C06: connect curto (falha rápido) + read longo (upload
        de arte de até 10 MB) + retries idempotentes. O orçamento de 5s do
        readiness (W0-A-004) é imposto pelo CALLER — asyncio.wait_for no health
        check — e não depende mais do timeout do cliente."""
        s = Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url="postgresql+asyncpg://u:p@h/db",
            migrations_database_url="postgresql+asyncpg://u:p@h/db",
            r2_endpoint_url="https://acc.r2.cloudflarestorage.com",
            r2_access_key_id="key",
            r2_secret_access_key="secret",
            r2_bucket="artes",
        )
        storage = R2Storage.from_settings(s)
        config = storage._client.meta.config
        assert config.connect_timeout == 5
        assert config.read_timeout == 60
        # botocore normaliza max_attempts=3 (retries) em total_max_attempts=4
        # (1 tentativa inicial + 3 retentativas)
        assert config.retries == {"mode": "standard", "total_max_attempts": 4}
