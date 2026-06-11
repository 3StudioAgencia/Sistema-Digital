# Auditoria da Wave 0 — Relatório (W0-AUDIT)

> Sessão de auditoria **read-only**: este relatório inspeciona, verifica e relata — **nenhuma correção foi aplicada**. Os IDs `W0-A-NNN` são estáveis e alimentam a sessão de remediação.

---

> ## ✅ Status pós-remediação (2026-06-11)
>
> Todos os 29 achados foram **endereçados** na sessão de remediação — log completo, evidências e gate em **[`wave-0-remediation.md`](./wave-0-remediation.md)**. Gate de re-verificação **VERDE** (88 testes, cobertura 100%, lint/types/migrations/build verdes, sem segredos).
>
> **Status por achado** (`R` = Resolvido · `RD` = Resolvido documental, código na Wave 2 · `AR` = Ação do responsável · `PD` = Parcial + dívida registrada):
>
> | Achado | St. | Achado | St. | Achado | St. | Achado | St. |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | W0-A-001 | **AR** | W0-A-009 | R | W0-A-016 | R | W0-A-023 | R |
> | W0-A-002 | R | W0-A-010 | R | W0-A-017 | R | W0-A-024 | R |
> | W0-A-003 | R | W0-A-011 | R | W0-A-018 | **RD** | W0-A-025 | R |
> | W0-A-004 | R | W0-A-012 | R | W0-A-019 | R | W0-A-026 | R |
> | W0-A-005 | R | W0-A-013 | R | W0-A-020 | R | W0-A-027 | R |
> | W0-A-006 | R | W0-A-014 | R | W0-A-021 | R | W0-A-028 | R |
> | W0-A-007 | R | W0-A-015 | R | W0-A-022 | R | W0-A-029 | **PD** |
> | W0-A-008 | R | | | | | | |
>
> **Pendências pós-remediação:** `W0-A-001` (responsável cadastra o secret `KEEPALIVE_DATABASE_URL`) e a dívida `W0-A-029` (digest das imagens Docker, ao definir o deploy). A **matriz de conformidade (§3)** abaixo reflete o estado da auditoria; o estado pós-correção dos itens `PARTIAL`/`FAIL` (C01-6, C02-1, 4.8/4.9) está no log de remediação.

## 1. Cabeçalho

| Campo | Valor |
| --- | --- |
| **Data** | 2026-06-11 |
| **Escopo** | W0-C01 (Infraestrutura) · W0-C02 (Keep-Alive) |
| **Commit auditado** | `54ae345` (`docs(w0-c02): registra publicacao no GitHub e modelo de branches (ADR-016)`) |
| **Branch** | `develop` (padrão — ADR-016) |
| **Ambiente de verificação** | Windows 11 Pro · Python 3.12 via uv (lockfile congelado) · pnpm 11.5.3 / Node 22 · **PostgreSQL 17.10 real** (binários portáteis zonky, porta 5433 — a máquina não tem Docker; mesmo procedimento da validação do W0-C01) |
| **Método** | Checklist §4 do prompt W0-AUDIT, verificações executáveis (§5) contra Postgres real + revisão multi-agente (12 auditores por dimensão × verificação adversarial cética de cada achado) |

**Limitação de escopo declarada:** os documentos originais *Requisitos v1.0*, *Backlog v1.0* e *DAT v3.0* **não estão no repositório**. A auditoria usou como proxy normativo o `CLAUDE.md` (que consolida hierarquia, pilares, stack e DoD) e os prompts `PROMPTS/W0-C01-infraestrutura.md` / `PROMPTS/W0-C02-keep-alive.md` (que transcrevem escopo, critérios de aceitação e testes do Backlog C01/C02). Referências a RNF/critérios abaixo são mediadas por esses arquivos.

---

## 2. Veredito executivo

**A Wave 0 está pronta para servir de base à Wave 1. A continuidade NÃO está bloqueada.**

A fundação é sólida e fiel à especificação: arquitetura hexagonal respeitada (domínio puro, portas abstratas, composition root único), stack exata do DAT com versões pinadas, estratégia de conexão do ADR-007 implementada e validada contra Postgres 17.10 real (ciclo Alembic completo em banco limpo), observabilidade com log JSON correlacionado por `request_id`, health checks com degradação clara, keep-alive externo DRY com fail-loud comprovado (exit 0/1, sem vazamento de credencial), zero segredos versionados, e **todas as verificações executáveis verdes** (ruff, ruff format, mypy strict, pytest 76/76 com banco real e cobertura 100%, pnpm lint/build).

| Severidade | Quantidade |
| --- | --- |
| **Blocker** | **0** |
| **High** | **0** |
| **Medium** | **2** |
| **Low** | **16** |
| **Nit** | **11** |
| **Total** | **29** *(36 achados brutos dos auditores; 7 eram duplicatas entre dimensões, consolidadas)* |

Os 2 achados **Medium** não são defeitos de código — são **handoffs operacionais já registrados como pendência (ADR-016) porém não executados**, e ambos têm prazo implícito:

1. **W0-A-001** — o cron diário do keep-alive está armado na branch padrão **sem** o secret `KEEPALIVE_DATABASE_URL`: falha vermelha todo dia (fadiga de alerta) e o Supabase real segue desprotegido contra a pausa de 7 dias (~2026-06-18 se ninguém tocar o banco).
2. **W0-A-002** — o CI não dispara em push para `develop` (branch padrão de integração): o HEAD atual de `develop` nunca rodou no CI do GitHub; precisa de decisão antes de a Wave 1 começar a integrar código por ali.

Todos os achados de severidade Low/Nit são dívidas pontuais de hardening, observabilidade ou consistência documental, com correções de esforço P (pequeno) em sua quase totalidade.

---

## 3. Matriz de conformidade

### 3.1 Critérios de aceitação — W0-C01 (Backlog C01 §5, via prompt §5)

| # | Critério | Veredito | Evidência |
| --- | --- | --- | --- |
| C01-1 | `alembic upgrade head` aplica em ambiente limpo; `downgrade` funciona | **PASS** | Executado nesta auditoria contra PG 17.10 limpo (porta 5433): `upgrade head` → `downgrade base` → `upgrade head`, todos exit 0; `pgcrypto` instalada; nenhuma tabela de domínio (apêndice A.4) |
| C01-2 | Upload e leitura via porta de storage comprovados por teste (moto/fake) + instruções p/ R2 real | **PASS** | `tests/unit/test_storage.py` (moto + fake, roundtrip upload→download) na suíte verde; roteiro R2 real em `docs/setup-infra.md` §5; roundtrip real executado no W0-C01 (SESSION_LOG sessão 01) |
| C01-3 | Health checks respondendo (RNF-024) | **PASS** | Smoke test desta auditoria: `GET /health` → 200 `{"status":"ok"}`; `GET /health/ready` → 503 `degraded` com `{"database":"ok","storage":"down"}` sem R2 (degradação clara); apêndice A.6 |
| C01-4 | Variáveis sensíveis fora do código; `.env.example` cobre todas as chaves | **PASS** | `git grep` de segredos: só credenciais fictícias de teste e `postgres:postgres` local de CI/compose; `.env` jamais commitado (histórico vazio); `.env.example` das duas apps cobre todos os campos do `Settings` e todos os `process.env` do web (apêndice A.2) |
| C01-5 | Custo-alvo R$ 0 | **PASS** | Supabase free + R2 free + GitHub Actions free; deploy proposto (Vercel/Fly) free tier (ADR-009, ainda Proposta); nenhuma escolha paga encontrada |
| C01-6 | `ruff`, `mypy (strict)`, `pytest`, `pnpm build/lint` verdes localmente e no CI | **PARTIAL** | Localmente todos verdes (apêndice A.3/A.5); o pipeline do CI espelha exatamente esses passos, **mas o HEAD de `develop` nunca executou no CI do GitHub** (gatilho de push só em `main` — achado **W0-A-002**) |
| C01-7 | Backend sobe com uvicorn e expõe `/docs` | **PASS** | Smoke test: `GET /docs` → 200 (apêndice A.6) |
| C01-8 | Regra hexagonal respeitada; `main.py` único composition root | **PASS** | `src/domain` sem nenhum import (grep vazio); portas ABC em `application/ports/`; concreto↔abstrato somente em `src/main.py:29-64`; `create_app()` recebe tudo injetado. Ressalva de colocação do `SqlAlchemyUnitOfWork` (W0-A-018, Low) |

