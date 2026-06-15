"""Teto do corpo da requisição (W2-C06, revisão adversarial) — offline.

O FastAPI parseia o multipart ANTES de resolver as dependências de auth, então
o limite precisa valer também para clientes NÃO autenticados: sem ele, um
anônimo faria o servidor receber GBs para disco temporário antes do 401/403.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
from src.adapters.inbound.http.middleware import LIMITE_CORPO_BYTES
from src.infrastructure.config import Settings

from tests.conftest import FakeStorage, make_client, ping_ok


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    async with make_client(settings, FakeStorage(), ping_ok) as c:
        yield c


async def test_content_length_acima_do_teto_e_413_imediato_sem_auth(
    client: httpx.AsyncClient,
) -> None:
    """Content-Length declarado acima do teto: rejeitado sem ler o corpo —
    e SEM exigir token (a defesa vale pré-auth)."""
    resp = await client.post(
        "/provas",
        content=b"x",  # corpo mínimo; o que conta é o header declarado
        headers={
            "Content-Type": "multipart/form-data; boundary=x",
            "Content-Length": str(LIMITE_CORPO_BYTES + 1),
        },
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "payload_too_large"


async def test_corpo_em_streaming_acima_do_teto_e_cortado_no_meio(
    client: httpx.AsyncClient,
) -> None:
    """Sem Content-Length confiável (chunked) o contador aborta a leitura ao
    cruzar o teto — Content-Length é declarativo e contornável. Usa um envelope
    multipart VÁLIDO com uma parte de arquivo sem fim: o parser segue lendo e o
    contador estoura ANTES de o ataque concluir."""
    boundary = "X"
    preambulo = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="arte"; filename="a.bin"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()

    async def gerador() -> AsyncIterator[bytes]:
        yield preambulo
        bloco = b"\x00" * (1024 * 1024)
        # Parte de arquivo deliberadamente NUNCA fechada (sem boundary final):
        # simula o atacante que mantém o corpo aberto além do teto.
        for _ in range(LIMITE_CORPO_BYTES // len(bloco) + 2):
            yield bloco

    resp = await client.post(
        "/provas",
        content=gerador(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] in {"payload_too_large", "http_error"}


async def test_requisicoes_normais_passam_pelo_teto(client: httpx.AsyncClient) -> None:
    """Regressão: corpos pequenos seguem o fluxo normal (aqui, 401 sem token)."""
    resp = await client.post(
        "/provas",
        data={"nome": "x"},
        files={"arte": ("a.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")},
    )
    assert resp.status_code == 401  # passou do teto e parou na auth, como antes
