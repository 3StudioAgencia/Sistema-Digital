# Prompt de Execução — W0-AUDIT · Auditoria da Wave 0 (read-only)

> **Como usar:** cole este prompt no Claude Code com a **Wave 0 já implementada** (W0-C01 e W0-C02) e os arquivos de contexto na raiz. Esta é uma sessão de **auditoria somente-leitura**: ela **inspeciona, verifica e relata** — **não corrige nada**. A correção será uma sessão separada (remediação), que consumirá os achados numerados por este relatório.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando como **auditor independente** do projeto **Rastreio de Provas Digitais** (3Studio). Audite com rigor e honestidade — **não valide por cortesia**. Todo achado precisa de **evidência** (arquivo + linha + trecho).

**Leia antes de auditar:** `CLAUDE.md` (inteiro — §2 hierarquia de fontes, §3 pilares, §4 stack, §5 arquitetura, §8 DoD, §11 proibições), `DECISIONS.md` (ADRs), `SESSION_LOG.md` (entradas W0-C01 e W0-C02), `README.md`, e os documentos de Backlog (**C01, C02**), DAT (**§1, §2, §3, §6 NÃO se aplica**) e Requisitos (**RNF-011, RNF-018, RNF-023, RNF-024**).

> Se a Wave 0 **não** estiver implementada no repositório, **pare** e reporte isso como bloqueador único, sem inventar achados.

---

## 1. Objetivo

Produzir um **relatório de auditoria** que estabeleça, com evidências, o **grau de conformidade** da Wave 0 com: (a) o escopo e critérios de aceitação do Backlog (C01, C02); (b) a stack e os padrões do DAT; (c) as regras e pilares do `CLAUDE.md`; (d) a Definition of Done aplicável; (e) os ADRs registrados; e (f) boas práticas de engenharia (segurança, observabilidade, tratamento de erros, testes, reprodutibilidade). Cada não-conformidade recebe **ID, severidade e correção recomendada**, para alimentar a sessão de remediação.

---

## 2. Regra de ouro: NÃO corrigir nada

- ❌ **Não edite** código-fonte, configs, migrations, workflows, docs (exceto o relatório, §6) nem os arquivos de contexto (exceto a entrada de sessão no `SESSION_LOG.md`, §8).
- ✅ **Pode (e deve)** ler arquivos e **executar comandos de verificação não-destrutivos** (lint, types, testes, `alembic upgrade head` em banco de **teste**, etc.) para coletar evidência. Rodar verificação **não é** corrigir.
- Se encontrar uma correção óbvia, **registre-a como recomendação** no achado — **não a aplique**.

---

## 3. Escopo da auditoria

Componentes: **W0-C01 (Infraestrutura)** e **W0-C02 (Keep-Alive)**. Dimensões auditadas (detalhe em §4):
arquitetura hexagonal · stack/versões · configuração/segredos · banco/conexão/migrations · storage/R2 · observabilidade · health checks · keep-alive · CI/CD · testes/cobertura · documentação · conformidade com ADRs · conformidade com a DoD · conformidade com os pilares.

---

## 4. Checklist de auditoria (verifique cada item → PASS / FAIL / PARTIAL / N/A + evidência)

### 4.1 Arquitetura hexagonal (ADR-002, CLAUDE.md §5)
- [ ] `domain/` **não importa** FastAPI, SQLAlchemy, boto3, Pydantic-settings nem qualquer framework/infra (verifique imports).
- [ ] `application/ports/` define **interfaces abstratas** (ex.: `StoragePort`); adapters as implementam.
- [ ] Dependências apontam **para dentro**; `main.py` é o **único** composition root (concreto encontra abstrato só ali).
- [ ] Estrutura de pastas coerente com `CLAUDE.md §5.1` (mapeamento de caminhos do DAT respeitado).

### 4.2 Stack e versões (ADR-003, DAT §1, CLAUDE.md §4)
- [ ] Backend: Python 3.12 (piso 3.11), FastAPI (async), SQLAlchemy 2.0 async, Pydantic v2, Alembic, **PyJWT ≥ 2.8** (e **não** `python-jose`), boto3.
- [ ] Frontend: Next.js **App Router**, TypeScript **`strict: true`** (confira `tsconfig`), **CSS Modules**, **sem** framework CSS externo.
- [ ] Itens "≥" **pinados**; **lockfiles versionados** (uv lock e pnpm-lock).

### 4.3 Configuração e segredos
- [ ] **Nenhum segredo** versionado (faça varredura por chaves/tokens/URLs com credencial em todo o repo, inclusive histórico de exemplos).
- [ ] `.env.example` de **ambas** as apps documenta **todas** as chaves usadas (incl. `DATABASE_URL`, `MIGRATIONS_DATABASE_URL`, vars do R2, `SUPABASE_*`, `CORS_ALLOWED_ORIGINS`, `LOG_LEVEL`).
- [ ] `Settings` (pydantic-settings) valida na inicialização; segregação por ambiente; sem defaults sensíveis.

