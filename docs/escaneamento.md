# Escaneamento — Identificação física→digital (W3-C10)

> Primeiro componente da **Wave 3** (fluxo de movimentação) e o mais **mobile-first** do
> sistema. Conecta a prova **física** (etiqueta impressa) ao registro **digital** por
> **leitura de QR** (in-app) ou **digitação manual**, com um endpoint **único e idempotente**
> de identificação. O C10 **só identifica** — validar a próxima transição é o **C11** e
> capturar a assinatura é o **C12**.
>
> Referências: Backlog **C10** · Requisitos **RF-004, RF-005, RF-029, RN-014, RNF-002,
> RNF-013, RNF-014** · §7 (Escanear = universal) · C06 (código/QR) · C08 (anti-vazamento).
> Decisões: **ADR-052..056**.

---

## 1. Visão geral

```
QR (câmera)  ─┐
              ├─► normaliza ─► valida formato ─► resolve_por_codigo (RLS) ─► ProvaDetalhe
código manual ┘                                                              └─► tela de
                                                                                 confirmação
```

- **Mesmo caminho** para QR e manual: o QR carrega o **próprio código** (C06, sem URL), então
  leitura e digitação batem no mesmo `POST /provas/identificar` (`resolver_prova()`).
- **Idempotente quanto ao mecanismo:** o mesmo código resolve sempre o mesmo registro.
- **Universal-em-escopo** (Matriz §7: "Escanear"): qualquer perfil ativo identifica; o **escopo
  de dado** é da **RLS de `provas`** (claims propagados — ADR-008).

---

## 2. O contrato do código (DP-1 — ADR-052)

O design do Figma mostra o input manual como **"3S- / 8 dígitos"** — isso é **legado**. Vale o
formato **canônico do C06**:

| Item | Valor |
| --- | --- |
| Formato | `PRV-AAAA-MM-NNNNNN` |
| Regex (fonte única) | `^PRV-\d{4}-(0[1-9]\|1[0-2])-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{6}$` |
| Sufixo | 6 caracteres, charset não ambíguo (sem `0/O`, `1/I/L`) — 31 símbolos |
| Payload do QR | o **código puro** (sem URL/indireção — DAT §8.3) |

- **Backend:** `domain/provas.py` é a fonte única (`CODIGO_REGEX`, `validar_codigo`,
  **`normalizar_codigo`** = `strip().upper()`).
- **Frontend:** `apps/web/src/lib/provas/codigo.ts` **espelha** o domínio
  (`CODIGO_REGEX`/`validarCodigo`/`normalizarCodigo`/`mascararResto`/`montarCodigo`). A máscara do
  input usa o **prefixo fixo `PRV-`** + `AAAA-MM-XXXXXX`; o cliente força maiúsculas e o **servidor
  normaliza** antes de validar — colar em minúsculas ou com `\n` do leitor ainda resolve.

---

## 3. Endpoint `POST /provas/identificar`

Prefixo real **`/provas`** (não `/api/provas`), seguindo C06/C07/C08.

**Entrada** (`IdentificarIn`): `{ "codigo": "<QR ou código manual>" }` (`max_length=100` — teto
anti-abuso; o código real tem ~18 chars).

**Saída (200):** `ProvaDetalheOut` (id, codigo, nome, requerimento, cliente, vendedor_id,
vendedor_nome, rota, status, ciclo_atual, created_at, finalizada_em) — o **mesmo shape do
detalhe**, para a tela de confirmação não precisar de um `GET` extra.

**Erros:**

| Status | code | Quando |
| --- | --- | --- |
| **404** | `prova_nao_encontrada` | código **malformado** OU **inexistente** OU **fora do escopo** — **mesma mensagem** ("Prova não encontrada.") |
| **429** | `limite_de_tentativas` | acima de **30 tentativas/usuário/minuto** |
| 401 | `http_error` | sem Bearer válido |
| 403 | `http_error` | sem linha `usuarios` / inativo / não autorizado (negação única) |
| 422 | `validation_error` | corpo sem `codigo` (forma) — não enumera nada |

### Fluxo do `ProvasIdentificacaoService.identificar`

