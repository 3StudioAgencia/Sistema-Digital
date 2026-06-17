# Provas digitais (W2-C06) — criação, código, etiqueta e RLS

> Porta de entrada do domínio (Wave 2): a prova nasce aqui, com **rota imutável**
> (RN-007), **código alfanumérico único** (RF-002) e **etiqueta PDF** (RF-003).
> Referências: Requisitos v1.0 RF-001/002/003/010, RN-007/011, US-001,
> RNF-017/019 · Backlog C06 · DAT §2/§8 · ADR-035 a ADR-040.

## 1. Modelo de dados (`provas` — migration `0007`)

| Coluna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid PK | Gerado pela **aplicação** (uuid4) — a chave da arte no R2 deriva dele e fica estável entre retries de código; `gen_random_uuid()` como default de segurança |
| `codigo` | varchar(18) UNIQUE | `PRV-AAAA-MM-NNNNNN` (§2) — `uq_provas_codigo` |
| `nome` · `cliente` | varchar(200) | Obrigatórios (RF-001) |
| `requerimento` | varchar(50) | **Texto de dígitos** (preserva zeros à esquerda); validação na borda |
| `vendedor_id` | uuid FK → `usuarios` | A FK garante existência; "setor Vendedor **ativo**" é validado na aplicação (`validar_vendedor`) |
| `rota` | `rota_enum` NOT NULL | `matriz`/`lam_matriz`/`filial`/`lam_filial` — **imutável** (§4) |
| `status` | `status_prova_enum` default `'criada'` | Enum **completo** com os 14 estados (DP-4) — transições só no C11 |
| `arte_key` · `arte_content_type` | varchar | Objeto no R2 (`provas/<id>/arte.<ext>`) + tipo real detectado |
| `created_at` · `updated_at` | timestamptz | `now()` server-side |

Índices (RNF-019, antecipando o C07): `status`, `rota`, `vendedor_id`,
`created_at` (+ o índice único de `codigo`).

## 2. Código identificador (DP-3 / DAT §8.3)

- Formato **`PRV-AAAA-MM-NNNNNN`**; sufixo de 6 caracteres por aleatoriedade
  criptográfica (`secrets`) no alfabeto **não ambíguo** `23456789ABCDEFGHJKMNPQRSTUVWXYZ`
  (31 símbolos, sem `0/O`, `1/I/L` — ~887 milhões de combinações/mês).
- **Unicidade**: constraint `uq_provas_codigo` + **retry de colisão** no serviço
  (até 5 tentativas; esgotar vira erro interno alto, nunca 422).
- **O QR codifica o código puro** (sem URL/indireção): QR e digitação manual
  resolvem para o mesmo registro pelo mesmo caminho (`resolver_prova()` — C10).
- Fonte única: `apps/api/src/domain/provas.py` (`gerar_codigo`/`validar_codigo`/
  `CODIGO_REGEX`) — a máscara do C10 **reutiliza** esse regex.

## 3. Criação atômica (RNF-017)

`POST /provas` (multipart; exclusivo do **admin** — Matriz §7 "Criar Prova"):

1. O **`BodyLimitMiddleware`** corta o corpo acima de **12 MB** (413) — inclusive
   ANTES da auth (o FastAPI parseia o multipart antes das dependências): por
   `Content-Length` declarado e por contador de bytes no `receive` (chunked).
2. Borda valida FORMA (campos obrigatórios, requerimento numérico, rota
   presente) e lê **no máximo 10 MB + 1 byte** do upload para a memória;
3. Serviço valida a arte por **magic bytes** (JPEG/PNG; o header declarado
   precisa concordar) e o vendedor (setor Vendedor ativo);
4. Fecha a transação de leitura, faz o **upload no R2** (`provas/<id>/arte.<ext>`,
   porta do C01 via `asyncio.to_thread`);
5. **INSERT + COMMIT** com retry de colisão do código; qualquer falha após o
   upload **compensa** o objeto no R2 (delete idempotente; falha da própria
   compensação → log `CRITICAL` com `arte_key`).

Resultado: **prova órfã nunca existe**; o pior caso é objeto órfão **marcado**
no log. Storage indisponível responde **503 `storage_indisponivel`** (nunca 500
opaco).

**Idempotência (RNF-015):** o cliente envia `prova_id` (UUID gerado no form) como
**chave de idempotência**. Reenvio após resposta perdida (timeout/abort com o
INSERT já commitado) **converge** para a prova existente — mesmos dados → devolve
a prova já criada (a arte regrava a MESMA key, *put* idempotente, ANTES de
qualquer upload no caminho de pré-check); dados diferentes sob a mesma chave →
**409 `criacao_divergente`** (nunca duplicata nem sobrescrita silenciosa). A UI
gera a chave uma vez por preenchimento e a reusa nas retentativas, além de manter
o botão desabilitado durante o submit e a navegação pós-sucesso.