### 3.2 Critérios de aceitação — W0-C02 (Backlog C02 §5, via prompt §5)

| # | Critério | Veredito | Evidência |
| --- | --- | --- | --- |
| C02-1 | Projeto Supabase permanece ativo > 7 dias (caminho pronto e documentado) | **PARTIAL** | Workflow agendado correto e validado em execução real (ADR-015); porém o secret `KEEPALIVE_DATABASE_URL` **não está cadastrado** — o cron falha diariamente e a proteção real está inativa (**W0-A-001**). O prompt aceita "caminho pronto", mas o estado publicado não é neutro: gera falha visível todo dia |
| C02-2 | Frequência mínima que mantém ativo (sem polling excessivo) | **PASS** | `0 9 * * *` diário (06:00 BRT) = ~7× de margem sobre 7 dias; racional documentado em `docs/keep-alive.md` §4; sem frequência sub-horária (RNF-023) |
| C02-3 | Falha registrada e alertada (RNF-024) | **PASS** | Demonstrado nesta auditoria: credencial inválida → log JSON `status="error"` apenas com `error_type` + **exit 1** (apêndice A.7); workflow vermelho → notificação nativa; webhook opcional gated por `if: failure()` + secret |
| C02-4 | Rotina roda offline com Postgres local (sucesso) e falha controlada | **PASS** | Executado: sucesso contra PG local 5433 (exit 0, todos os campos do contrato) e falha controlada (exit 1, senha ausente do log) — apêndice A.7 |
| C02-5 | `ruff`, `mypy (strict)`, `pytest` verdes; sem segredos versionados | **PASS** | Apêndice A.3; varredura de segredos limpa (A.2) |
| C02-6 | Reuso real do ping do C01 (sem duplicação de lógica de banco) | **PASS** | Núcleo único `fetch_db_time()` em `database.py:76-89`, consumido por `ping()` (readiness, :92-98) e pelo keep-alive (`keep_alive.py:60`); nenhuma segunda ida ao banco existe |

### 3.3 Checklist de dimensões (§4 do prompt de auditoria) — visão consolidada

| Dimensão | Resultado | Observações |
| --- | --- | --- |
| 4.1 Arquitetura hexagonal | **PASS** (1 item PARTIAL) | Domínio puro; portas/adapters corretos; composition root único. PARTIAL: `UnitOfWork` implementada em `infrastructure/` e não em `adapters/outbound/` (W0-A-018 — colocação mandada pelo próprio prompt C01, tensão documental) |
| 4.2 Stack e versões | **PASS** | Python 3.12 (`.python-version`), FastAPI/SQLAlchemy 2 async/Pydantic v2/Alembic/boto3; PyJWT 2.13 sem `python-jose`; Next 16.2.9 + React 19.2.4 exatos; TS `strict: true`; CSS Modules sem framework externo; lockfiles versionados |
| 4.3 Configuração e segredos | **PASS** (1 item PARTIAL) | Zero segredos; `.env.example` completos; `Settings` valida no boot (R2 tudo-ou-nada). PARTIAL: `LOG_LEVEL` não validado no Settings (W0-A-013) |
| 4.4 Banco/conexão/migrations | **PASS** (1 item PARTIAL) | Duas URLs; NullPool + ambos os caches de prepared statement off; env.py async na direta; `alembic.ini` ASCII puro (0 bytes não-ASCII — A.8); ciclo completo verde; baseline sem domínio; `migrations/rls/` com README e sem `.sql` (correto). PARTIAL: downgrade dropa pgcrypto sem guarda (W0-A-014) |
| 4.5 Storage/R2 | **PASS** | Porta + adapter com cliente injetado; erros mapeados (`NoSuchKey`→`StorageObjectNotFound`); sem credencial hardcoded; testes moto/fake verdes. Achados Low de timeout/log (W0-A-003/004) |
| 4.6 Observabilidade | **PASS** | JSON estruturado + `ContextVar`; `X-Request-ID` em toda resposta (comprovado inclusive reuso do inbound); CRITICAL correlacionado sem stack trace ao cliente (ADR-013) |
| 4.7 Health checks | **PASS** | Liveness 200 imediato sem dependências; readiness paralelo com timeout 5s, 200/503 e `checks` por dependência (smoke test A.6). `SELECT now()` ≡ `SELECT 1` (trivial read-only) |
| 4.8 Keep-alive | **PASS** (2 FAIL operacionais/doc) | Externo, DRY, read-only, log completo, fail-loud sem vazamento — tudo comprovado. FAIL: secret ausente com cron armado (W0-A-001); doc §6 "push para main" impreciso (W0-A-006) |
| 4.9 CI/CD | **PARTIAL** | Jobs api/web completos e fiéis; deploy parametrizável sem segredos. FAIL: gatilho não cobre `develop` (W0-A-002); Lows de hardening (W0-A-008/010/011/024) |
| 4.10 Testes/cobertura | **PASS** (1 item PARTIAL) | Todos os testes de C01 §6 e C02 §6 mapeados e presentes; suíte offline (70 passed/6 skipped) e com banco real (76 passed, cobertura 100%). PARTIAL: hermeticidade contra env vars do processo incompleta (W0-A-012) |
| 4.11 Docs e contexto | **PASS** (2 itens PARTIAL) | Protocolo de Encerramento cumprido nas duas sessões; ADR-003/007/010 confirmados, 012–016 registrados. PARTIAL: ADR-013 descreve desenho pré-fix (W0-A-007); keep-alive.md §6 impreciso (W0-A-006) |
| 4.12 Pilares | **PASS** | Stateless (config/adapters em `app.state` são wiring, não sessão; logs em stdout); mínimo de requisições (1 fetch na página de status, sem polling); robustez (degradação clara); custo R$ 0. Gap novo: readiness silencioso (W0-A-003) |

### 3.4 Definition of Done aplicável (CLAUDE.md §8)