1. **Rate limit primeiro:** `registrar_e_contar` conta a tentativa e o caso de uso **commita
   antes** de resolver — assim a tentativa conta **mesmo quando dá 404** (senão o rollback do 404
   zeraria o contador e furaria o limite). Acima do limite → **429**.
2. **Normaliza + valida o formato.** Malformado → **404** (sem nem consultar — não revela que não
   chegou a buscar).
3. **Resolve pelo código** (`buscar_por_codigo`, **escopado pela RLS**). Inexistente/fora do escopo
   → `None` → **404 genérico**.

> Nunca loga o código (não vaza o conteúdo escaneado — RNF-024): só `prova_id` no sucesso e a
> contagem no bloqueio.

---

## 4. Anti-enumeração + Rate limiting (DP-3 — ADR-054)

### 4.1 Anti-enumeração (RN-014)
Reuso do **`ProvaNaoEncontradaError`** do C08: código **inválido**, **inexistente** e **fora do
escopo** retornam o **mesmo 404 com a mesma mensagem**. Nada distingue os casos — sem canal lateral
(de status, mensagem ou existência). A RLS é o ponto de verdade do escopo.

### 4.2 Rate limiting — contador Postgres de janela fixa
Backend **stateless**, sem Redis (R$ 0). O estado vive no Postgres:

- **Tabela `rate_limit_contadores`** (migration **0014**): `(user_id, chave)` PK, `janela_inicio`,
  `contador`. **Uma linha por (ator, chave)**.
- **Upsert atômico** (`SqlAlchemyRateLimiter`): `INSERT ... ON CONFLICT DO UPDATE` que **incrementa**
  na janela de 1 min e **reseta** ao virar o minuto (`date_trunc('minute', now())`). Sem job de
  limpeza — o armazenamento é limitado ao nº de atores. O `user_id` vem de
  **`public.app_current_user_id()`** (claims), nunca de parâmetro.
- **RLS `rate_limit_contadores_self`** (`FOR ALL`): o ator só vê/grava a **própria** linha — defesa
  em profundidade (um ator nunca lê nem incrementa o contador de outro). `authenticated` recebe
  SELECT/INSERT/UPDATE; **sem DELETE**. Espelho em
  `migrations/rls/rate_limit_contadores_{grants,self}.sql`.
- **Limite:** `LIMITE_IDENTIFICACAO = 30`, `CHAVE_IDENTIFICACAO = "identificar"`
  (`application/provas.py`). A tabela é genérica — outros endpoints futuros usam outras chaves sem
  nova migration.

---

## 5. Fronteira C10 ↔ C11 ↔ C12 e destino pós-identificação (DP-2 — ADR-053)

- O C10 **só identifica** (`resolver_prova`). **NÃO** valida a próxima transição (C11) nem assina
  (C12).
- **Destino pós-identificação:** uma **nova tela de confirmação** em **`/provas/[id]/confirmar`**
  que mostra **nome + requerimento + status** da prova e um **placeholder de assinatura** (C12) com
  o botão "Confirmar movimentação" **desabilitado** (C11). A tela busca o detalhe por
  `GET /provas/{id}` (universal-em-escopo, mesmo padrão do C08), tratando 404 com toast genérico +
  volta ao escaneamento (anti-enumeração).
- O C11 e o C12 plugam exatamente neste cartão sem reescrever a identificação.

---

## 6. Frontend (mobile-first — DP-4/ADR-055)

Tela **`/escanear`** (`(app)/escanear/`), dentro do app shell, em **dois modos sempre acessíveis**
via toggle (radiogroup com pílula `layoutId`):

- **Câmera** (`camera-scanner.tsx`): `html5-qrcode` (stack do CLAUDE.md §4) por **import dinâmico
  client-only**; abre só por **gesto** ("Abrir câmera"); câmera **traseira** (`facingMode:
  "environment"`); lê em tempo real (≤ 2 s — RNF-002). **Degradação graciosa (RNF-014):** permissão
  negada / sem câmera **não bloqueia** — mostra o aviso e o **manual segue acessível**.
- **Manual** (`EntradaManual` em `escanear-view.tsx`): prefixo fixo `PRV-` + máscara
  `AAAA-MM-XXXXXX`; "Buscar prova" só habilita com o código válido.
- **Feedback de sucesso:** flash leve (`transform`/`opacity`) antes de navegar; instantâneo sob
  `prefers-reduced-motion`.
