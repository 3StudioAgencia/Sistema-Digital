# Remediação da Wave 0 — Log (W0-REMEDIATION)

> Sessão de **correção** (modifica código) consumindo os achados de
> [`wave-0-audit.md`](./wave-0-audit.md). Cada correção é mínima, testada e
> aderente ao `CLAUDE.md`, com rastreabilidade `achado → correção → evidência`.

## 1. Cabeçalho

| Campo | Valor |
| --- | --- |
| **Data** | 2026-06-11 |
| **Branch** | `develop` (ADR-016) |
| **Commit de origem (auditado)** | `54ae345` |
| **Commit pós-remediação (HEAD)** | `2d5ba95` |
| **Relatório de origem** | [`docs/audits/wave-0-audit.md`](./wave-0-audit.md) (29 achados: 0 Blocker · 0 High · 2 Medium · 16 Low · 11 Nit) |
| **Ambiente de verificação** | Windows 11 · Python 3.12 (uv 0.11) · PostgreSQL **16.9** real (binários portáteis, porta 5433; o Supabase real **não** foi tocado) · pnpm 11.5.3 / Node 22 |
| **Gate de re-verificação (§5 do prompt)** | ✅ **VERDE** (detalhe na §3) |

---

## 2. Tabela achado → status

> Convenção de status: **Resolvido** (corrigido + verificado) · **Resolvido (documental)** (decisão registrada em ADR; movimentação de código planejada) · **Ação do responsável** (operacional, fora do alcance desta sessão) · **Parcial + dívida** (parte resolvida, parte adiada com motivo).

