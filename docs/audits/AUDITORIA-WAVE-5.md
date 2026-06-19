# Auditoria de Fechamento — Wave 5 · Relatórios e Refinamento de UX

> **Data:** 2026-06-19 · **Auditor:** engenheiro sênior, adversarial e independente (papel de fechamento de wave) · **Modo:** read-only (nenhuma mudança em código de produção).
> **Escopo da entrega da Wave 5:** **C17 (Relatórios)** entregue · **C18 (Atalhos Rápidos) CORTADO por decisão de produto**.
> **Princípio:** *executar, não confiar* — toda conclusão tem comando+saída / teste+resultado / query / arquivo:linha. Esta auditoria **não repete** a recomputação métrica do C17 (Área A): ela cobre **integração, regressão, limpeza do corte do C18 e qualidade transversal**.

---

> ## ✅ REMEDIAÇÃO APLICADA — 2026-06-19 (Sessão 25)
> Os dois bloqueadores e os achados endereçáveis foram **fechados** (status por achado abaixo). Resumo:
> - **F-01 (Crítico) — RESOLVIDO:** produzida a auditoria dedicada `docs/audits/AUDITORIA-C17.md` (recomputação métrica-por-métrica) — **veredito GO**. Ela ainda **descobriu e corrigiu** um *time-bomb* de relógio na fixture do C17 (M-1): provas ATIVAS com eventos em data fixa `2026-06-15` virariam "atrasadas" a partir de ≈ sexta 19/06 15:00, quebrando 3 testes (o "807 passed" do B2 abaixo era um snapshot **antes** desse limiar). Corrigido na causa raiz + guard determinístico.
> - **F-02 (Alto) — RESOLVIDO:** `ruff check .` e `ruff format --check .` **verdes** (F841 corrigido preservando o seed; `ruff format` em todo o repo). Suíte api completa re-rodada — sem regressão.
> - **F-03/F-04/F-05 (Médios) — RESOLVIDOS:** ADR-095 (corte do C18) + docs sincronizados (C18 **descartado**, Clicheria reconstruída, claims de qualidade reconciliados); guard de regressão do corte em `dashboard-view.test.tsx`.
> - **F-06 (Baixo) — RESOLVIDO** (`prettier --write`). **F-07 (Baixo) — mantido por design** (ver status abaixo).
> - **Guardrail dos dois lados:** novo `test_integracao_atrasadas_c16_c17.py` prova "Atrasadas" igual em dashboard e relatório.
> - **Próximo:** **re-auditar a Wave 5** (a palavra final do GO é da re-auditoria).

---

## 1. Sumário executivo

# ⛔ VEREDITO DA WAVE 5: **NO-GO**

| Severidade | Qtd. | Bloqueia GO? |
| --- | --- | --- |
| 🔴 Crítico | **1** | **Sim** |
| 🟠 Alto | **1** | **Sim** |
| 🟡 Médio | 3 | Não (registrar) |
| ⚪ Baixo | 2 | Não |

**Por que NO-GO (dois bloqueadores independentes):**

1. **🔴 Crítico — a auditoria dedicada do C17 NÃO EXISTE.** O `docs/audits/AUDITORIA-C17.md` — o **insumo principal** desta auditoria, cujo veredito sobre a correção interna do C17 é **assumido** aqui — **não está no repositório**. Pelas regras do próprio prompt (§0 item 1, §A3, §4, §5), **relatório do C17 ausente ⇒ Wave 5 é NO-GO automático**. Não é possível dar a wave por são sem o veredito métrica-por-métrica do núcleo.
2. **🟠 Alto — o gate de lint/format da CI está VERMELHO.** Em ambiente equivalente à CI (`uv sync --frozen`, ruff 0.15.16), `ruff check .` acusa **16 erros** e `ruff format --check .` acusa **17 arquivos** a reformatar. A CI roda exatamente esses dois comandos como gate do job `api` (`.github/workflows/ci.yml:71-72`) — logo a CI em `develop` falha no passo de lint. Isso viola a DoD §9 ("verde no CI") e o critério de GO §5(d) ("qualidade transversal verde").

