# Integração com o ERP legado (Firebird) — SOMENTE LEITURA

> Fatia 1–4 da migração de origem de dados (fora do backlog v1.0). A criação de
> prova deixou de receber os dados digitados/enviados no formulário e passou a
> **nascer do número de requerimento**: o backend lê o ERP legado (Firebird) para
> resolver nome/cliente/vendedor e o servidor de arquivos para a imagem oficial.
> Ver também [`storage.md`](storage.md) (destino do snapshot + fonte da arte) e
> `DECISIONS.md` ADR-119..124.

## 1. Regra inegociável

**É estritamente proibido escrever qualquer coisa no banco Firebird.** O ERP é a
fonte da verdade de um sistema de terceiros em produção; o Rastreio apenas **lê**
dele e grava exclusivamente no **nosso PostgreSQL local**. A regra é defendida em
profundidade:

1. **Contrato da porta** (`RequerimentoReaderPort`) — só expõe `buscar`/`health`,
   nenhum método de escrita.
2. **Transação READ ONLY no driver** — toda consulta abre a transação em
   `TraAccessMode.READ` (`isolation=SNAPSHOT`); o **motor Firebird rejeita**
   qualquer tentativa de escrita, mesmo acidental.
3. **SQL parametrizado** — nunca interpolado (`WHERE COD_REQ_ART = ?`).

## 2. Onde vive (Ports & Adapters)

| Camada | Arquivo | Papel |
| --- | --- | --- |
| **domain** | `domain/requerimentos.py` | Value object `RequerimentoArte` (puro) + erros de negócio (`RequerimentoNaoEncontradoError` 404, `RequerimentoIncompletoError` 422, `VendedorNaoMapeadoError` 422, `ArteNaoDisponivelError` 422). |
| **application/ports** | `application/ports/requerimentos.py` | `RequerimentoReaderPort` (ABC síncrona) + `RequerimentoReaderError` (infra → 503). |
| **adapters/outbound** | `adapters/outbound/firebird/requerimento_reader.py` | `FirebirdRequerimentoReader` (firebird-driver). |
| **adapters/outbound** | `adapters/outbound/firebird/unconfigured.py` | Adapter de fallback: sobe a app sem ERP; `health()`→`False`, `buscar()`→`RequerimentoReaderError` (503). |

A porta é **síncrona** (o firebird-driver é bloqueante) — igual à `StoragePort`. Os
handlers async a despacham por `asyncio.to_thread`, mantendo o event loop livre sem
acoplar a interface ao driver.

## 3. Schema legado consumido (só leitura)

Uma única consulta com `LEFT JOIN` (um vendedor/cliente ausente não faz o
requerimento sumir):

```sql
SELECT r.COD_REQ_ART, r.PRODART, r.COD_VENDE, v.NOMVEN, v.COD_VEND_FAT,
       r.COD_CLIEN, c.CLIENTE, r.ANEXO_IMAGEM
FROM TB_REQ_ARTE r
LEFT JOIN TB_VENDEDOR v ON v.COD_VENDE = r.COD_VENDE
LEFT JOIN TB_CLIENTES c ON c.COD_CLIEN = r.COD_CLIEN
WHERE r.COD_REQ_ART = ?
```

| Coluna ERP | Mapeia para | Uso |
| --- | --- | --- |
| `TB_REQ_ARTE.COD_REQ_ART` | `requerimento` (str) | Número digitado na criação. |
| `TB_REQ_ARTE.PRODART` | `nome` da prova | Nome do produto/arte. |
| `TB_REQ_ARTE.COD_VENDE` | (mapeamento) | Casado com `usuarios.cod_vendedor_firebird`. |
| `TB_VENDEDOR.NOMVEN` | `nome_vendedor` | Só informativo no preview. |
| `TB_VENDEDOR.COD_VEND_FAT` | caminho da arte | Compõe `/<COD_VEND_FAT>/…/VERSAO/`. |
| `TB_REQ_ARTE.COD_CLIEN` | caminho da arte | Compõe `/…/<COD_CLIEN>/…`. |
| `TB_CLIENTES.CLIENTE` | `cliente` | Nome do cliente na prova. |
| `TB_REQ_ARTE.ANEXO_IMAGEM` | escolha da imagem | Nome do arquivo OFICIAL da versão atual. |

Campos textuais nulos/vazios viram `None` (`NOMVEN`/`CLIENTE` são `NULLABLE`).
`COD_VEND_FAT` `NULLABLE` → requerimento **incompleto** (bloqueia criação).

## 4. Mapeamento vendedor ERP → sistema (migration 0024)

O ERP tem seu próprio cadastro de vendedores (`COD_VENDE`); o Rastreio tem os seus
(`usuarios`). A ponte é a coluna nova **`usuarios.cod_vendedor_firebird`**:

- **NULLABLE** — nem todo vendedor mapeia; nenhum outro setor tem código.
- **UNIQUE PARCIAL** (`WHERE cod_vendedor_firebird IS NOT NULL`) — um `COD_VENDE` →
  no máximo um usuário (sem ambiguidade); parcial para não colidir vários `NULL`.