| ID | Sev. | Status | Commit | Evidência da correção |
| --- | --- | --- | --- | --- |
| **W0-A-001** | Medium | **Ação do responsável** | — | Decisão do responsável (pergunta da sessão): **ele cadastrará o secret `KEEPALIVE_DATABASE_URL`** no GitHub. O workflow permanece **fail-loud** (correto assim que o secret existir). Caminho documentado em `docs/keep-alive.md §6` (corrigido — W0-A-006) e checklist do ADR-016. **Não é correção de código.** |
| **W0-A-002** | Medium | **Resolvido** | `3e14467` | `ci.yml`: `on.push.branches: [main, develop]`. Decisão do responsável: "adicionar develop ao push". Checklist do ADR-016 fechado. |
| **W0-A-003** | Low | **Resolvido** | `4fb95ee` | `ping()`/`R2Storage.health()`/checks do readiness logam `WARNING` com `error_type` (nunca `str(exc)`). Testes: `test_database_offline`, `test_r2_mapeamento_de_erros`, `test_health`. |
| **W0-A-004** | Low | **Resolvido** | `4fb95ee` | `BotoConfig` com `connect_timeout/read_timeout=5` + `max_attempts=1`. Teste `test_from_settings_define_timeouts_explicitos`. |
| **W0-A-005** | Low | **Resolvido** | `952d5ab` | `Settings(hide_input_in_errors=True)` + `get_settings()` dentro do contrato de erro do `main()`. Testes de não-vazamento em `test_config`/`test_keep_alive`. |
| **W0-A-006** | Low | **Resolvido** | `2d5ba95` | `keep-alive.md §6` passo 3: schedule roda da **branch padrão** (`develop`), não `main`. |
| **W0-A-007** | Low | **Resolvido** | `2d5ba95` | Emenda da **ADR-013** + docstrings de `errors.py` (catch-all = `ErrorHandlingMiddleware` interno ao CORS; demais = redes de segurança). |
| **W0-A-008** | Low | **Resolvido** | `3e14467` | Actions de terceiros **pinadas por SHA** (checkout/setup-uv/action-setup/setup-node) nos dois workflows + `.github/dependabot.yml` (github-actions/pip/npm). Exemplo de deploy deixa de citar `@master`. *(Digest de imagem Docker → ver W0-A-029.)* |
| **W0-A-009** | Low | **Resolvido** | `3e14467` | keep-alive: `uv sync --frozen --no-dev` **e** `uv run --no-dev`. Validado: ping `exit 0` sem o grupo dev. |
| **W0-A-010** | Low | **Resolvido** | `3e14467` | `permissions: contents: read` no `ci.yml`. |
| **W0-A-011** | Low | **Resolvido** | `3e14467` | Passo `pnpm format:check` no job web. |
| **W0-A-012** | Low | **Resolvido** | `76bdbaf` | Fixture autouse `_isola_env_do_settings` (delenv de todas as chaves do Settings). Verde inclusive com `DATABASE_URL`/`APP_ENV` exportados (como no CI). |
| **W0-A-013** | Low | **Resolvido** | `76bdbaf` | `LOG_LEVEL` validado no Settings (strip+upper contra a lista canônica). Testes de normalização e rejeição. |
| **W0-A-014** | Low | **Resolvido** | `3368a90` | Downgrade da baseline só dropa `pgcrypto` em `APP_ENV` dev/test; no-op em staging/produção. Teste @db do caminho de produção + ciclo dev verde. |
| **W0-A-015** | Low | **Resolvido** | `7413ddb` | Settings rejeita `"*"` em `CORS_ALLOWED_ORIGINS`. Teste `test_origem_curinga_rejeitada`. |
| **W0-A-016** | Low | **Resolvido** | `7413ddb` | `X-Content-Type-Options: nosniff` + `Cache-Control: no-store` em toda resposta. Teste de security headers. |
| **W0-A-017** | Low | **Resolvido** | `50e9b99` | `ApiStatus` valida `response.ok\|503` + shape (type guard); novo `app/error.tsx` + CSS module. `pnpm lint`/`build`/`format:check` verdes. |
| **W0-A-018** | Low | **Resolvido (documental)** | `2d5ba95` | **ADR-017**: implementações de porta de DB (UoW/repositórios) → `adapters/outbound/db/`. Movimentação física na **Wave 2 (C06)**, conforme o próprio achado ("resolver documentalmente; não mover código agora"). |
| **W0-A-019** | Nit | **Resolvido** | `2d5ba95` | `CLAUDE.md §5.1` inclui `tasks/`. |
| **W0-A-020** | Nit | **Resolvido** | `2d5ba95` | `.env.example`: staging/produção DEVEM definir `APP_ENV`. |
| **W0-A-021** | Nit | **Resolvido** | `2d5ba95` | `.env.example`: caveat IPv6-only da conexão direta + formato do pooler em modo session. |
| **W0-A-022** | Nit | **Resolvido** | `561bed6` | `coerce_asyncpg_url` público (consumido por `env.py`/`conftest`). |
| **W0-A-023** | Nit | **Resolvido** | `7413ddb` | `X-Request-ID` recebido passa por whitelist `^[A-Za-z0-9._-]{1,128}$`; fora do padrão → uuid4. Teste correspondente. |
| **W0-A-024** | Nit | **Resolvido** | `3e14467` | `concurrency` (cancel-in-progress) no `ci.yml`. |
| **W0-A-025** | Nit | **Resolvido** | `561bed6` | Fixture local `_restaura_logging` removida (conftest já tem a autouse). |
| **W0-A-026** | Nit | **Resolvido** | `561bed6` | Teste offline duplicado removido de `integration/test_database.py`. |
| **W0-A-027** | Nit | **Resolvido** | `561bed6` | `apps/api/tests/e2e/` criada (README reservado p/ Playwright, Wave 2+). |
| **W0-A-028** | Nit | **Resolvido** | `2d5ba95` | `README`: ADR-010 (gerenciadores) Aceita; só ADR-009 (deploy) revisável. |
| **W0-A-029** | Nit | **Parcial + dívida** | `561bed6` | **Feito:** `--chown` removido do Dockerfile (código/venv root:root, não graváveis pelo runtime). **Adiado (dívida):** pinagem das **imagens base por digest** — sem Docker no ambiente para resolver/validar o digest, exposição nula até o deploy (a CI não builda a imagem) e a renovação exigiria Dependabot-docker; comentário no Dockerfile registra a recomendação. |

---

## 3. Resumo

### 3.1 Contagem por severidade