**Referência ao veredito do C17 (Área A, incorporado e não repetido):** **AUSENTE.** Não há `AUDITORIA-C17.md` (confirmado por `glob docs/audits/*`, `glob **/AUDITORIA*` e `grep` por "C17"/"Relatórios" em `docs/audits/`). O único artefato C17 no repo é o **prompt** `PROMPTS/W5-C17-relatorios.md`. **Encaminhamento:** rodar/fechar a auditoria dedicada do C17 **antes** de re-auditar a wave.

**O lado bom (o sistema, fora do gate do C17, está saudável):** zero regressão funcional (suíte de 807 testes verde, round-trip de migrations verde), reuso do C16 **intacto e verbatim**, acesso a Relatórios **coerente** entre proxy e backend, e o **corte do C18 está limpo no código** (sem atalho de relatórios, sem sobra órfã). As pendências restantes são de **documentação** (o corte do C18 não está registrado) e de **higiene de lint/format**.

---

## 2. Achados (por severidade, com evidência reproduzível)

### 🔴 F-01 (Crítico) — `docs/audits/AUDITORIA-C17.md` ausente → Wave 5 NO-GO automático (Área A1/A3)

- **Evidência:**
  - `Glob docs/audits/*` → `AUDITORIA-WAVE-1.md`, `AUDITORIA-WAVE-2.md`, `AUDITORIA-WAVE-3.md`, `wave-0-audit.md`, `wave-0-remediation.md`. **Não há `AUDITORIA-C17.md`.**
  - `Glob **/AUDITORIA*` → só os três `AUDITORIA-WAVE-*.md`. `Glob **/*C17*` → só `PROMPTS/W5-C17-relatorios.md` (o prompt, não a auditoria).
  - `Grep "C17|AUDITORIA-C17|Relat[óo]rios"` em `docs/audits/` → *No files found*.
- **Impacto:** O fechamento de wave **se apoia** no veredito interno do C17. Sem ele, a Área A não pode ser marcada PASSA e a wave **não pode** ser dada como GO (§A3: "Não prossiga fingindo que o núcleo está são"). Crítico por definição do prompt.
- **Recomendação:** Executar a auditoria dedicada do C17 (recomputação métrica-por-métrica das fórmulas DP-3 / ADR-088, distribuição soma 100%, CSV, 403 não-admin) e produzir `docs/audits/AUDITORIA-C17.md` com veredito GO/NO-GO. Só então re-rodar este fechamento de wave.
- **STATUS: ✅ RESOLVIDO (Sessão 25).** `docs/audits/AUDITORIA-C17.md` criada — **GO**. Recomputação independente (workflow adversarial 12 áreas + crítico + auditor humano); descobriu/corrigiu o achado M-1 (*time-bomb* de relógio na fixture). Sem Crítico/Alto de métrica.

### 🟠 F-02 (Alto) — Gate de lint/format do repositório VERMELHO; a CI do job `api` falha (Área D1)

- **Evidência (reproduzível, equivalente à CI):**
  ```
  $ cd apps/api && uv sync --frozen && uv run ruff version
  ruff 0.15.16 (6c498ab53 2026-06-04)        # == versão do uv.lock (a mesma da CI)
  $ uv run ruff check .
  Found 16 errors.                            # 15× E501 (linha > 100) + 1× F841 (var não usada)
  $ uv run ruff format --check .
  17 files would be reformatted, 149 files already formatted
  ```
  - A CI roda **exatamente** esses gates: `.github/workflows/ci.yml:70-72` → `uv run ruff check .` **e** `uv run ruff format --check .`. Como ambos saem `!= 0`, o passo "Lint (ruff)" do job `api` **falha** e o pipeline em `develop` fica vermelho (não foi possível confirmar via `gh` — não instalado no ambiente; conclusão sustentada pela reprodução local com o lockfile congelado).
  - **`ruff check` (16):** todos em **arquivos de teste do W4-C16** — `tests/integration/test_dashboard_endpoints.py` (E501 + `F841 p_hoje_transito`) e `tests/integration/test_provas_listagem_atrasada_endpoints.py` (E501). **Dívida pré-existente**, já reconhecida em `SESSION_LOG.md:83` (Sessão 22), **não** introduzida pelo C17.
  - **`ruff format` (17):** inclui **fontes de produção do C17** (`src/adapters/outbound/db/relatorios_repository.py`, `src/application/relatorios.py`, `tests/integration/test_relatorios_endpoints.py`) **e** arquivos antigos (`src/domain/provas.py`, `src/domain/state_machine/rules.py`, `src/adapters/outbound/db/movimentacoes_repository.py`, vários testes W3/W4). O alcance amplo sobre arquivos estáveis sugere um **bump de versão do ruff** sem um `ruff format .` subsequente em todo o repo; o C17 também contribuiu com arquivos não formatados.