| Item da DoD | Veredito | Evidência |
| --- | --- | --- |
| Code review aprovado | **PASS** | Revisão adversarial multi-agente nas duas sessões (SESSION_LOG 01/02; 8 achados corrigidos no C01). Nota: sem PR formal — fluxo de push direto (ver W0-A-002) |
| Testes unitários ≥ 80% (domínio/serviço) | **PASS** | 98,81% offline / **100%** com banco real (piso 80 configurado e aplicado); ≥95% máquina de estados **N/A** (não existe na Wave 0) |
| Testes de integração em ambiente isolado | **PASS** | `tests/integration/` contra PG real isolado (`rastreio_test`); gate `REQUIRE_DB_TESTS=1` no CI. Ressalva W0-A-012 (env vars do processo) |
| Migrations aplicadas, versionadas e documentadas | **PASS** | `0001_baseline` versionada, ciclo completo demonstrado (A.4), documentação em docs/README |
| Validado contra critérios de aceitação | **PASS/PARTIAL** | Ver §3.1/§3.2 (2 PARTIAL: C01-6 e C02-1) |
| Validado contra Matriz de Acesso | **N/A** | RBAC chega na Wave 1/C05; nenhum endpoint com escopo de perfil existe |
| Sem erros no console / logs críticos | **PASS** | Suíte sem warnings; smoke test sem log crítico; build web limpo |
| Documentação interna atualizada | **PASS** | READMEs de módulo presentes e fiéis; docs/ atualizada (Lows documentais apontados) |
| Políticas RLS versionadas | **N/A (correto)** | `migrations/rls/README.md` fixa a política; nenhum `.sql` ainda — exatamente o esperado na Wave 0 |
| Animações com `prefers-reduced-motion` | **N/A** | Nenhuma animação na Wave 0 (CSS da fundação sem `transition`/`animation`) |
| Escritas idempotentes (RNF-015) | **N/A** | Nenhuma escrita de domínio; keep-alive é read-only por construção |
| Sem N+1; mínimo de requisições | **PASS** | 1 consulta única no readiness da página de status; keep-alive 1 SELECT/dia |
| Error boundaries cobrindo a rota | **PARTIAL** | Não há `error.tsx`/`global-error.tsx` no App Router; o prompt C01 tratava o health da página como "opcional, com fallback amigável", mas um JSON de shape inesperado derruba a renderização (W0-A-017) |
| Protocolo de encerramento executado | **PASS** | CHANGELOG/DECISIONS/SESSION_LOG/README/CLAUDE.md §9 atualizados nas duas sessões |

---

## 4. Achados

> Severidades já calibradas pela verificação adversarial (cada achado foi conferido por um segundo agente cético, com acesso ao código; 2 achados originalmente High foram rebaixados a Medium por serem pendências documentadas; 3 foram rebaixados de Medium/Low para Low/Nit por impacto menor que o narrado).

### Medium

---

#### W0-A-001 — Cron do keep-alive armado na branch padrão sem o secret: falha diária e Supabase real desprotegido

- **Severidade:** Medium · **Categoria:** 4.8 Keep-alive / 4.9 CI-CD (operacional) · **Esforço:** P
- **Evidência:** [keep-alive.yml:30](../../.github/workflows/keep-alive.yml) (`- cron: "0 9 * * *"`, ativo na branch padrão `develop` desde o push `abc293c`); [keep-alive.yml:69-70](../../.github/workflows/keep-alive.yml) (`MIGRATIONS_DATABASE_URL`/`DATABASE_URL` ← `secrets.KEEPALIVE_DATABASE_URL`); `DECISIONS.md:115` (checkbox aberto: "cadastrar o secret KEEPALIVE_DATABASE_URL"); `SESSION_LOG.md:57` ("o cron diário (06:00) falha sem ele"). Sem o secret, as URLs chegam vazias e o `Settings` (campos obrigatórios, `config.py:51-53`) aborta → run vermelho todo dia.
- **Esperado:** o componente cuja única função é impedir a pausa de 7 dias do Supabase (RNF-011) operante, com alerta de falha **significativo** (RNF-024). O critério C02 §5.1 aceita "caminho pronto e documentado", mas o repositório foi publicado com o schedule **armado** — o estado entregue não é neutro.
- **Atual:** desde 2026-06-11 o workflow roda às 09:00 UTC e falha diariamente: notificação nativa de falha vira ruído (fadiga de alerta — uma falha real fica indistinguível, anulando o valor do RNF-024) enquanto o Supabase real validado no C01 permanece sem proteção. Se nada tocar o banco remoto por 7 dias (~2026-06-18), o projeto pausa — exatamente o cenário que o C02 existe para impedir.
- **Referência:** RNF-011, RNF-023/024; ADR-015/ADR-016 (DECISIONS.md:94-105); PROMPTS/W0-C02 §5.1 e lembrete final ("um keep-alive que falha sem avisar é pior do que não ter").
- **Correção recomendada:** primeira ação operacional pós-auditoria: cadastrar `KEEPALIVE_DATABASE_URL` (Settings → Secrets and variables → Actions) e validar com `workflow_dispatch` (roteiro em `docs/keep-alive.md` §6). Se o cadastro não puder ser imediato, **desabilitar temporariamente o workflow** pela UI do Actions para não acumular falhas diárias.

---

#### W0-A-002 — CI não dispara em push para `develop`: o HEAD da branch de integração nunca rodou no CI do GitHub

- **Severidade:** Medium · **Categoria:** 4.9 CI/CD · **Esforço:** P
- **Evidência:** [ci.yml:10-13](../../.github/workflows/ci.yml) — `on: push: branches: [main]` + `pull_request:`. ADR-016 (DECISIONS.md:103-105) define `develop` como branch padrão/integração e reconhece a lacuna ("pushes diretos em develop NÃO acionam a CI"); o fluxo até aqui foi push direto (sem PRs), logo o HEAD `54ae345` de `develop` jamais foi validado pelo CI do GitHub.
- **Esperado:** a branch onde os componentes integram deve ser gated por CI — `develop` em `on.push.branches` **ou** fluxo PR-only com branch protection. O critério C01 §5.6 exige as verificações "verdes localmente **e no CI**"; a DoD global pressupõe verificação contínua por componente.
- **Atual:** o delta atual de `develop` vs `main` é docs-only (risco imediato baixo — e esta auditoria executou localmente tudo que o CI roda, com sucesso), mas a partir da Wave 1 todo componente entrará por `develop` sem nenhuma execução de CI, esvaziando o critério "verde no CI" da DoD. Pendência registrada (ADR-016 checklist) porém não decidida.
- **Referência:** ADR-016 consequência 1 (DECISIONS.md:105, 115); PROMPTS/W0-C01 §5.6; CLAUDE.md §8.
- **Correção recomendada:** resolver o item pendente do ADR-016 **antes de abrir a Wave 1**: opção mínima = adicionar `develop` a `on.push.branches` (1 linha); opção mais forte = manter push só em `main` e ativar branch protection em `develop` exigindo PR com status check. Registrar a escolha fechando o checkbox em DECISIONS.md.

### Low

---

#### W0-A-003 — Readiness degrada para "down" sem registrar a causa nos logs

- **Severidade:** Low · **Categoria:** 4.5 Storage / 4.12 Pilares (observabilidade) — consolidação de 2 achados · **Esforço:** P
- **Evidência:** [database.py:92-98](../../apps/api/src/infrastructure/database.py) (`ping()`: `except Exception: return False`, sem log); [health.py:35-51](../../apps/api/src/adapters/inbound/http/health.py) (`_check_database`/`_check_storage`: `except Exception: return "down"`, sem log); [r2_storage.py:89-94](../../apps/api/src/adapters/outbound/storage/r2_storage.py) (`health()`: `except ...: return False`). O único rastro em stdout de um 503 é o access log com `status_code` — sem causa.
- **Esperado:** pilar 5 (RNF-024): uma dependência reportada como `down` deixa rastro diagnóstico no log — ao menos o **tipo** da exceção, como o próprio keep-alive já faz (`error_type` sem `str(exc)`, `keep_alive.py:79-88`).
- **Atual:** quando banco ou storage caem no readiness, a exceção (timeout, DNS, credencial, bucket ausente) é descartada em silêncio; diagnóstico em staging/produção impossível só pelos logs. Inconsistente com o padrão de logging adotado no mesmo repo. (Os critérios *explícitos* do C01 §3.6 são atendidos — corpo do 503 identifica a dependência; por isso Low e não High.)
- **Referência:** CLAUDE.md §3 pilar 5 / RNF-024; ADR-015 (padrão `error_type`); PROMPTS/W0-C01 §3.6.
- **Correção recomendada:** nos blocos `except` de `_check_database`/`_check_storage` (e/ou `ping()`), logar `WARNING` com o nome da dependência e `type(exc).__name__` (nunca `str(exc)` — anti-vazamento), aproveitando o `request_id` já no ContextVar.