| Severidade | Total | Resolvido | Resolvido (documental) | Ação do responsável | Parcial + dívida |
| --- | --- | --- | --- | --- | --- |
| **Blocker** | 0 | — | — | — | — |
| **High** | 0 | — | — | — | — |
| **Medium** | 2 | 1 (W0-A-002) | — | 1 (W0-A-001) | — |
| **Low** | 16 | 15 | 1 (W0-A-018) | — | — |
| **Nit** | 11 | 10 | — | — | 1 (W0-A-029) |
| **Total** | **29** | **26** | **1** | **1** | **1** |

Nenhum achado emergente novo (`W0-A-101+`) surgiu durante as correções.

### 3.2 Resultado do gate de re-verificação (§5)

| Checagem | Resultado |
| --- | --- |
| `ruff check` · `ruff format --check` | ✅ All checks passed · 43 files formatted |
| `mypy` (strict, config do pyproject) | ✅ Success: no issues found in 26 source files |
| Alembic `upgrade head → downgrade -1 → upgrade head` (PG real) | ✅ up=OK · down=OK · up=OK |
| `pytest --cov` (`REQUIRE_DB_TESTS=1`) | ✅ **88 passed** · cobertura **100%** (piso 80) |
| keep-alive contra DB local (`uv run --no-dev`) | ✅ `status="ok"`, exit 0 |
| Domínio sem imports de framework | ✅ `OK: domain limpo` |
| Varredura de segredos | ✅ só nomes de variáveis/placeholders fictícios — nenhum segredo real |
| `pnpm install --frozen-lockfile` · `lint` · `format:check` · `build` | ✅ todos exit 0 (Compiled successfully) |
| Lockfiles versionados | ✅ `apps/api/uv.lock` · `apps/web/pnpm-lock.yaml` |

**Critérios do gate:** ✅ Zero Blocker e zero High em aberto · ✅ itens `FAIL`/`PARTIAL` tratados agora verdes · ✅ todas as checagens verdes · ✅ nenhuma regressão (nada que era `PASS` virou `FAIL`; suíte foi de 70→88 testes, cobertura mantida em 100%).

### 3.3 Itens que dependem do responsável (não são código)

1. **W0-A-001 — cadastrar o secret `KEEPALIVE_DATABASE_URL`** (Settings → Secrets and variables → Actions) com a connection string do Supabase (mesma de `MIGRATIONS_DATABASE_URL`) e validar via `workflow_dispatch`. Enquanto não cadastrado, o cron diário falha (vermelho) e o Supabase fica desprotegido contra a pausa de 7 dias. Guia: `docs/keep-alive.md §6`.

### 3.4 Dívida técnica registrada (adiada com motivo)

1. **W0-A-029 (Nit) — pinagem das imagens base do Dockerfile por digest.** Motivo: sem Docker no ambiente de dev para resolver/validar o digest; exposição nula até o deploy (a CI não builda a imagem); renovação demanda Dependabot-docker. Recomendação registrada em comentário no `apps/api/Dockerfile`. Reavaliar ao definir a plataforma de deploy (ADR-009).
2. **W0-A-018 (Low) — movimentação física da UoW** para `adapters/outbound/db/`: decidida (ADR-017), a executar na **Wave 2 (C06)** junto com os primeiros repositórios.

---

## 4. Commits da remediação (em `develop`)

```
4fb95ee fix(w0-a-003,w0-a-004)  readiness diagnostico + R2 timeouts
952d5ab fix(w0-a-005)           keep-alive nao vaza connection string
76bdbaf fix(w0-a-012,w0-a-013)  hermeticidade da suite + LOG_LEVEL validado
7413ddb fix(w0-a-015,016,023)   hardening HTTP (CORS/headers/request-id)
3368a90 fix(w0-a-014)           downgrade defensivo da baseline
50e9b99 fix(w0-a-017)           status page: shape guard + error.tsx
3e14467 ci(w0-a-002,008..011,024) gatilho develop + hardening dos workflows
561bed6 refactor(w0-a-022,025,026,027,029) nits de testes/convencao/Dockerfile
2d5ba95 docs(w0-a-006,007,018,019,020,021,028) pacote de docs/ADRs
```

**Próximo passo:** retomar a **Wave 1 · W1-C03 (Tela de Login e Sessão)** na branch `develop` — após o responsável cadastrar o secret do keep-alive (W0-A-001).