- **Impacto:** Viola a DoD §9 ("Sem erros... verde no CI") e o critério de GO §5(d). É **conteúdo cosmético** (comprimento de linha, formatação, 1 variável não usada) e **trivialmente corrigível**, mas mantém o gate vermelho — bloqueia um GO limpo.
- **Recomendação:** `uv run ruff check --fix .` (resolve o F841) + quebrar as linhas E501 (ou anotar `# noqa` justificado nos testes), e `uv run ruff format .` em todo o repo; re-rodar os dois gates até verdes. *(Correção fora do escopo desta auditoria — read-only.)*
- **STATUS: ✅ RESOLVIDO (Sessão 25).** `F841 p_hoje_transito` corrigido **preservando o seed** (só removido o binding); `ruff format .` aplicado (17 arquivos). `ruff check .` ✅ + `ruff format --check .` ✅ + `mypy` ✅. Suíte api completa re-rodada: **813 passed** — sem regressão.

### 🟡 F-03 (Médio) — Corte do C18 **não registrado**; docs o tratam como pendente (dívida fantasma) (Área C4)

- **Evidência:** Nenhum dos 5 docs registra o corte do C18; todos o listam como **próximo passo / pendente**:
  - `README.md:148` → `| **5 · Relatórios/UX** | 17 Relatórios ✅ · 18 Atalhos | 🔄 em andamento |` (C18 sem nota de corte; wave "em andamento").
  - `CLAUDE.md:200` (§7 roadmap) → `- **Wave 5 — Relatórios/UX:** 17 Relatórios · 18 Atalhos`; e a nota do §9 termina em "**Próximo: W5-C18 (Atalhos rápidos).**".
  - `DECISIONS.md:665` → "Próximo passo: ... e então **W5-C18 — Atalhos rápidos** (RF-017) ... Encerra a Wave 5 com o C17."
  - `SESSION_LOG.md:58` e `:87` → próximo passo = W5-C18.
  - `CHANGELOG.md [Unreleased]` → registra **só o C17**; **nenhuma** entrada `Removed`/`Deprecated` para o C18.
  - `Grep "cortad|descartad|fora de escopo|decisão de produto"` ligado ao C18 nos 5 docs → **zero**. Não há ADR do corte.
- **Impacto:** Dívida fantasma — a próxima sessão lerá os docs e tentará **implementar o C18** que produto decidiu **não** fazer. (Não bloqueia o GO por §4, mas precisa ser sanado.)
- **Recomendação (não implementada — read-only):** Registrar um **ADR** em `DECISIONS.md` formalizando o corte do C18 por decisão de produto; marcar o C18 como **descartado / fora de escopo** (não "pendente") em CHANGELOG, SESSION_LOG, README (roadmap) e CLAUDE.md §7; redirecionar o "Próximo passo" para **W6-C19**.
- **STATUS: ✅ RESOLVIDO (Sessão 25).** **ADR-095** registra o corte do C18; `CLAUDE.md §7/§9`, `README.md`, `DECISIONS.md`, `CHANGELOG.md`, `SESSION_LOG.md` marcam o C18 **descartado** e o próximo passo = re-auditar / W6-C19. **Guard de regressão** em `dashboard-view.test.tsx` (`corte do C18: nenhum atalho/CTA leva a Relatórios`) — falha se o atalho reaparecer.

### 🟡 F-04 (Médio) — Documentação **stale**: aba Clicheria marcada pendente embora já reconstruída (Área D3)

