# Prompt de Execução — W0-C02 · Cron Job de Keep-Alive

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto na raiz e o **W0-C01 já concluído**. Este é o **segundo e último componente da Wave 0**. Trabalhe a sessão inteira neste único componente.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Em especial: **§3** (pilares — aqui os relevantes são **mínimo de requisições**, **robustez** e **observabilidade**), **§4/§5** (stack e arquitetura) e **§11** (o que NÃO fazer). Leia também a entrada do **W0-C01 em `SESSION_LOG.md`** para saber exatamente o que já existe (config, logging, camada de banco, CI).

Este componente **depende do W0-C01** (Backlog: "Depende de 01") e **reutiliza** a infraestrutura já criada — não recrie nada.

Referências: Backlog **C02** · Requisitos **RNF-011** (disponibilidade no horário comercial), **RNF-023** (mínimo necessário), **RNF-024** (observabilidade).

---

## 1. Objetivo do componente

O Supabase free tier **pausa o projeto após 7 dias sem requisições** — o que derrubaria o banco inteiro. Este componente entrega um **job agendado** que executa uma requisição **leve e read-only** ao banco em cadência calibrada ao **mínimo necessário** para impedir a pausa, com **registro estruturado** de cada execução (auditoria de disponibilidade) e **alerta em caso de falha**. O mecanismo sustenta o **RNF-011** (banco disponível e "quente" no horário comercial). Custo: **R$ 0**.

---

## 2. Decisão de arquitetura desta sessão (ADR-012 — registrar em `DECISIONS.md`)

> **A armadilha:** seria tentador usar `pg_cron` (cron interno do PostgreSQL) ou um scheduler embutido na API. **Ambos estão errados para este fim:**
> - **`pg_cron` não serve** — se o projeto Supabase pausar, o `pg_cron` pausa junto e **não consegue se auto-acordar**. O keep-alive **precisa vir de fora do Supabase**.
> - **Scheduler na própria API não serve** — se o host da API hibernar (free tier), o scheduler hiberna junto.

**Decisão (ADR-012):** o keep-alive é um **scheduler externo e independente do host da API**, que invoca uma **rotina read-only de *ping* ao banco**. A lógica de ping mora em código testável e reutilizável; o scheduler é apenas o gatilho (portanto trocável).

- **Scheduler primário (padrão):** **GitHub Actions scheduled workflow** (`.github/workflows/keep-alive.yml`). Justificativa: custo zero, já existe o repositório/CI, é **totalmente desacoplado** do host da API, tem histórico de execuções como trilha de auditoria e notificação nativa de falha.
- **Caveat documentado:** o GitHub **desabilita workflows agendados após 60 dias de inatividade do repositório** e pode atrasar/saltar execuções sob carga. A margem de cadência (§4.3) absorve atrasos; para produção de longo prazo, documente a **alternativa Cloudflare Worker Cron Trigger** (mesmo ecossistema do R2, sem o limite de 60 dias) — **apenas documentar, não implementar agora.**

---

## 3. Escopo e NÃO-escopo

### Faz parte desta sessão
- Uma **rotina de keep-alive** em `apps/api`, read-only, que abre uma conexão curta ao Postgres, executa um `SELECT` trivial (ex.: `SELECT 1` / `SELECT now()`), **reutilizando** `infrastructure/config.py`, `infrastructure/logging.py` e a camada de banco do C01.
- **Reaproveitamento da função de *ping*** já usada pelo `/health/ready` (C01): extraia/consolide um único `ping()` reutilizado pelo readiness **e** pelo keep-alive (DRY).
- O **workflow agendado** do GitHub Actions que executa essa rotina em cadência calibrada, com **alerta de falha**.
- **Log estruturado** por execução (evento, status, latência, timestamp do banco, `correlation_id`).
- **Testes** (sucesso e falha) — ver §6.
- Documentação em `docs/` (operação, cadência, como ligar em produção, alternativa Cloudflare).
- Atualização dos documentos de contexto (§8).

### NÃO faz parte
- ❌ `pg_cron`, scheduler embutido na API, ou framework genérico de jobs.
- ❌ Stack de monitoramento/alerta completa — apenas o log estruturado + a notificação nativa de falha do workflow + um webhook **opcional** (ver §4.4).
- ❌ Qualquer escrita no banco, tabela de domínio, regra de negócio ou feature de produto.
- ❌ Implementar a alternativa Cloudflare (só documentar).