## 4. Imutabilidade da rota (RN-007 / DP-5)

Três camadas, sem caminho de update em nenhuma:

1. **Domínio/Pydantic** — nenhum schema/serviço expõe update de `rota`;
2. **HTTP** — não existe PATCH/PUT de provas nesta wave (405/404 por ausência);
   quando o C11 criar a superfície de update, o schema herda a ausência de `rota`;
3. **Banco** — trigger `trg_provas_rota_imutavel` (`BEFORE UPDATE OF rota`)
   rejeita `NEW.rota IS DISTINCT FROM OLD.rota` **até para o owner**
   (`UPDATE ... SET rota = rota` segue válido — idempotência). Mudar a rota =
   **cancelar e recriar** (C14).

## 5. Etiqueta PDF (RF-003 / RN-011 / DP-1 / DP-2)

- `GET /provas/{id}/etiqueta.pdf` — **sob demanda, stateless** (nada é
  armazenado; reimprimir gera bytes idênticos — `creation_date` fixada em
  `created_at`). Download com `Content-Disposition: etiqueta-<codigo>.pdf`.
- **Tamanho físico exato 95 × 55 mm** (landscape), tudo **vetorial**: QR
  desenhado módulo a módulo da matriz do `segno`; logos 3STUDIO + Studio&ART em
  SVG pré-processado (`adapters/outbound/etiqueta/assets/` — classes CSS viraram
  atributos `fill`/`fill-rule`, que o parser do fpdf2 entende); fontes core
  Helvetica (sem embedding).
- **Reconciliação DP-1** (o design omitia itens obrigatórios do RF-003): o
  **código em fonte grande abaixo do QR** (Backlog C06) e a **rota como quinta
  linha** do bloco de campos. Demais elementos seguem o design: wordmark +
  logo, "Aponte a câmera para o QR CODE", barra divisória, bloco de campos,
  ano dinâmico (de `created_at`) e "Etiqueta de rastreio".
- **Template padrão parametrizável** (`EtiquetaTemplate` — dimensões, margem,
  fonte, zona quieta do QR); a tela de **configuração** é do C09 (RN-011).
- Libs (DP-7): **`segno`** (QR, pure-python) + **`fpdf2`** (PDF). O
  `qrcode.react` do DAT segue disponível para exibir QR em TELA (C08/C10);
  a etiqueta é renderizada no servidor.

## 6. RLS de `provas` (DP-6 — fecha a pendência do C05)

Espelho versionado em `apps/api/migrations/rls/` (aplicado pela migration
`0008`), composto sobre os helpers do C05:

| Policy | Escopo |
| --- | --- |
| `provas_select_studio` | setor `studio` vê **todas** |
| `provas_select_clicheria` | setor `clicheria` vê **todas** |
| `provas_select_admin` | flag `administrador` vê **todas** (quem cria precisa enxergar — releitura ADR-023) |
| `provas_select_vendedor` | `vendedor_id = app_current_user_id()` |
| `provas_select_motorista` | `status ∈` os **3** "Com Motorista" (= `ESTADOS_EM_TRANSITO` do domínio) |
| `provas_insert_admin` | INSERT do flag admin **+ invariantes de criação** (migration `0009`) |

**WITH CHECK endurecido (`0009`):** como `provas` é exposta pela Data API/PostgREST,
a policy de INSERT espelha os invariantes que o backend valida — para acesso
direto não burlar o domínio: `status = 'criada'` (US-001), `codigo` no formato
canônico (`PRV-\d{4}-(0[1-9]|1[0-2])-[charset]{6}` — mesmo de `domain/provas.py`)
e `vendedor_id` de um usuário **setor vendedor ativo** (a FK só garante
existência). Sem isso, um admin poderia inserir direto prova em status arbitrário,
código fora do contrato do C10/QR ou vendedor inválido.

Grants de **privilégio mínimo**: `authenticated` tem só `SELECT, INSERT`
(UPDATE chega no C11; DELETE no C14). Anti-enumeração: prova inexistente e
prova fora do escopo retornam o **mesmo** `404 "Prova não encontrada."`.

**Role de runtime não-owner** (fecha o ADR-034 item 3): `rastreio_runtime`
(`NOLOGIN NOINHERIT NOBYPASSRLS`, membro de `authenticated`) criado pela `0008`
(espelho `_runtime_role.sql`). Ativação (passo de operação, fora do repo):

```sql
ALTER ROLE rastreio_runtime LOGIN PASSWORD '<segredo-fora-do-repo>';
```