### 4.4 Banco, conexão e migrations (ADR-007, DAT §2)
- [ ] **Duas URLs**: runtime (`DATABASE_URL`, pooler de transação 6543) e migrations (`MIGRATIONS_DATABASE_URL`, conexão direta 5432).
- [ ] Engine de runtime com **`NullPool`** + `statement_cache_size=0` (asyncpg).
- [ ] Alembic `env.py` assíncrono, usando a **conexão direta**; `alembic.ini` correto.
- [ ] **`alembic upgrade head` aplica em banco limpo** e **`downgrade`** funciona (execute contra o Postgres de teste).
- [ ] Migration **baseline sem tabelas/enums de domínio**; `CREATE EXTENSION IF NOT EXISTS pgcrypto` idempotente.
- [ ] `migrations/rls/` existe com README de política; **sem** `.sql` de RLS ainda (correto para Wave 0).
- [ ] **Nenhuma** tabela/enum de domínio antecipada (`usuarios`, `provas_digitais`, `rota_enum`, etc.).

### 4.5 Storage / Cloudflare R2
- [ ] `StoragePort` (porta) + `R2Storage` (adapter boto3) configurado por env, **sem credenciais hardcoded**.
- [ ] `upload`/`download`/`delete`/`health` implementados e tipados; **teste passa** (moto/fake).

### 4.6 Observabilidade (RNF-024)
- [ ] Logging **estruturado JSON** com correlação por `request_id` (via `contextvars` ou equivalente).
- [ ] Middleware de `request_id` injeta header de resposta (ex.: `X-Request-ID`).
- [ ] Erros não tratados **logados em nível crítico**; resposta de erro **padronizada**, **sem vazar stack trace** ao cliente.

### 4.7 Health checks (RNF-024)
- [ ] **`GET /health`** (liveness): `200` imediato, **sem** tocar dependências.
- [ ] **`GET /health/ready`** (readiness): verifica **banco** (`SELECT 1`) e **storage**, reporta status por dependência, **`200`** se ok / **`503`** se essencial down. Estrutura clara de `checks`.

### 4.8 Keep-Alive (ADR-012, C02)
- [ ] Scheduler **externo** ao Supabase e **independente do host da API** — **NÃO** `pg_cron`, **NÃO** scheduler embutido na API. (Confirme que é GitHub Actions agendado ou equivalente externo.)
- [ ] A rotina de ping **reutiliza o `ping()`** do readiness (C01) — **sem duplicar** lógica de banco (DRY).
- [ ] Ping **read-only**; conexão curta (direta/sessão). Sem escrita.
- [ ] **Log estruturado** por execução (`event=keep_alive`, `status`, `latency_ms`, `db_time`, `correlation_id`, `env`).
- [ ] **Fail-loud:** exit **≠ 0** em falha; workflow falha; alerta de webhook **opcional** gatilhado por `if: failure()` **e** existência de secret (sem URL/token hardcoded).
- [ ] Workflow com `schedule` (cron calibrado, ~06:00 BRT = `0 9 * * *` UTC), `workflow_dispatch`, `concurrency`, `timeout-minutes`; lê a connection string de **secret do repo**.
- [ ] Cadência calibrada ao **mínimo** (sem polling sub-horário — RNF-023) e cobre a margem dos 7 dias.
- [ ] `docs/keep-alive.md` presente, incluindo **como ligar em produção** e a **alternativa Cloudflare Worker Cron**.

### 4.9 CI/CD
- [ ] `ci.yml`: job **api** (ruff, mypy strict, Postgres de serviço, `alembic upgrade head`, `pytest --cov`) e job **web** (lint, build).
- [ ] Passo de **deploy documentado/parametrizável**, **sem segredos** no repo (uso de secrets do repositório).
- [ ] CI realmente **passa** com o estado atual (rode localmente o que o CI roda; reporte divergências).

### 4.10 Testes e cobertura (DoD)
- [ ] Existem os testes especificados em **C01 §6** (config, health liveness/readiness, storage port, conectividade DB, request-id) e **C02 §6** (sucesso, falha/exit≠0, log estruturado).
- [ ] **Toda a suíte roda offline** (sem Supabase/R2 reais).
- [ ] Cobertura adequada onde há lógica (a meta ≥95% da máquina de estados **ainda não se aplica** — não há máquina de estados na Wave 0; avalie ≥80% onde houver domínio/serviço relevante).
- [ ] `ruff`, `mypy (strict)`, `pytest`, `pnpm lint`, `pnpm build` **verdes**.

### 4.11 Documentação e contexto
- [ ] `docs/setup-infra.md` e `docs/keep-alive.md` presentes e **precisos** (batem com o código real).
- [ ] **Protocolo de Encerramento** foi cumprido nas sessões W0: `CHANGELOG.md`, `SESSION_LOG.md`, `README.md` (roadmap com Wave 0) e `CLAUDE.md §9` (comandos) refletem o que foi feito.
- [ ] **ADRs atualizados:** ADR-003, ADR-007, ADR-010 e ADR-012 foram **confirmados** (status movido de *Proposta* para *Aceita*) ou ajustados conforme o implementado. Divergências entre o ADR e o código são achados.