- **Evidência:** O commit `9e3fbde` (2026-06-19, "reconstrói a aba Clicheria fiel ao design (bento) — fecha o C17 visual") veio **depois** de `f7dc4b5` (2026-06-18) que gravou a Sessão 23 + ADR-094; `9e3fbde` tocou `clicheria-tab.tsx`/`widgets.tsx`/`.css`/`.py` mas **nenhum `.md`**. Logo, ficaram falsos:
  - `SESSION_LOG.md:54` "Aba Clicheria ainda no layout antigo — reconstruir" e `:60` "fecha quando a aba Clicheria for reconstruída";
  - `DECISIONS.md:628`/`:664` "Aba Clicheria pendente de reconstrução";
  - `CHANGELOG.md:14` "**Pendente:** a aba Clicheria segue no layout antigo".
- **Impacto:** Docs de contexto divergem do código real (a aba já está em bento). Não bloqueia, mas confunde a continuidade.
- **Recomendação:** Atualizar SESSION_LOG/DECISIONS/CHANGELOG para refletir que a Clicheria foi reconstruída (commit `9e3fbde`) e o C17 visual está completo.
- **STATUS: ✅ RESOLVIDO (Sessão 25).** `SESSION_LOG.md` (Sessão 23), `DECISIONS.md` (ADR-094 + checklist) e `CHANGELOG.md` atualizados: Clicheria reconstruída (`9e3fbde`), C17 visual completo.

### 🟡 F-05 (Médio) — Claims de qualidade **falsos** nos docs ("ruff/format/prettier limpos") (Área D3)

- **Evidência:** `SESSION_LOG.md:50-51` (Sessão 23) e `CHANGELOG.md:14` afirmam "`ruff`/`mypy --strict`/`lint`/`build`/`prettier` ... limpos/verdes". A execução real (F-02) mostra `ruff check .` (16) e `ruff format --check .` (17) **vermelhos**, e `prettier --check` vermelho no arquivo não commitado `nova-prova-view.tsx`. (Apenas `mypy` — *Success, 98 files* — e o `pnpm` web — lint/build/vitest 178 — estão de fato verdes.)
- **Impacto:** Os docs declaram um estado verde que não existe; ilude a próxima sessão e a DoD.
- **Recomendação:** Não declarar "limpos" enquanto os gates estiverem vermelhos; ou corrigir (F-02), ou rebaixar a afirmação citando a dívida real.
- **STATUS: ✅ RESOLVIDO (Sessão 25).** Os gates foram **corrigidos** (F-02) e as afirmações reconciliadas: `SESSION_LOG.md` (Sessão 23) e `CHANGELOG.md` agora anotam a dívida real de `ruff format`/`prettier` daquela sessão (fechada na remediação), sem declarar "limpos" o que não estava.

### ⚪ F-06 (Baixo) — Arquivo não commitado `nova-prova-view.tsx` deixa o `prettier --check` local vermelho

- **Evidência:** `git status` mostra `M apps/web/.../nova-prova-view.tsx`; `git diff` = **um único espaço em branco no fim de uma linha** (`<div className={styles.campo}> `). `pnpm format:check` falha **só** nesse arquivo. É um artefato da **árvore de trabalho** (mudança local pré-existente, não desta auditoria); o código **commitado** (que a CI verifica) não é afetado.
- **Impacto:** Nulo para a CI/código commitado; ruído local.
- **Recomendação:** `pnpm prettier --write` no arquivo (ou descartar a mudança). Fora do escopo desta auditoria (read-only; não toco código de produção).
- **STATUS: ✅ RESOLVIDO (Sessão 25).** `prettier --write` aplicado; o diff (só o espaço em branco) sumiu — `pnpm format:check` web ✅.

### ⚪ F-07 (Baixo, informativo) — Barras CSS do C17 não declaram `transition` (snap ao valor)