- **CHECK** `cod_vendedor_firebird IS NULL OR setor = 'vendedor'` — espelha a regra
  de domínio (`validar_cod_vendedor_firebird` em `domain/usuarios.py`): só Vendedor
  pode ter código.

Na criação, `buscar_por_cod_vendedor_firebird(COD_VENDE)` resolve o `vendedor_id` do
app **sozinho** — a RLS "vendedor só vê as suas" (por `vendedor_id`) segue intacta.
Vendedor sem mapeamento → `VendedorNaoMapeadoError` (422): o admin cadastra o código
no Gerenciador de Usuários antes de criar a prova. O campo é editado em `/usuarios`
(só aparece/persiste para o setor Vendedor; trocar o setor limpa o código).

## 5. Configuração (`.env`)

```dotenv
# Tudo-ou-nada: os três juntos, ou os três vazios (ERP 'down' no readiness).
FIREBIRD_DATABASE=localhost:C:\bancos\STUDIOEART_2010.FDB   # host:caminho (via servidor, evita lock)
FIREBIRD_USER=SYSDBA
FIREBIRD_PASSWORD=<senha>
FIREBIRD_CHARSET=WIN1252                                     # banco legado é WIN1252 (acentos pt-BR)
FIREBIRD_CLIENT_LIBRARY=C:\Program Files\Firebird\Firebird_4_0\fbclient.dll  # opcional (autolocaliza)
```

- **`host:caminho`** (não caminho puro): conecta **via servidor Firebird**, não pelo
  arquivo direto — evita lock/conflito com o sistema legado que já usa o `.FDB`.
- **`WIN1252`** é obrigatório: o banco legado nasceu nesse charset; conectar em
  UTF-8 corromperia acentos.
- **`FIREBIRD_CLIENT_LIBRARY`** aponta a `fbclient.dll` do servidor instalado
  (config global do driver, feita uma vez por processo). Vazio → o driver
  autolocaliza.
- Validado contra **Firebird 4.0.3** em produção (requerimento real 150288 →
  REGISLAINE PETRIM / LATICINIOS FLORIDA / `VERSAO_150288_V3.jpg`).

Dependência: **`firebird-driver`** (`pyproject.toml`). Fora dela, `uv sync`.

## 6. Modos de falha e mapeamento HTTP

| Situação | Erro | HTTP | Observação |
| --- | --- | --- | --- |
| Requerimento inexistente | `RequerimentoNaoEncontradoError` | **404** | Superfície admin-only; sem preocupação anti-enumeração (≠ `provas`). |
| Falta `PRODART`/cliente/`COD_VEND_FAT` | `RequerimentoIncompletoError` | **422** | Não se cria prova de requerimento incompleto. |
| Vendedor não cadastrado no app | `VendedorNaoMapeadoError` | **422** | Cadastrar `cod_vendedor_firebird` antes. |
| Sem imagem utilizável no share | `ArteNaoDisponivelError` | **422** | Ver [`storage.md`](storage.md). |
| ERP fora do ar / driver / credencial | `RequerimentoReaderError` | **503** | Indisponibilidade clara — nunca 500 opaco nem confundido com "não existe". |

`health()` alimenta o readiness (`GET /health/ready`): ERP inacessível é reportado
sem derrubar a app — só a criação por requerimento fica indisponível.

## 7. Fluxo de criação (resumo)

`POST /provas {cod_req_art, rota, prova_id?}` → `ProvasService.criar`:

1. Idempotência (RNF-015): `prova_id` já existe → converge (não toca ERP/share).
2. `_resolver(cod_req_art)`: lê o ERP + mapeia o vendedor (só leitura, sem IO externo).
3. Fecha a transação de leitura (não segura conexão durante o IO).
4. Lê a imagem oficial no servidor de arquivos ([`storage.md`](storage.md) §3).
5. **Snapshot** da arte no nosso storage local (chave `provas/<id>/arte.<ext>`).
6. INSERT + COMMIT atômico (RNF-017), com compensação da arte em falha.

Preview sem criar: `GET /provas/requerimento/{cod_req_art}` (dados) e
`GET /provas/requerimento/{cod_req_art}/arte` (imagem) — usados pela tela
`/provas/nova` para auto-preencher os campos travados e mostrar o box da imagem.

## 8. Testes

```bash
cd apps/api
uv run pytest tests/integration/test_firebird_reader.py \
              tests/integration/test_arte_fonte_share.py \
              tests/integration/test_criacao_e2e.py \
              tests/unit/test_provas_service.py
```

Os testes `@firebird`/`@share` só rodam com o ERP e o share reais configurados
(`FIREBIRD_TEST_DATABASE`, `ARTE_SHARE_TEST_BASE`); pulam sem eles (offline-friendly,
como o padrão `@db`). O `test_criacao_e2e` cria uma prova **de verdade** contra
Firebird + share + Postgres.