### 4.12 Pilares (CLAUDE.md §3)
- [ ] **Stateless (RNF-018):** sem estado de sessão/negócio em memória de processo; pronto para escala horizontal.
- [ ] **Mínimo de requisições (RNF-020 a 023):** keep-alive calibrado; nada de polling supérfluo introduzido.
- [ ] **Robustez:** tratamento de erro/degradação coerente com o que existe nesta camada; readiness degrada com clareza.
- [ ] **Observabilidade:** conforme §4.6/§4.7.
- [ ] **Custo R$ 0:** nenhuma escolha fora do free tier.

---

## 5. Verificações executáveis (rode e cole as evidências no relatório)
Execute o que for aplicável e registre saída resumida como evidência:
```bash
# Estrutura e imports do domínio (deve retornar vazio):
grep -rEn "import (fastapi|sqlalchemy|boto3)" apps/api/src/domain || echo "OK: domain limpo"

# Segredos versionados (inspecione resultados manualmente):
git grep -nE "(SECRET|PASSWORD|ACCESS_KEY|service_role|eyJ[A-Za-z0-9_-]{10,})" -- . ':!*.example' ':!*.md' || echo "Sem matches óbvios"

# Backend: lint, types, testes, migrations (contra Postgres de teste do docker-compose)
docker compose up -d db
cd apps/api && uv sync && uv run ruff check . && uv run mypy src \
  && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head \
  && uv run pytest --cov

# Keep-alive (sucesso contra DB local) e simulação de falha
uv run python -m src.tasks.keep_alive

# Frontend
cd ../web && pnpm install && pnpm lint && pnpm build

# Lockfiles versionados?
git ls-files | grep -E "uv.lock|pnpm-lock.yaml"
```
Se algum comando não existir/divergir do esperado, **isso é um achado**.

---

## 6. Formato do relatório (entregável único desta sessão)

Crie **`docs/audits/wave-0-audit.md`** com a estrutura abaixo:

1. **Cabeçalho** — data, escopo (W0-C01, W0-C02), commit/branch auditado, ambiente de verificação.
2. **Veredito executivo** — a Wave 0 está pronta para servir de base à Wave 1? Quantos achados por severidade. Bloqueia ou não a continuidade.
3. **Matriz de conformidade** — tabela mapeando **cada critério de aceitação (C01 §5, C02 §5)** e **cada item da DoD aplicável** → `PASS | FAIL | PARTIAL | N/A` + evidência curta.
4. **Achados** — um bloco por achado, com **ID `W0-A-NNN`**:
   - `ID` · `Título` · `Severidade` (§7) · `Categoria` (dimensão §4)
   - `Evidência` (arquivo:linha + trecho ou saída de comando)
   - `Esperado` × `Atual`
   - `Referência` (RF/RNF/RN/ADR/DoD/Backlog)
   - `Correção recomendada` (objetiva, sem aplicá-la)
   - `Esforço estimado` (P/M/G)
5. **Lista priorizada de remediação** — os IDs em ordem de execução sugerida (severidade × dependência), pronta para virar o backlog da sessão de remediação.
6. **Apêndice** — saídas brutas relevantes dos comandos de verificação.

> Os **IDs `W0-A-NNN` são estáveis** e serão referenciados pelo prompt de remediação. Numere de forma contínua.

---

## 7. Escala de severidade
- **Blocker** — quebra build/deploy, vaza segredo, viola regra de negócio/segurança, ou impede a Wave 1 de se apoiar na base. Corrigir antes de qualquer avanço.
- **High** — não-conformidade material com spec/DAT/ADR/pilar, ou ausência de critério de aceitação. Corrigir nesta rodada de remediação.
- **Medium** — desvio de qualidade/robustez/observabilidade que não bloqueia, mas gera dívida.
- **Low** — melhoria menor, consistência, clareza.
- **Nit** — cosmético/estilo.

---

## 8. Encerramento da sessão (auditoria — leve)
- ✅ Salve **`docs/audits/wave-0-audit.md`**.
- ✅ Adicione **uma entrada no `SESSION_LOG.md`** (sessão de auditoria): data, escopo, total de achados por severidade, veredito, e **próximo passo** (= "Sessão de remediação da Wave 0 consumindo `docs/audits/wave-0-audit.md`").
- ❌ **Não** altere `CHANGELOG.md`, `DECISIONS.md`, código, configs, migrations ou workflows — a remediação fará isso.
- Ao final, **apresente um resumo**: veredito, contagem por severidade, os 3–5 achados mais críticos (ID + título), e o caminho do relatório.

---

### Lembrete final
A função desta sessão é dizer a **verdade técnica** sobre a Wave 0 — com evidência, sem suavizar e sem corrigir. Um auditor que "passa tudo" é inútil; um que conserta no meio da auditoria contamina o diagnóstico. **Diagnostique com precisão; a cirurgia vem depois.**