- **Evidência:** `relatorios.module.css` define `transform-origin` em `.rankBarFill`/`.barraFill`/`.volFill` mas nenhuma `transition`; o `scaleX(...)` inline aplica instantaneamente. **Não** é defeito de `prefers-reduced-motion` (não há animação a suprimir) — apenas as "barras animadas" do design são, na prática, estáticas.
- **Recomendação:** Opcional — se o design pedir crescimento animado, adicionar `transition: transform var(--motion-micro) ...` (já zera sob reduced via `globals.css`).
- **STATUS: ⏸️ MANTIDO POR DESIGN (Sessão 25).** Barras renderizando no valor instantaneamente **não é defeito** (correto e seguro — só `transform`); adicionar crescimento animado é **decisão de design** que o dono não pediu. Deixado como está (sem escopo novo); reabrir no W6-C19 (camada de animações) se desejado. Não bloqueia.

---

## 3. Matriz de cobertura (Áreas A–D)

| Área | Item | Resultado | Evidência |
| --- | --- | --- | --- |
| **A** | A1 — `AUDITORIA-C17.md` existe? | **FALHA** | Ausente (F-01) |
| **A** | A2 — Críticos/Altos do C17 remediados? | **N/A** | Sem relatório para incorporar |
| **A** | A3 — C17 não-GO ⇒ Wave NO-GO | **FALHA → NO-GO** | F-01 |
| **B** | B1 — Reuso do C16 sem dano (nº "Atrasadas" bate) | **PASSA** | `relatorios_repository.py:28` e `dashboard_repository.py:22` importam o MESMO `SQL_PREDICADO_ATRASADA` de `atraso_sql.py`; C17 reusa `SQL_ULTIMO_EVENTO` + `private.instante_limite_atraso` verbatim; `horas_uteis_entre` (0021) é aditiva. Número igual por construção. |
| **B** | B2 — Regressão Waves 0–4 | **PASSA** | `pytest -q` (REQUIRE_DB_TESTS=1, PG `.tmp-pg` 5432): **807 passed in 145.93s**, exit 0 |
| **B** | B3 — Migrations/RLS aplicam limpo (round-trip) | **PASSA** | `test_migrations.py` faz `downgrade base → upgrade head → downgrade base → upgrade head` (head **0021**, `private.horas_uteis_entre` cria/remove) — verde na suíte |
| **B** | B4 — Acesso consistente (proxy × backend) | **PASSA** | `cells.json:9` `"relatorios":"admin"`; `access-matrix.ts:41,66` + `rbac.py` RECURSOS_ADMIN (flag admin), travados por testes de equivalência; proxy `podeAcessarRota` redireciona+toast; endpoints `get_relatorios_service` → 403 em 4 abas + `/exportar` |
| **B** | B5 — Navegação coerente (sidebar) | **PASSA** | `nav-items.ts:33` item "Relatórios" filtrado por `podeAcessarRota` no Sidebar → some para não-admin |
| **C** | C1 — Sem atalho/CTA a Relatórios fora da sidebar | **PASSA** | `grep '/relatorios'` (21 hits) = só rota própria + sidebar + matriz/fetch; dashboard **não** referencia relatórios |
| **C** | C2 — Sem sobra meio-construída do C18 | **PASSA** | Sem rota `/atalhos`, sem componente de atalhos, sem flag, sem import morto, sem TODO; hits de "atalho" = só os 2 do C16 |
| **C** | C3 — Atalhos do C16 coerentes sozinhos | **PASSA** | `dashboard-view.tsx:228` Escanear→`/escanear` (universal) · `:239` Nova Prova→`/provas/nova` (gated `podeCriarProva`, 3Studio) |
| **C** | C4 — Docs refletem o corte do C18 | **FALHA** | F-03 (docs tratam C18 como pendente; sem ADR) |
| **D** | D1 — ruff/mypy/pytest/lint/build verdes | **FALHA (parcial)** | mypy ✅ · pytest ✅ · web lint/build/vitest ✅ — **ruff check ❌ + ruff format ❌** (F-02); prettier web ❌ só em arquivo não commitado (F-06) |
| **D** | D2 — Sem segredos versionados; stateless | **PASSA** | `git ls-files` só `.env.example` (valores vazios); `.gitignore` protege `.env*`; `git grep` sem chaves reais (só dummies de teste); C17 stateless (dataclasses frozen, sessão por request) |
| **D** | D3 — 5 docs refletem a realidade | **FALHA** | F-04 (Clicheria stale) + F-05 (claims "limpos" falsos) |
| **D** | D4 — `prefers-reduced-motion` + responsivo | **PASSA** | Recharts `isAnimationActive={!reduced}`, pílulas Framer `DURATION.instant`, `AnimatedCounter` salta sob reduced; barras CSS só `transform`/`opacity`; `@media (prefers-reduced-motion)` + tokens zerados; breakpoints 1100/767px refluem |

