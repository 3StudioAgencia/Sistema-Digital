# Storage de artes — servidor local + fonte no servidor de arquivos

> Fatia 0–4 da migração de storage (fora do backlog v1.0). O **Cloudflare R2 saiu**
> (deploy on-prem, custo R$ 0, sem egress). Há agora **duas** superfícies de arquivo,
> deliberadamente separadas em duas portas distintas:
>
> - **DESTINO** (`StoragePort`) — onde a app **GRAVA** o snapshot da arte de cada
>   prova. Passou de R2 para um **diretório local** (`FilesystemStorage`).
> - **FONTE** (`ArteFontePort`) — de onde a app **LÊ** a imagem oficial do
>   requerimento: o **servidor de arquivos do estúdio** (SMB/UNC), **somente leitura**.
>
> Ver também [`firebird.md`](firebird.md) (resolução do requerimento) e `DECISIONS.md`
> ADR-119/ADR-123.

## 1. Por que duas portas

O R2 era origem **e** destino num só lugar (upload manual do admin → R2 → proxy de
leitura). No novo fluxo a arte já existe: foi produzida pelo fluxo legado e vive no
servidor de arquivos do estúdio. A app **não recebe upload** — ela **lê** a imagem
oficial de lá (read-only) e **grava uma cópia** (snapshot) no seu próprio storage.
Isso desacopla a prova do share depois de criada: renomear/mover a pasta legada não
quebra o detalhe/arte/etiqueta da prova, que sempre lê do snapshot.

| | `StoragePort` (destino) | `ArteFontePort` (fonte) |
| --- | --- | --- |
| Direção | Leitura **e** escrita | **Somente leitura** |
| Onde | Diretório local (`STORAGE_DIR`) | Share do estúdio (`ARTE_SHARE_BASE`) |
| Adapter | `FilesystemStorage` | `SistemaDeArquivosArteFonte` |
| Chave/caminho | `provas/<uuid>/arte.<ext>` | `<COD_VEND_FAT>/<COD_CLIEN>/<COD_REQ_ART>/VERSAO/` |

## 2. DESTINO — `FilesystemStorage` (substitui o R2)

`adapters/outbound/storage/filesystem_storage.py`. Mesmo contrato da `StoragePort`
que o `R2Storage` cumpria (upload idempotente, download 404, delete idempotente) —
a troca é transparente para `ProvasService`/`ProvasConsultaService`.

- **Escrita atômica**: grava num temporário no mesmo diretório e `os.replace`
  (atômico no mesmo filesystem) — um crash no meio do upload nunca deixa arte
  meio-gravada no lugar da definitiva.
- **Anti path-traversal**: a key é resolvida e conferida contra a base
  (`_resolver`); uma key com `..` nunca escapa da base (defesa em profundidade,
  embora a key seja sempre gerada pela app).
- **`health()`**: base existe **e** gravável (`os.W_OK`).
- O `content_type` **não** é persistido no arquivo — a prova guarda
  `arte_content_type` no Postgres (o proxy de leitura do C08 o devolve).

```dotenv
# Diretório onde a app GRAVA a cópia (snapshot). Vazio = storage 'down' no readiness
# (a app sobe; criar prova falha com erro claro). É criado no boot (idempotente).
STORAGE_DIR=C:\rastreio\artes        # Linux: /var/rastreio/artes
```

**Removido nesta migração:** `adapters/outbound/storage/r2_storage.py`,
`tests/unit/test_r2_mapeamento_de_erros.py`, e as 4 variáveis `R2_*` do `.env`.
`boto3` deixa de ser dependência de storage. As artes antigas (se houvesse) não
migram — o projeto é greenfield.

## 3. FONTE — `SistemaDeArquivosArteFonte` (read-only)

`adapters/outbound/arte_fonte/filesystem_arte_fonte.py`. Lê a imagem oficial em
`<base>/<COD_VEND_FAT>/<COD_CLIEN>/<COD_REQ_ART>/VERSAO/`. A escolha é
**determinística**:

1. o arquivo nomeado por `ANEXO_IMAGEM` (o que o ERP marca como a versão atual);
2. fallback: a maior versão `_V{n}` no nome; empate → mais recente por `mtime`.

- A subpasta **`ANEXO/`** (anexo do cliente) é **ignorada de propósito** — só a
  `VERSAO/` contém a prova aprovada.
- Valida **JPG/PNG por magic bytes** (`detectar_tipo_imagem` — fonte única do
  domínio de provas), não por extensão.
- **Teto** anti-OOM (`ARTE_FONTE_TAMANHO_MAXIMO_MB`, padrão 50): imagem acima →
  tratada como indisponível.
- **`health()`**: a base do share existe/acessível.

```dotenv
# Base até o STUDIO_TRANSICAO; a app compõe /<COD_VEND_FAT>/<COD_CLIEN>/<COD_REQ_ART>/VERSAO/.
# USE BARRAS "/" no UNC (ver §4). Vazio = fonte 'down' no readiness.
ARTE_SHARE_BASE=//172.16.0.6/Artes/STUDIO_TRANSICAO
ARTE_FONTE_TAMANHO_MAXIMO_MB=50
```

## 4. ⚠️ Caminho UNC com barras normais (gotcha do `.env`)

O parser de `.env` (**python-dotenv**) **colapsa `\\` em `\`**, quebrando um UNC
`\\172.16.0.6\Artes\...` (vira `\172.16.0.6\Artes...`, um único backslash). A
solução é escrever o UNC com **barras normais**: `//172.16.0.6/Artes/STUDIO_TRANSICAO`.
O `pathlib.Path` trata `//host/share` como UNC no Windows — funciona igual. Vale
tanto para `ARTE_SHARE_BASE` quanto para qualquer caminho de rede em `.env`.

## 5. Modos de falha (fonte)

| Situação | Erro | HTTP |
| --- | --- | --- |
| Pasta `VERSAO/` ausente/vazia, ou nenhum JPG/PNG válido | `ArteNaoDisponivelError` (domínio) | **422** |
| Imagem acima do teto | `ArteNaoDisponivelError` | **422** |
| Share fora do ar / permissão / IO | `ArteFonteError` (infra) | **503** |

A separação é importante: "não há imagem" (negócio, 422) **nunca** é confundido com
"o share caiu" (infra, 503) — o cliente não fica retentando em loop o que não vai
voltar.

## 6. Snapshot na criação (o elo entre as duas portas)

`ProvasService.criar` ([`firebird.md`](firebird.md) §7): lê a imagem via
`ArteFontePort` (fonte) e **copia** para o `StoragePort` (destino) sob a chave
`provas/<id>/arte.<ext>`, tudo **antes** do INSERT — o commit só ocorre com a arte
já no storage; qualquer falha após o upload **compensa** o objeto (delete
idempotente). Prova órfã nunca existe; o pior caso é um objeto órfão no storage,
logado (`CRITICAL`) para limpeza. Daí em diante, detalhe/arte/etiqueta leem só do
snapshot (proxy do C08) — o share não é mais tocado.

## 7. Adapters "unconfigured" (degradação graciosa)

Sem `STORAGE_DIR`/`ARTE_SHARE_BASE`/`FIREBIRD_*`, a app **sobe** com adapters de
fallback que reportam `health()`→`False` e levantam erro claro (503) se usados. O
readiness mostra o subsistema 'down'; só o fluxo de criação por requerimento fica
indisponível — o resto da plataforma funciona.

## 8. Testes

```bash
cd apps/api
uv run pytest tests/unit/test_storage.py \
              tests/unit/test_unconfigured_storage.py \
              tests/integration/test_arte_fonte_share.py \
              tests/integration/test_criacao_e2e.py
```

`@share` pula sem `ARTE_SHARE_TEST_BASE`; `@firebird` sem `FIREBIRD_TEST_DATABASE`
(offline-friendly). `test_storage.py`/`test_unconfigured_storage.py` cobrem o
`FilesystemStorage` (escrita atômica, path traversal, 404) sem IO de rede.