---

## 4. Entregáveis detalhados

### 4.1 Rotina de keep-alive (`apps/api`)
- Crie um **entry point de tarefa agendada** (driver inbound), ex.: `src/tasks/keep_alive.py`, executável por `uv run python -m src.tasks.keep_alive`.
- Comportamento:
  1. Carrega `Settings`; usa a **conexão direta/sessão (5432)** do C01 (reutilize `MIGRATIONS_DATABASE_URL`, ideal para conexão *one-shot*) — uma conexão curta, aberta e fechada na execução. *(Qualquer requisição real ao banco conta como atividade; a conexão direta evita qualquer peculiaridade do pooler para um único `SELECT`.)*
  2. Executa o `ping()` reutilizado do readiness; mede a **latência**.
  3. Emite **um log JSON estruturado** com: `event="keep_alive"`, `status="ok"|"error"`, `latency_ms`, `db_time` (valor de `now()`), `correlation_id` (gerado para a execução), `env`.
  4. **Exit code 0** em sucesso; **exit code ≠ 0** em falha (para o scheduler marcar o run como falho e disparar alerta). Trate exceções de conexão sem vazar credenciais no log.
- Mantenha a função de ping **pura e testável** (sem efeitos colaterais além de ler do banco).

### 4.2 Workflow agendado (`.github/workflows/keep-alive.yml`)
- Gatilhos: `schedule` (cron) + `workflow_dispatch` (execução manual para teste).
- `concurrency` para evitar execuções sobrepostas; `timeout-minutes` curto.
- Passos: checkout → setup Python/uv → instalar deps mínimas → executar `uv run python -m src.tasks.keep_alive` em `apps/api`, lendo a connection string de **secret do repositório** (ex.: `secrets.KEEPALIVE_DATABASE_URL`).
- **Nenhum segredo no código**; documente quais secrets configurar no repo para ligar em produção.

### 4.3 Cadência (calibrada — RNF-023 + RNF-011)
- **Restrição dura:** intervalo entre execuções **sempre << 7 dias**.
- **Padrão recomendado:** **uma execução diária**, às **06:00 America/Sao_Paulo** = **`0 9 * * *` (UTC)** — uma hora antes do início do horário comercial (07:00), deixando o banco "quente" para o dia útil. *(Brasil sem horário de verão desde 2019, então BRT = UTC−3 o ano todo; sem complicação de DST.)*
- **Racional (documente):** diário dá margem de ~7× sobre o limite de 7 dias — robusto contra atrasos/saltos do GitHub cron — e atende ao RNF-011 sem polling excessivo. Cadência **configurável** pela expressão cron (rodar só em dias úteis também é aceitável: o gap máximo no fim de semana segue < 7 dias). Não use frequências altas (sub-horárias) — violaria o RNF-023.

### 4.4 Alerta de falha (RNF-024)
- Falha da rotina → exit ≠ 0 → **workflow falha** → notificação nativa do GitHub (suficiente como baseline).
- Adicione um passo de alerta **opcional**, acionado **apenas** com `if: failure()` **e** se um secret de webhook existir (ex.: `secrets.ALERT_WEBHOOK_URL`), postando uma mensagem curta (Slack/Discord/genérico). Sem o secret, o passo é simplesmente pulado. **Não** hardcode URLs nem tokens.

### 4.5 Documentação (`docs/`)
- `docs/keep-alive.md`: o que é, por que existe (pausa de 7 dias), por que é externo ao Supabase (ADR-012), a cadência e seu racional, como **ligar em produção** (configurar `KEEPALIVE_DATABASE_URL` e, opcionalmente, `ALERT_WEBHOOK_URL` nos secrets do repo; habilitar o workflow), como **testar manualmente** (`workflow_dispatch` e execução local), e a **alternativa Cloudflare Worker Cron** para hardening de longo prazo.
- Atualize `docs/setup-infra.md` (C01) com um link para esta página, se fizer sentido.

---

## 5. Critérios de aceitação (do Backlog C02)

Demonstre objetivamente:

1. ✅ **O projeto Supabase permanece ativo após período > 7 dias** — comprovável pela cadência diária do workflow e pelo histórico de execuções bem-sucedidas. *(Validável de verdade só com o Supabase real ligado; deixe o caminho pronto e documentado.)*
2. ✅ **A frequência é a mínima que mantém o projeto ativo** (sem polling excessivo) — cadência diária, configurável e justificada (§4.3).
3. ✅ **Falha do job é registrada e alertada** (RNF-024) — exit ≠ 0 + workflow falho + notificação (e webhook opcional). Demonstre simulando uma falha (connection string inválida) e mostrando o log de erro estruturado + o run marcado como falho.

Qualidade adicional:
4. ✅ A rotina **roda offline** contra o Postgres local do docker-compose (sucesso) e falha de forma controlada com credencial inválida.
5. ✅ `ruff`, `mypy (strict)` e `pytest` **verdes**; sem segredos versionados.
6. ✅ Reuso real da função de `ping()` do C01 (sem duplicação de lógica de banco).

---

## 6. Testes desta camada
- **Sucesso:** com o Postgres local, a rotina executa o ping, retorna `db_time`, emite log `status="ok"` e sai com **exit 0**.
- **Falha:** com connection string inválida, a rotina emite log `status="error"` (sem vazar a credencial) e sai com **exit ≠ 0**.
- **Log estruturado:** verifica que o evento `keep_alive` contém os campos esperados (`status`, `latency_ms`, `correlation_id`, `env`).
- (Opcional) Lint do YAML do workflow / validação básica de sintaxe.

Use `pytest-asyncio`. A suíte roda **sem Supabase/R2 reais**.

---

## 7. Ordem de execução sugerida
1. Ler `CLAUDE.md` + entrada do W0-C01 no `SESSION_LOG.md`; confirmar o que já existe.
2. Consolidar/extrair a função `ping()` reutilizável (readiness + keep-alive).
3. Implementar `src/tasks/keep_alive.py` (config + logging + conexão curta + exit codes).
4. Testes (sucesso e falha) → rodar tudo verde.
5. Criar `.github/workflows/keep-alive.yml` (schedule + dispatch + concurrency + alerta opcional).
6. Escrever `docs/keep-alive.md`.
7. Verificar **todos** os critérios de aceitação (§5).
8. Executar o **Protocolo de Encerramento** (§8).

> Incrementos pequenos e verificáveis. Decisões não óbvias → decidir pelos pilares, implementar e registrar ADR no encerramento.

---

## 8. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)
1. **`CHANGELOG.md`** — em `[Unreleased] → Added`, descreva o W0-C02 (rotina de keep-alive + workflow agendado + alerta + docs).
2. **`DECISIONS.md`** — **registre o ADR-012** (keep-alive externo, scheduler primário GitHub Actions, alternativa Cloudflare documentada, cadência diária) e qualquer outra decisão da sessão.
3. **`SESSION_LOG.md`** — nova entrada: objetivo, feito, decisões, testes/cobertura, **pendências** (ex.: ligar secrets no repo quando o Supabase real existir) e **próximo passo** (= **Wave 1 · W1-C03 · Tela de Login e Sessão**).
4. **`CLAUDE.md`** — atualize **§9 (comandos)** com o comando do keep-alive (`uv run python -m src.tasks.keep_alive`) e ajuste o que mais tiver mudado.
5. **`README.md`** — atualize comandos/roadmap e **marque a Wave 0 como concluída** ✅ (ambos os componentes entregues).
6. Verifique a **Definition of Done** aplicável (subconjunto do `CLAUDE.md §8`: testes, observabilidade, error handling, docs do módulo, sem segredos versionados).
7. **Commits semânticos** (`feat(w0-c02): ...`, `ci(w0-c02): ...`), árvore limpa.

Ao concluir, **apresente um resumo** com: o que foi entregue, evidência de cada critério de aceitação (§5), o que precisa ser ligado em produção (secrets do repo), e o comando exato para iniciar a próxima sessão (W1-C03).

---

### Lembrete final
Este job é a diferença entre "o banco está no ar" e "o banco sumiu durante um feriado prolongado". Pequeno em código, crítico em consequência. Faça-o **desacoplado, observável e à prova de falha silenciosa** — um keep-alive que falha sem avisar é pior do que não ter keep-alive.