e apontar `DATABASE_URL` para ele (no pooler do Supabase, usuário
`rastreio_runtime.<project-ref>`). Tarefas de sistema (migrations,
`bootstrap_admin`, keep-alive) permanecem no owner via `MIGRATIONS_DATABASE_URL`.

> **Obrigatório em staging/produção (M-01 — remediação W3).** Apontar `DATABASE_URL`
> ao owner/superuser deixaria a RLS inerte (BYPASSRLS ignora as policies; o
> `FORCE` não anula). Por isso a app faz uma **checagem de boot**
> (`verificar_role_runtime_nao_privilegiado`, em `infrastructure/database.py`):
> em `staging`/`production`, **recusa subir** se o role de conexão for
> superuser/`BYPASSRLS`. Em `dev`/`test` o gate é no-op (conecta-se como `postgres`
> de propósito). `FORCE ROW LEVEL SECURITY` **não** foi adicionado: um superuser o
> ignora de qualquer modo e ele quebraria os resolvedores `private.*`
> (`SECURITY DEFINER` rodam como owner) — o controle que fecha o cenário é o role
> NOBYPASSRLS acima. Detalhe em `docs/rbac.md` §"Role de runtime".

**Equivalência (extensão do harness do C05):** `test_equivalencia_rls_provas.py`
trava domínio ↔ `rls/*.sql` ↔ migration (offline); `test_rls_provas.py` (@db)
valida cada célula da Matriz com provas semeadas em vários status, **sem**
depender da máquina de estados do C11.

## 7. Frontend (`/provas/nova`)

Página exclusiva do admin (proxy C05 já gateia `criar_prova`; o backend nega
403 em profundidade). Formulário fiel ao design: Nome/Requerimento (linha 1),
Cliente/Vendedor (linha 2 — vendedores ativos em **uma** consulta
`GET /usuarios?setor=vendedor&status=ativo`), **segmented control de Rota**
(Matriz · Filial · Lam. Matriz · Lam. Filial, **sem pré-seleção** — a escolha é
manual e consciente, e "criar sem rota" produz erro claro), dropzone JPG/PNG
≤ 10 MB (validação client + server). Pós-criação (DP-7): toast + **download
automático da etiqueta** + navegação para `/provas`; se só o download falhar,
painel de retry (a etiqueta é regenerável). Animações por tokens
(transform/opacity; pílula da rota via `layoutId`), zeradas sob
`prefers-reduced-motion`.

## 8. Como rodar localmente

```bash
# migrations (cria provas + RLS + role de runtime)
cd apps/api && uv run alembic upgrade head

# testes (inclui @db contra o Postgres local zonky 5433)
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/rastreio_test \
  uv run pytest tests/unit/test_provas_dominio.py tests/unit/test_provas_service.py \
  tests/unit/test_etiqueta_pdf.py tests/unit/test_equivalencia_rls_provas.py \
  tests/integration/test_rls_provas.py tests/integration/test_provas_endpoints.py \
  tests/integration/test_body_limit.py

# gerar uma etiqueta de amostra (sem banco): ver docstring de
# src/adapters/outbound/etiqueta/fpdf_etiqueta.py — FpdfEtiquetaGenerator().gerar_pdf(...)

# fluxo completo: api de pé + R2 configurado (R2_*) → web /provas/nova (admin)
```

## 9. Checklist dos critérios de aceitação (§6 do prompt)

- [x] Criar sem rota → erro de validação claro (client + 422 no server).
- [x] PATCH em `rota` rejeitado (sem superfície de update — 405/404) e UPDATE
  direto no banco rejeitado pelo **trigger**; `rota_enum` NOT NULL.
- [x] Código único (formato/charset DP-3), UNIQUE + retry; **QR = código puro**.
- [x] Etiqueta com nome, requerimento, vendedor, **rota**, QR e **código em
  destaque**, em **95 × 55 mm exatos**, via download/impressão.
- [x] Arte validada (magic bytes + ≤ 10 MB, client+server) no R2; criação
  **atômica** (sem prova/arte órfã; compensação logada).
- [x] RLS ativa por perfil; query direta fora do escopo → **0 registros**;
  harness de equivalência estendido às células de provas.
- [x] Prova nasce **"Criada"** na rota selecionada (US-001).
- [x] Tela fiel ao design + DP-1, gateada a admin, responsiva, animações com
  `prefers-reduced-motion`.
- [x] Índices RNF-019; stateless; sem segredos versionados; R$ 0.
- [x] `ruff`/`mypy --strict`/`pytest` (338) e `pnpm lint/build/test` (93) +
  Playwright verdes; ciclo `upgrade→downgrade→upgrade` limpo; RLS reaplicável.
