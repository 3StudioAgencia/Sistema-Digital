"""R2Storage: mapeamento de erros do boto3 para as exceções da porta.

Usa um stub de cliente S3 que falha sob demanda — os caminhos de erro não
dependem de rede nem do moto.
"""

from typing import Any

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from src.adapters.outbound.storage.r2_storage import R2Storage
from src.application.ports.storage import StorageError, StorageObjectNotFound


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "operation")


class _ClienteExplosivo:
    """Stub do cliente S3: toda operação falha com o erro configurado."""

    def __init__(self, erro: Exception) -> None:
        self._erro = erro

    def _explode(self, **kwargs: Any) -> Any:
        raise self._erro

    put_object = _explode
    get_object = _explode
    delete_object = _explode
    head_bucket = _explode


@pytest.fixture
def storage_com(request: pytest.FixtureRequest) -> R2Storage:
    return R2Storage(client=_ClienteExplosivo(request.param), bucket="b")


ERRO_GENERICO = _client_error("InternalError")
ERRO_REDE = EndpointConnectionError(endpoint_url="https://r2.example")
ERRO_NAO_ENCONTRADO = _client_error("NoSuchKey")


@pytest.mark.parametrize("storage_com", [ERRO_GENERICO, ERRO_REDE], indirect=True)
class TestErrosDeInfraestrutura:
    def test_upload_vira_storage_error(self, storage_com: R2Storage) -> None:
        with pytest.raises(StorageError, match="Falha ao gravar"):
            storage_com.upload("k", b"v", "image/png")

    def test_download_vira_storage_error(self, storage_com: R2Storage) -> None:
        with pytest.raises(StorageError, match="Falha ao ler"):
            storage_com.download("k")

    def test_delete_vira_storage_error(self, storage_com: R2Storage) -> None:
        with pytest.raises(StorageError, match="Falha ao remover"):
            storage_com.delete("k")

    def test_health_vira_false_sem_levantar(self, storage_com: R2Storage) -> None:
        assert storage_com.health() is False


@pytest.mark.parametrize("storage_com", [ERRO_NAO_ENCONTRADO], indirect=True)
def test_nosuchkey_vira_not_found_e_nao_erro_generico(storage_com: R2Storage) -> None:
    with pytest.raises(StorageObjectNotFound):
        storage_com.download("k")