---

#### W0-A-004 — Cliente boto3 sem connect/read timeout: threads do threadpool podem ficar presas além do orçamento de 5 s do readiness

- **Severidade:** Low (rebaixado de Medium pela verificação adversarial) · **Categoria:** 4.5/4.7/boas-práticas-api — consolidação de 3 achados · **Esforço:** P
- **Evidência:** [r2_storage.py:52](../../apps/api/src/adapters/outbound/storage/r2_storage.py) — `BotoConfig(signature_version="s3v4", retries={"max_attempts": 3})` sem `connect_timeout`/`read_timeout` (defaults do botocore: 60 s + 60 s por tentativa); [health.py:46-48](../../apps/api/src/adapters/inbound/http/health.py) — `asyncio.wait_for(run_in_threadpool(storage.health), timeout=5.0)`: o `wait_for` cancela só o `await`; a **thread** segue bloqueada no `head_bucket`.
- **Esperado:** orçamento de tempo da chamada ao R2 alinhado ao orçamento do check (timeouts explícitos no BotoConfig), liberando a thread pouco após o `wait_for` expirar.
- **Atual:** com endpoint R2 inacessível (black-hole de rede), cada probe deixa uma thread presa por minutos. A verificação adversarial **testou empiricamente** com as deps pinadas: o token do CapacityLimiter do anyio é liberado no cancel (threads abandonadas **não** esgotam o limite de 40 — o impacto real é acúmulo limitado e autorrecuperável de threads/sockets de SO durante a indisponibilidade), e o 503 sai corretamente em 5 s. Desvio real de boa prática com impacto menor que o aparente.
- **Referência:** CLAUDE.md §3.1 (robustez); RNF-024; ADR-012 ("event loop nunca bloqueia" pressupõe threads que terminam).
- **Correção recomendada:** `connect_timeout`/`read_timeout` explícitos (3–5 s) no `BotoConfig` de `R2Storage.from_settings`, com `retries={"max_attempts": 1}` adequado ao caminho de health; beneficia também upload/download na Wave 2.

---

#### W0-A-005 — Falha de validação do `Settings` no keep-alive escapa do contrato "só `error_type`" e pode ecoar a connection string em traceback

- **Severidade:** Low · **Categoria:** 4.8 Keep-alive (segurança de logs) · **Esforço:** P
- **Evidência:** [keep_alive.py:121-123](../../apps/api/src/tasks/keep_alive.py) — `main()` chama `get_settings()` **fora** do try/except de `run()` (:104-111) que garante o log só com `error_type`; [config.py:39-43](../../apps/api/src/infrastructure/config.py) — `Settings` não define `hide_input_in_errors=True`; a `ValidationError` do Pydantic v2 imprime `input_value='<valor integral>'`. O teste de não-vazamento (`test_keep_alive.py:69-83`) cobre apenas falha de **conexão**.
- **Esperado:** nenhum caminho de falha da rotina imprime credenciais (PROMPTS/W0-C02 §4.1.4).
- **Atual:** um `KEEPALIVE_DATABASE_URL` malformado mas com credencial (prefixo trocado, aspas/espaço da colagem) mata o processo com traceback cru contendo a URL. No Actions o masking cobre o valor exato do secret (mitigação parcial); em execução local (`docs/keep-alive.md` §7) não há masking.
- **Referência:** PROMPTS/W0-C02 §4.1.4; CLAUDE.md §9 (segredos); RNF-024.
- **Correção recomendada:** defesa em profundidade barata: (a) `hide_input_in_errors=True` no `model_config` do `Settings`; e/ou (b) envolver `get_settings()` em `main()` num try/except que loga só `error_type` e retorna 1. Adicionar teste correspondente.

---

#### W0-A-006 — `docs/keep-alive.md` §6 atribui a ativação do schedule ao "push para `main`", mas o schedule roda da branch padrão (`develop`)

- **Severidade:** Low · **Categoria:** 4.8/4.11 Docs — consolidação de 2 achados · **Esforço:** P
- **Evidência:** [keep-alive.md:145-147](../keep-alive.md) — "Em repositórios novos os workflows agendados já ficam ativos no push para `main`"; contradiz ADR-016 (DECISIONS.md:105): "O workflow agendado do keep-alive roda a partir da branch padrão (`develop`)". Scheduled workflows do GitHub executam a versão do arquivo na **branch padrão**.
- **Esperado:** runbook de produção refletindo o comportamento real (o doc foi escrito antes da publicação no GitHub e não foi atualizado).
- **Atual:** o operador pode concluir que o cron só liga após merge em `main`, ou editar a cadência em `main` esperando efeito (a versão executada é a de `develop`).
- **Referência:** ADR-016; PROMPTS/W0-C02 §4.5; CLAUDE.md §10 (docs verdadeiros).
- **Correção recomendada:** corrigir o passo 3 do §6: o schedule executa a partir da **branch padrão** (`develop`, ADR-016); alterações de cadência devem ser feitas nela.

---

#### W0-A-007 — ADR-013 e docstring de `errors.py` descrevem o desenho **pré-fix** do catch-all (divergência ADR × código)

- **Severidade:** Low · **Categoria:** 4.11 Docs/ADRs · **Esforço:** P
- **Evidência:** DECISIONS.md:84 ("O `RequestIdMiddleware` captura `Exception`... O handler genérico permanece como rede de segurança") e [errors.py:10-14, 41-42](../../apps/api/src/adapters/inbound/http/errors.py) descrevem o RequestIdMiddleware como caminho principal. Código real ([app.py:46-52](../../apps/api/src/adapters/inbound/http/app.py), [middleware.py:35-47](../../apps/api/src/adapters/inbound/http/middleware.py)): o caminho **principal** é o `ErrorHandlingMiddleware` interno ao CORS (fix da revisão adversarial, CHANGELOG: "catch-all movido para ErrorHandlingMiddleware interno ao CORS"); o RequestIdMiddleware virou a rede de segurança.
- **Esperado:** ADR-013 emendado (como foi feito no ADR-007) refletindo a arquitetura final em três camadas; docstrings coerentes — `middleware.py:13` e `app.py:49` citam "ADR-013" como se o ADR contivesse o racional do CORS, que ele não menciona.
- **Atual:** o fix foi registrado no CHANGELOG e nos comentários de `app.py`/`middleware.py`, mas o texto do ADR e a docstring de `errors.py` continuam com o desenho anterior.
- **Referência:** CLAUDE.md §10 item 2; checklist 4.11 ("divergências entre ADR e código são achados").
- **Correção recomendada:** emendar o ADR-013 (ErrorHandlingMiddleware interno ao CORS como caminho principal + porquê) e corrigir as docstrings de `errors.py`. Sem mudança de comportamento.

---

#### W0-A-008 — Actions de terceiros referenciadas por tag mutável (em workflow que receberá secret de banco de produção)