---

## 4. Nota sobre o C18 (Atalhos Rápidos)

- **Status:** **CORTADO por decisão de produto** (conforme premissa do prompt de auditoria) — não se quer o atalho de relatórios.
- **O corte está limpo no CÓDIGO (Áreas C1/C2/C3 = PASSA):** não existe atalho/CTA para Relatórios fora da sidebar; o acesso a Relatórios é **exclusivamente** pelo item de menu (3Studio). Não há rota/componente/flag/import/TODO de "atalhos rápidos" meio-construído. Os dois atalhos que o **C16** já trouxe (Escanear, Nova Prova) funcionam **sozinhos**, role-aware, levando ao módulo certo.
- **O corte NÃO está registrado nos DOCS (Área C4 = FALHA — F-03):** os 5 docs ainda tratam o C18 como **próximo passo/pendente**, e **não há ADR** do corte. **Recomendação (não implementada):** criar o ADR do corte e marcar o C18 como descartado/fora-de-escopo nos roadmaps, eliminando a dívida fantasma.

---

## 5. Apêndice — artefatos de auditoria (em `audit/`)

Nenhum teste de produção foi alterado. Foram capturadas as saídas dos comandos executados (evidência reproduzível) em `audit/logs/`:

| Arquivo | Conteúdo |
| --- | --- |
| `audit/logs/api-pytest.log` | Suíte completa `pytest -q` (@db, REQUIRE_DB_TESTS=1) → **807 passed**, exit 0 (B2) |
| `audit/logs/api-ruff-mypy.log` | `ruff check .` → 16 erros (W4) · `mypy` → Success (98 files) (D1) |
| `audit/logs/api-ruff-format.log` | `ruff format --check .` → 17 arquivos a reformatar (D1/F-02) |
| `audit/logs/web-test.log` | `vitest run` → **178 passed** (27 files), exit 0 (D1) |
| `audit/logs/web-lint-build.log` | `pnpm lint` + `pnpm build` → exit 0; rota `/relatorios` no manifesto (D1) |
| `audit/logs/web-format.log` | `prettier --check` → vermelho só em `nova-prova-view.tsx` não commitado (F-06) |

**Sobre testes de auditoria descartáveis:** não foi necessário escrever um teste novo de equivalência para B1. O número compartilhado "Atrasadas" bate **por construção** — Dashboard (C16) e Relatórios (C17) consomem o **mesmo** `SQL_PREDICADO_ATRASADA` (mesma função `private.instante_limite_atraso`, mesmo delay de `system_settings`, mesma lista de terminais) do módulo único `atraso_sql.py`; provado por leitura de código + as duas suítes verdes. B3 já é coberto pelo round-trip completo de `test_migrations.py` (verde na suíte de 807).

**Limitação declarada (D2, parte "console em uso normal"):** não houve navegação live das telas (sem app de pé/auth/dados neste ambiente). `build`/`lint`/`vitest` estão verdes; a verificação de console em uso real deve ser coberta pela auditoria dedicada do C17 + smoke manual.

---

## 6. Encaminhamento (§5/§8 do prompt)

**⛔ NO-GO.** Para reverter, na ordem:

1. **(Crítico — F-01)** Rodar/fechar a **auditoria dedicada do C17** e produzir `docs/audits/AUDITORIA-C17.md` (GO ou GO-após-remediação).
2. **(Alto — F-02)** Limpar o gate de lint/format do repo (`ruff check --fix` + E501 + `ruff format .`) até a CI do job `api` ficar verde.
3. **(Médios — F-03/04/05)** Registrar o ADR do corte do C18 e sincronizar os 5 docs (C18 descartado; Clicheria reconstruída; remover claims "limpos" falsos).
4. **Re-auditar** o fechamento da Wave 5.

**Próximo passo após GO:** **W6-C19 — Camada Transversal de Animações** (abre a Wave 6).