- **Rodapé (DP-5/ADR-056):** "Última leitura há X min" = indicador **local/sessão** (sem persistência
  no C10); "Ver histórico" = **placeholder** (a timeline é do C13).

**Diretrizes mobile-first aplicadas (RF-029/US-020):** CSS **mobile-first** (base 360px+, `@media
(min-width:768px)` recompõe o layout de 2 colunas do design no desktop); touch targets **≥ 48px**;
**safe areas** via `env()` (notch/gestos); **botões principais no terço inferior** (`margin-top:auto`
no mobile, resetado no desktop); contraste **AA**; portrait e landscape.

---

## 7. Arquivos

**Backend**
- `domain/provas.py` — `normalizar_codigo`, `LimiteDeTentativasError` (429).
- `application/ports/rate_limiter.py` — `RateLimiterPort`.
- `adapters/outbound/db/rate_limiter.py` — `SqlAlchemyRateLimiter` (upsert atômico).
- `application/ports/provas_repository.py` + `adapters/outbound/db/provas_repository.py` —
  `buscar_por_codigo` (resolução por código, RLS-escopada).
- `application/provas.py` — `ProvasIdentificacaoService` (+ `LIMITE_IDENTIFICACAO`,
  `CHAVE_IDENTIFICACAO`).
- `adapters/inbound/http/dependencies.py` — `get_identificacao_service` (gate `Recurso.ESCANEAR`).
- `adapters/inbound/http/provas.py` — `IdentificarIn` + `POST /provas/identificar`.
- `adapters/inbound/http/errors.py` — `LimiteDeTentativasError` → 429.
- `adapters/outbound/db/models.py` — `RateLimitContadorRow` (espelho de schema).
- `migrations/versions/0014_rate_limit_identificacao.py` + `migrations/rls/rate_limit_contadores_*.sql`.

**Frontend**
- `lib/provas/codigo.ts` — espelho do formato do C06.
- `lib/api/escaneamento.ts` — `identificarProva`.
- `app/(app)/escanear/{page.tsx, escanear.module.css, _components/{escanear-view,camera-scanner}.tsx}`.
- `app/(app)/provas/[id]/confirmar/{page.tsx, confirmar.module.css, _components/confirmar-view.tsx}`.

---

## 8. Testes

```bash
# Backend (@db usa a mesma TEST_DATABASE_URL das demais waves)
uv run pytest tests/unit/test_provas_identificacao.py \
  tests/integration/test_provas_identificacao_endpoints.py \
  tests/integration/test_rls_rate_limit.py

# Frontend
pnpm test        # codigo.test.ts, escanear-view.test.tsx, confirmar-view.test.tsx
pnpm test:e2e    # e2e/escanear.spec.ts (redirect sempre; live opt-in via E2E_LIVE=1)
```

Cobre: QR e manual → **mesmo registro** (idempotente); **anti-enumeração** (inválido == inexistente
== fora-de-escopo, mensagem idêntica); **rate limit 429** + **isolamento por usuário**; **RLS do
contador** (incremento na janela + um ator não vê o outro + WITH CHECK + sem DELETE); **degradação
graciosa** da câmera; máscara/validação do formato do C06; navegação à confirmação.

---

## 9. Checklist de aceitação (§6 do prompt)

- [x] Identifica QR em ≤ 2 s após o foco (RNF-002); leitura **in-app** sem app externo (RF-004).
- [x] Fluxo **manual sempre acessível**; **câmera negada não bloqueia** (RNF-014).
- [x] Código **inválido e fora do escopo** → **mesma mensagem genérica** (RN-014); **rate limit
  30/usuário/min** ativo.
- [x] **QR e manual** resolvem o **mesmo registro** pelo mesmo caminho (idempotente); resolução
  respeita a **RLS**.
- [x] Input manual usa o **formato do C06** (DP-1); o parser do QR lê o payload puro.
- [x] **Mobile-first** (360–768px, portrait/landscape, touch ≥ 48, safe areas, terço inferior, AA).
- [x] Pós-identificação navega ao destino (DP-2); o C10 **não** transiciona nem assina; **flash** com
  `prefers-reduced-motion`.
- [x] **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/
  `pnpm lint`/`build` verdes.