- **Severidade:** Low · **Categoria:** 4.8/4.9 CI-CD (supply chain) — consolidação de 2 achados · **Esforço:** P
- **Evidência:** [ci.yml:45,48,90,97](../../.github/workflows/ci.yml) e [keep-alive.yml:52,55](../../.github/workflows/keep-alive.yml) — `actions/checkout@v4`, `astral-sh/setup-uv@v6`, `pnpm/action-setup@v4`, `actions/setup-node@v4` (tags mutáveis); exemplo de deploy comentado usa `superfly/flyctl-actions/setup-flyctl@master` (ref de branch — a pior forma).
- **Esperado:** pinning por SHA de commit (tag em comentário) em workflows que manipulam credenciais — coerente com a postura de supply chain já adotada (ADR-010 aprova build scripts do pnpm explicitamente).
- **Atual:** um comprometimento upstream da tag executaria código com acesso ao env contendo `KEEPALIVE_DATABASE_URL` no run diário automático.
- **Referência:** ADR-010 (postura supply chain); GitHub Actions security hardening (prática de mercado — nenhuma regra interna explícita, daí Low).
- **Correção recomendada:** pinar cada action por SHA completo (`@<sha40> # vX.Y.Z`) nos dois workflows; habilitar Dependabot para `github-actions`; trocar o `@master` do exemplo por SHA quando o deploy for ativado.

---

#### W0-A-009 — Job diário do keep-alive instala o grupo dev inteiro (pytest, mypy, ruff, moto) sem necessidade

- **Severidade:** Low · **Categoria:** 4.8 Keep-alive (eficiência) · **Esforço:** P
- **Evidência:** [keep-alive.yml:61](../../.github/workflows/keep-alive.yml) — `uv sync --frozen` (uv inclui o grupo `dev` por padrão); `pyproject.toml:21-30` — dev = pytest, pytest-asyncio, pytest-cov, httpx, ruff, mypy, moto. A rotina importa apenas config/logging/database.
- **Esperado:** PROMPTS/W0-C02 §4.2: "instalar deps **mínimas**" no job do keep-alive.
- **Atual:** o run diário resolve/instala dependências de teste e lint nunca usadas pelo SELECT one-shot (mitigado, não eliminado, pelo cache do setup-uv).
- **Referência:** PROMPTS/W0-C02 §4.2; CLAUDE.md §3 (custo R$ 0).
- **Correção recomendada:** `uv sync --frozen --no-dev` no step de instalação do keep-alive.yml (o CI principal continua com dev).

---

#### W0-A-010 — `ci.yml` sem bloco `permissions` explícito (least privilege aplicado só no keep-alive.yml)

- **Severidade:** Low · **Categoria:** 4.9 CI/CD · **Esforço:** P
- **Evidência:** [ci.yml](../../.github/workflows/ci.yml) não contém `permissions:`; contraste com [keep-alive.yml:35-36](../../.github/workflows/keep-alive.yml) (`permissions: contents: read`, comentado como least privilege).
- **Esperado:** ambos os workflows com `permissions: contents: read` — o CI só faz checkout/lint/teste/build.
- **Atual:** escopo do `GITHUB_TOKEN` do CI depende do default do repositório; inconsistência entre os dois workflows do mesmo repo.
- **Referência:** padrão já adotado em keep-alive.yml; CLAUDE.md §3 (robustez).
- **Correção recomendada:** adicionar `permissions: contents: read` no nível do workflow em `ci.yml`.

---

#### W0-A-011 — Job web não roda `pnpm format:check` (formatação do frontend não é gated; assimetria com o api)

- **Severidade:** Low · **Categoria:** 4.9 CI/CD · **Esforço:** P
- **Evidência:** [ci.yml:106-110](../../.github/workflows/ci.yml) — job web executa só `pnpm lint` e `pnpm build`; o script existe (`apps/web/package.json:12`) e é comando padrão no CLAUDE.md §9; o job api gateia formatação via `ruff format --check` (ci.yml:59).
- **Esperado:** paridade de gates — se a formatação Python falha o CI, a TS/CSS também deveria.
- **Atual:** drift de Prettier passa no CI. (O prompt C01 §4.4 só exigia lint+build — dívida de consistência, não violação de spec.)
- **Referência:** CLAUDE.md §9; PROMPTS/W0-C01 §4.4.
- **Correção recomendada:** step `pnpm format:check` entre Lint e Build no job web.

---

#### W0-A-012 — Hermeticidade incompleta: `_env_file=None` não isola variáveis de ambiente do processo para campos opcionais do `Settings`

- **Severidade:** Low · **Categoria:** 4.10 Testes · **Esforço:** P
- **Evidência:** [conftest.py:87-92](../../apps/api/tests/conftest.py) — `Settings(_env_file=None, ...)` desliga apenas a fonte dotenv; campos não passados explicitamente (R2_*, `CORS_ALLOWED_ORIGINS`, `SUPABASE_URL`, `LOG_LEVEL`) continuam lidos do ambiente do processo. Ex.: `test_config.py:62-63` falharia com `R2_*` exportadas no shell do desenvolvedor.
- **Esperado:** suíte hermética contra **qualquer** configuração local (PROMPTS/W0-C01 §6; princípio autodeclarado no docstring do conftest), incluindo variáveis de shell — não só o arquivo `.env`.
- **Atual:** o `.env` está corretamente isolado (`_env_file=None` + `chdir` em test_main), mas env vars exportadas vazam para testes que não as fixam, podendo causar falhas espúrias em máquinas de dev.
- **Referência:** PROMPTS/W0-C01 §6; CLAUDE.md §8 (integração em ambiente isolado).
- **Correção recomendada:** fixture autouse no conftest com `monkeypatch.delenv` de todas as chaves conhecidas do `Settings` (generalizando o padrão já usado em `test_main.py:32-33`).

---

#### W0-A-013 — `LOG_LEVEL` não é validado no `Settings`; valor inválido estoura como `ValueError` genérico do stdlib

- **Severidade:** Low · **Categoria:** 4.3 Configuração · **Esforço:** P
- **Evidência:** [config.py:47](../../apps/api/src/infrastructure/config.py) — `log_level: str = "INFO"` (str livre); [logging.py:68](../../apps/api/src/infrastructure/logging.py) — `root.setLevel(level.upper())`. `LOG_LEVEL=VERBOSE` (ou `INFO ` com espaço) atravessa o `Settings` e só falha em `configure_logging`, com `ValueError: Unknown level` sem citar a variável.
- **Esperado:** a própria docstring de config.py ("ambiente mal configurado falha rápido no boot") e PROMPTS/W0-C01 §3.4 — todo campo validado na construção do `Settings`, com erro nomeando a variável. O contrato `DEBUG | INFO | WARNING | ERROR` documentado no `.env.example:11` fica sem enforcement.
- **Atual:** a falha ainda ocorre no boot (impacto operacional pequeno), mas fora do `Settings` e com mensagem genérica.
- **Referência:** PROMPTS/W0-C01 §3.4; CLAUDE.md §3 pilar 5; `.env.example:11`.
- **Correção recomendada:** `log_level: Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"] = "INFO"` (ou field_validator com `.strip().upper()` validando contra `logging.getLevelNamesMapping()`).

---

#### W0-A-014 — Downgrade da baseline dropa `pgcrypto` sem guarda (assimetria com o upgrade no-op em ambiente gerenciado)

- **Severidade:** Low · **Categoria:** 4.4 Migrations · **Esforço:** P
- **Evidência:** [0001_baseline.py:33](../../apps/api/migrations/versions/0001_baseline.py) — `DROP EXTENSION IF EXISTS pgcrypto`. O upgrade (`:26`) é no-op no Supabase (extensão pré-existente e compartilhada); o downgrade remove incondicionalmente mesmo o que não criou. Mitigação atual: apenas o comentário das linhas 30-32.
- **Esperado:** downgrade simétrico ao que o upgrade efetivamente fez — não remover recurso pré-existente/compartilhado de ambiente gerenciado, ou guarda explícita.
- **Atual:** um `alembic downgrade base` por engano contra o Supabase real tentaria dropar extensão compartilhada (ou falharia no meio por dependência RESTRICT).
- **Referência:** CLAUDE.md §3.1 (robustez) e §8 (migrations documentadas); ADR-007.
- **Correção recomendada:** downgrade defensivo (condicionar a `APP_ENV` dev/test, ou registrar se a migration criou a extensão), mantendo o ciclo completo validável no Postgres limpo de CI/dev. Alternativa mínima: nota de operação no `docs/setup-infra.md` proibindo downgrade contra o projeto gerenciado.

---

#### W0-A-015 — CORS com `allow_credentials=True` por padrão e sem guarda contra origem curinga vinda do ambiente

- **Severidade:** Low · **Categoria:** boas-práticas/api (segurança) · **Esforço:** P
- **Evidência:** [app.py:53-60](../../apps/api/src/adapters/inbound/http/app.py) — `allow_origins=settings.cors_origins, allow_credentials=True`; [config.py:69,102-104](../../apps/api/src/infrastructure/config.py) — `cors_allowed_origins` é string livre sem validação de conteúdo. Verificado no código do Starlette instalado: com `"*"` + credentials, o middleware **reflete** a Origin do request com `Access-Control-Allow-Credentials: true`.
- **Esperado:** configuração fail-fast contra combinações inseguras (mesmo princípio do validador tudo-ou-nada do R2 no próprio `config.py:80-96`); `allow_credentials` só quando houver uso real de cookies (Wave 1 usará JWT via header `Authorization`, que não exige credentials).
- **Atual:** default (`http://localhost:3000`) seguro; mas `CORS_ALLOWED_ORIGINS=*` em staging/produção ligaria silenciosamente reflexão de origem com credenciais. Risco latente (exigiria dois erros futuros), sem não-conformidade material hoje.
- **Referência:** CLAUDE.md §3 (falhar rápido em má configuração); PROMPTS/W0-C01 §3.4/§4.2.
- **Correção recomendada:** validador no `Settings` rejeitando `"*"` em `cors_allowed_origins` enquanto credentials estiver ativo (ou tornar `allow_credentials` configurável com default `False` até a Wave 1 decidir o mecanismo de sessão).

---

#### W0-A-016 — Ausência de security headers mínimos nas respostas da API

- **Severidade:** Low · **Categoria:** boas-práticas/api (segurança) · **Esforço:** P
- **Evidência:** [app.py:52-61](../../apps/api/src/adapters/inbound/http/app.py) — middlewares: ErrorHandling, CORS, RequestId; nenhum adiciona `X-Content-Type-Options`, `Cache-Control` ou afins (grep no repo: zero ocorrências); `/docs` (HTML do Swagger) também sem proteção; deploy/proxy ainda indefinido (ADR-009 Proposta).
- **Esperado:** baseline de hardening para API JSON: `X-Content-Type-Options: nosniff` em tudo e `Cache-Control: no-store` nas respostas de API — relevante a partir da Wave 1 (endpoints autenticados). Sem RNF específico na Wave 0 (prática de mercado), superfície atual (~/health, /docs) de risco ~nulo.
- **Atual:** nenhum security header emitido pela aplicação; a proteção dependeria integralmente do proxy/host, não definido.
- **Referência:** CLAUDE.md §3; OWASP REST Security (mercado). HSTS pertence ao edge/TLS, não necessariamente à app.
- **Correção recomendada:** middleware leve (ou ampliar o RequestIdMiddleware) injetando `nosniff` + `no-store` — **antes da Wave 1**.

---

#### W0-A-017 — Página de status confia no shape do JSON sem validar `response.ok` e a rota não tem error boundary

- **Severidade:** Low · **Categoria:** boas-práticas/web (robustez) · **Esforço:** P
- **Evidência:** [api-status.tsx:44](../../apps/web/src/app/_components/api-status.tsx) — `(await response.json()) as ReadyPayload` (cast sem validação, sem checar `response.ok`/status); [api-status.tsx:88](../../apps/web/src/app/_components/api-status.tsx) — `Object.entries(payload.checks)` lança `TypeError` se `checks` vier `undefined`; não existe `error.tsx`/`global-error.tsx` em `apps/web/src/app/`.
- **Esperado:** PROMPTS/W0-C01 §4.3: health da página "opcional, **com fallback amigável**" — resposta fora do contrato degrada para o estado offline/nota. DoD global: "error boundaries cobrindo a rota".
- **Atual:** rede-fora/timeout/corpo não-JSON degradam bem; mas um JSON válido de shape diferente (ex.: `{"detail":"Not Found"}` de um `NEXT_PUBLIC_API_BASE_URL` com path errado, ou JSON de proxy) passa pelo cast, vira estado `ready` e **quebra a renderização** — o usuário vê a tela de erro padrão do Next, não o fallback amigável.
- **Referência:** PROMPTS/W0-C01 §4.3; CLAUDE.md §3 pilar 1 e §8 (RNF-014/016).
- **Correção recomendada:** aceitar somente `response.ok || response.status === 503` **e** validar minimamente o shape (`typeof payload?.checks?.database === 'string'`), caindo para `offline` caso contrário; adicionar um `error.tsx` mínimo em `apps/web/src/app/`.

---

#### W0-A-018 — `UnitOfWork` (porta) implementada em `infrastructure/database.py`, não em `adapters/outbound/`

- **Severidade:** Low · **Categoria:** 4.1 Arquitetura hexagonal (colocação) · **Esforço:** P
- **Evidência:** [database.py:101](../../apps/api/src/infrastructure/database.py) — `class SqlAlchemyUnitOfWork(UnitOfWork)` (única implementação da porta de `application/ports/unit_of_work.py:15`). CLAUDE.md §5.2: "adapters implementam as portas"; §5.1 mapeia "DB (SQLAlchemy)" em `adapters/outbound/`. O caso gêmeo (StoragePort) foi resolvido no sentido oposto — implementações em `adapters/outbound/storage/` — criando dois "lares" distintos para implementações de porta no mesmo codebase.
- **Esperado / Atual:** a colocação foi **mandada pelo próprio prompt C01 §4.2** ("infrastructure/database.py — ... e um UnitOfWork/sessão por request") e a direção de dependência está correta (infra → application.ports, para dentro) — é tensão de convenção/colocação, não de direção. O risco é a ambiguidade se materializar na Wave 2, quando os repositórios SQLAlchemy concretos precisarem de um lar consistente.
- **Referência:** CLAUDE.md §5.1/§5.2; ADR-002; PROMPTS/W0-C01 §4.2.
- **Correção recomendada:** antes/junto da Wave 2 (primeiros repositórios), decidir e registrar em ADR: mover `SqlAlchemyUnitOfWork` (e futuros repositórios) para `adapters/outbound/db/`, **ou** formalizar `infrastructure/database.py` como o adapter outbound de DB e ajustar a anotação do CLAUDE.md §5.1. Resolver documentalmente; não mover código agora.

### Nit

---

#### W0-A-019 — Árvore do CLAUDE.md §5.1 não reflete o pacote `src/tasks/` criado no W0-C02

- **Severidade:** Nit · **Categoria:** 4.1/docs · **Esforço:** P
- **Evidência:** `apps/api/src/tasks/` existe (keep_alive.py; CLAUDE.md §9 documenta o comando), mas a árvore de §5.1 lista apenas domain/application/adapters/infrastructure/main.py.
- **Correção recomendada:** adicionar `tasks/` (drivers inbound de tarefas agendadas) à árvore de §5.1 — CLAUDE.md §10.4 manda refletir mudanças estruturais.

#### W0-A-020 — `APP_ENV` com default silencioso `"dev"`: deploy que esqueça a variável reporta `env="dev"` na observabilidade

- **Severidade:** Nit · **Categoria:** 4.3 Configuração · **Esforço:** P
- **Evidência:** [config.py:46](../../apps/api/src/infrastructure/config.py); o valor alimenta readiness (`health.py:79`), log de boot e logs do keep-alive. Nada hoje gateia em `app_env` (impacto restrito a rótulos de triagem).
- **Correção recomendada:** documentar em `.env.example`/`setup-infra.md` que staging/produção DEVEM definir `APP_ENV`; opcional `logger.warning` no boot quando `app_env="dev"`. Manter o default para DX local.

#### W0-A-021 — `.env.example` sugere para `MIGRATIONS_DATABASE_URL` o formato de conexão direta que falha em redes IPv4-only

- **Severidade:** Nit · **Categoria:** 4.4 (docs de config) · **Esforço:** P
- **Evidência:** [.env.example:22](../../apps/api/.env.example) mostra só `db.<ref>.supabase.co:5432`; a emenda IPv6 do ADR-007 (DECISIONS.md:49) e `docs/setup-infra.md:32-38` documentam que isso falha com `gaierror` na própria rede de dev do projeto (pooler session é a alternativa). Mitigado: o cabeçalho do arquivo remete ao setup-infra.md.
- **Correção recomendada:** 1-2 linhas de comentário citando o caveat IPv6-only e o formato do pooler em modo session.

#### W0-A-022 — `migrations/env.py` importa símbolo privado `_coerce_asyncpg_url` de `src.infrastructure.config`

- **Severidade:** Nit · **Categoria:** 4.4 (convenção) · **Esforço:** P
- **Evidência:** [env.py:17](../../apps/api/migrations/env.py); a função tem prefixo de privado em `config.py:23` mas é consumida por módulo externo (o reuso em si é correto/DRY).
- **Correção recomendada:** renomear para `coerce_asyncpg_url` (público) e atualizar os dois usos; sem efeito funcional.

#### W0-A-023 — `X-Request-ID` inbound aceito/refletido sem whitelist de formato (apenas truncamento a 128)

- **Severidade:** Nit (rebaixado de Low pela verificação adversarial) · **Categoria:** 4.6/boas-práticas-api — consolidação de 2 achados · **Esforço:** P
- **Evidência:** [middleware.py:57-58](../../apps/api/src/adapters/inbound/http/middleware.py). Mitigações verificadas: h11 rejeita CR/LF (sem response splitting); JsonFormatter escapa o valor (sem log injection); truncamento mitiga flooding. O reuso do id do chamador é deliberado, testado e prática padrão; nenhum doc do projeto exige validação de formato — resta apenas higiene de charset nos logs.
- **Correção recomendada:** validar contra padrão restrito (ex.: `^[A-Za-z0-9._-]{1,128}$`), caindo para uuid4 quando não casar; opcional `client_request_id` para preservar o vínculo.

#### W0-A-024 — `ci.yml` sem `concurrency` para cancelar runs supersedidos

- **Severidade:** Nit · **Categoria:** 4.9 CI/CD · **Esforço:** P
- **Evidência:** [ci.yml](../../.github/workflows/ci.yml) sem bloco `concurrency:`; keep-alive.yml:39-41 já usa o padrão.
- **Correção recomendada:** `concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }` — ganha relevância quando `develop` entrar nos gatilhos (W0-A-002).

#### W0-A-025 — Fixture de restauração de logging duplicada em `test_logging.py` (redundante com a autouse do conftest)

- **Severidade:** Nit · **Categoria:** 4.10 Testes · **Esforço:** P
- **Evidência:** [test_logging.py:10-16](../../apps/api/tests/unit/test_logging.py) (`_restaura_logging`) idêntica à `_isola_logging_global` de [conftest.py:64-77](../../apps/api/tests/conftest.py) — sobra do refactor que globalizou o isolamento (commit `aac5aa1`).
- **Correção recomendada:** remover a fixture local, confiando na global.

#### W0-A-026 — Marker `@db` em módulo cobre teste que roda offline e duplica cenário da suíte unitária

- **Severidade:** Nit · **Categoria:** 4.10 Testes · **Esforço:** P
- **Evidência:** [test_database.py:20](../../apps/api/tests/integration/test_database.py) (`pytestmark` de módulo) marca também `test_ping_retorna_false_para_banco_inacessivel` (:40-52), que não usa a fixture gateadora e roda offline; o cenário já existe em `test_database_offline.py:38-43`. `pytest -m "not db"` o excluiria desnecessariamente.
- **Correção recomendada:** remover o teste duplicado de integration (ou tirá-lo do pytestmark do módulo).

#### W0-A-027 — Pasta `tests/e2e/` prevista no layout do monorepo não existe

- **Severidade:** Nit · **Categoria:** 4.10 (layout) · **Esforço:** P
- **Evidência:** CLAUDE.md §5.1 especifica `tests/{unit,integration,e2e}/`; só unit/ e integration/ existem. Materialmente irrelevante (E2E/Playwright só se aplica a UI, Wave 2+).
- **Correção recomendada:** criar `tests/e2e/` quando o primeiro teste Playwright nascer, ou ajustar o §5.1.

#### W0-A-028 — README.md raiz chama ADR-010 de "revisável", mas a decisão está Aceita desde o W0-C01

- **Severidade:** Nit · **Categoria:** 4.11 Docs · **Esforço:** P
- **Evidência:** [README.md:48](../../README.md) ("gerenciadores de pacote e plataformas de deploy é revisável — ver ADR-009/ADR-010") vs DECISIONS.md:67 (ADR-010 **Aceita** — uv/pnpm confirmados). Só o ADR-009 (deploy) segue revisável. Texto residual da Sessão 00.
- **Correção recomendada:** reescrever a frase: deploy revisável (ADR-009); gerenciadores confirmados (ADR-010).

#### W0-A-029 — Dockerfile: bases pinadas por tag mutável (não digest) e `/app` gravável pelo usuário de runtime

- **Severidade:** Nit (rebaixado de Low pela verificação adversarial) · **Categoria:** boas-práticas/api · **Esforço:** P
- **Evidência:** [Dockerfile:8,21](../../apps/api/Dockerfile) (tags mutáveis; builder e runtime são imagens distintas que podem driftar de patch) e [Dockerfile:27](../../apps/api/Dockerfile) (`COPY --chown=api:api` deixa código e venv graváveis pelo usuário que executa o processo). Todos os requisitos explícitos do prompt (multi-stage, non-root, healthcheck, uvicorn) estão atendidos; o mandato de pinagem do projeto cobre pacotes/lockfiles, não imagens; a CI não builda a imagem hoje (exposição nula até o deploy).
- **Correção recomendada:** pinar as duas bases por digest (renovação via Dependabot/Renovate) e remover o `--chown` (arquivos root:root com leitura para todos; `USER api` continua executando normalmente).

---

## 5. Lista priorizada de remediação

Ordem sugerida (severidade × dependência × afinidade de arquivo — itens agrupáveis num mesmo commit/PR estão juntos):

| Ordem | IDs | Tema | Racional |
| --- | --- | --- | --- |
| 1 | **W0-A-001** | Cadastrar `KEEPALIVE_DATABASE_URL` (+ opcional `ALERT_WEBHOOK_URL`) e validar via `workflow_dispatch`; se não for imediato, desabilitar o schedule | Ação **operacional**, não de código; risco real com prazo (~2026-06-18) e ruído diário de falha |
| 2 | **W0-A-002** | Decidir gatilho de CI para `develop` (push direto vs PR-only + branch protection) e fechar o checkbox do ADR-016 | Pré-condição de processo para a Wave 1 integrar com CI |
| 3 | **W0-A-003 + W0-A-004** | Observabilidade/robustez do readiness: log `WARNING` com `error_type` nos checks + timeouts no `BotoConfig` | Mesma área de código (health/r2_storage); fecha o gap de diagnóstico antes do staging |
| 4 | **W0-A-005** | `hide_input_in_errors=True` + `get_settings()` dentro do contrato de erro do keep-alive + teste | Segurança de logs; trivial e com teste |
| 5 | **W0-A-013 + W0-A-012** | `LOG_LEVEL` como `Literal` no Settings + fixture autouse de `delenv` no conftest | Configuração/hermeticidade; mesmo ciclo de testes |
| 6 | **W0-A-015 + W0-A-016 + W0-A-023** | Hardening HTTP: guarda CORS `*`×credentials, security headers, whitelist do `X-Request-ID` | Pacote único de hardening da camada HTTP, antes da Wave 1 (auth) |
| 7 | **W0-A-009 + W0-A-010 + W0-A-011 + W0-A-024 + W0-A-008** | Workflows: `--no-dev` no keep-alive, `permissions` no ci.yml, `format:check` no web, `concurrency`, SHA pinning | Um único PR de CI/workflows |
| 8 | **W0-A-014** | Downgrade defensivo da baseline (ou nota de operação) | Migrations; isolado |
| 9 | **W0-A-017** | Validação de shape + `error.tsx` na página de status | Frontend; isolado |
| 10 | **W0-A-006 + W0-A-007 + W0-A-019 + W0-A-021 + W0-A-028** | Pacote de docs/ADRs: keep-alive.md §6 (branch padrão), emenda ADR-013 + docstrings, árvore §5.1 com `tasks/`, caveat IPv6 no .env.example, frase do README | Um único PR documental |
| 11 | **W0-A-018** | ADR decidindo o lar das implementações de porta de DB (UoW/repositórios) | Decidir **antes da Wave 2**; sem mover código agora |
| 12 | **W0-A-020 + W0-A-022 + W0-A-025 + W0-A-026 + W0-A-027 + W0-A-029** | Nits restantes (APP_ENV doc, rename `coerce_asyncpg_url`, fixtures/markers de teste, e2e/, Dockerfile digest) | Varredura final de baixa prioridade |

---

## 6. Apêndice — saídas brutas das verificações executáveis

> Executadas em 2026-06-11 contra o commit `54ae345` (develop), Windows 11, Python 3.12 (uv), PostgreSQL 17.10 real (binários portáteis zonky, porta 5433 — máquina sem Docker; env vars sobrescritas para nunca tocar o Supabase real).

### A.1 Imports do domínio (deve ser vazio)

```
$ grep -rEn "import (fastapi|sqlalchemy|boto3|pydantic|starlette|alembic)|from (...)" apps/api/src/domain/
exit=1 (nenhum match) — src/domain contém apenas __init__.py (docstring, zero imports)
```

### A.2 Varredura de segredos e lockfiles

```
$ git grep -nE "(SECRET|PASSWORD|ACCESS_KEY|service_role|eyJ[A-Za-z0-9_-]{10,})" -- . ':!*.example' ':!*.md'
→ apenas: POSTGRES_PASSWORD=postgres (CI/compose local), nomes de variáveis em mensagens/validadores,
  credenciais FICTÍCIAS de teste (_SENHA_SECRETA="sup3r-s3cr3t-pw" usada justamente p/ provar o não-vazamento).
  Nenhum segredo real.

$ git log --all -- "*.env" → vazio (nenhum .env jamais commitado)
$ git ls-files | grep -E "uv.lock|pnpm-lock.yaml" → apps/api/uv.lock · apps/web/pnpm-lock.yaml
```

### A.3 Backend — lint, formato, tipos, testes offline

```
$ uv run ruff check .            → All checks passed! (RUFF_CHECK_EXIT=0)
$ uv run ruff format --check .   → 43 files already formatted (RUFF_FORMAT_EXIT=0)
$ uv run mypy                    → Success: no issues found in 26 source files (MYPY_EXIT=0)
$ uv run pytest --cov            → 70 passed, 6 skipped (@db) · cobertura 98.81% (piso 80) (PYTEST_EXIT=0)
```

### A.4 Ciclo Alembic contra Postgres 17.10 real, em banco limpo

```
$ MIGRATIONS_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:5433/rastreio_test uv run alembic upgrade head
INFO  Running upgrade  -> 0001, baseline ...        (UPGRADE1_EXIT=0)
$ uv run alembic downgrade base                      (DOWNGRADE_EXIT=0)
$ uv run alembic upgrade head                        (UPGRADE2_EXIT=0)
Inspeção pós-ciclo: pgcrypto instalada: True | alembic_version: 0001 | tabelas public: ['alembic_version']
(nenhuma tabela/enum de domínio — correto)
```

### A.5 Suíte completa com Postgres real obrigatório + frontend

```
$ TEST_DATABASE_URL=...5433/rastreio_test REQUIRE_DB_TESTS=1 uv run pytest --cov
→ 76 passed in 10.66s · Total coverage: 100.00% (PYTEST_DB_EXIT=0)

$ pnpm install --frozen-lockfile && pnpm lint && pnpm build
→ LINT_EXIT=0 · BUILD_EXIT=0 (Next 16.2.9; rotas / e /_not-found estáticas)
```

### A.6 Smoke test da API (uvicorn, porta 8123, PG local, sem R2 — .env não lido)

```
GET /health        → HTTP/1.1 200 OK · {"status":"ok"} · x-request-id: 9965bf76c1eb4025ba019f09826f2935
GET /health/ready  → HTTP/1.1 503 Service Unavailable
                     {"status":"degraded","checks":{"database":"ok","storage":"down"},"version":"0.1.0","env":"test"}
GET /docs          → 200
GET /health  com header "X-Request-ID: auditoria-w0-12345" → resposta ecoa x-request-id: auditoria-w0-12345
```

### A.7 Keep-alive — sucesso e falha controlada

```
# SUCESSO (Postgres local 5433):
{"timestamp":"2026-06-11T12:27:06.899Z","level":"INFO","logger":"rastreio.keep_alive","message":"keep-alive ok",
 "event":"keep_alive","status":"ok","latency_ms":34.48,"db_time":"2026-06-11T12:27:06.900012+00:00",
 "correlation_id":"64a1ef98846a4f62ab233bfbeea068b8","env":"test", ...}
KEEPALIVE_OK_EXIT=0

# FALHA (postgresql+asyncpg://usuario:senha-super-secreta@127.0.0.1:9/nada):
{"timestamp":"2026-06-11T12:27:09.776Z","level":"ERROR","logger":"rastreio.keep_alive","message":"keep-alive falhou",
 "event":"keep_alive","status":"error","correlation_id":"309f1e9fbdda4118b77f923146d9df29","env":"test",
 "error_type":"ConnectionRefusedError", ...}
KEEPALIVE_FAIL_EXIT=1
→ a string "senha-super-secreta" NÃO aparece em nenhuma saída.
```

### A.8 Checagens pontuais

```
apps/api/.python-version → 3.12
alembic.ini → 994 bytes, 0 bytes não-ASCII (requisito do CLAUDE.md §9 atendido)
Dockerfile → multi-stage (uv builder + python:3.12-slim), USER api (non-root), HEALTHCHECK via stdlib
working tree → untracked apenas: PROMPTS/W0-AUDIT-auditoria.md (este prompt) e apps/web/public/
  (assets do W1-C03, pendência já registrada no SESSION_LOG — fora do escopo da Wave 0)
```

---

*Auditoria executada por sessão read-only multi-agente (12 dimensões × verificação adversarial; 48 agentes). Nenhum arquivo de código/config/workflow foi alterado. Entregáveis desta sessão: este relatório + entrada no `SESSION_LOG.md`.*
