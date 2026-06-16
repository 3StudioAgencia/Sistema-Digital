# Prompt de Execução — W2-C09 · Tela de Configurações do Sistema

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–1 concluídas e auditadas (GO)** e os **C06, C07 e C08 mergeados**, e a **imagem do design anexada** (tela "Configurações do sistema"). Este componente **fecha a Wave 2**. Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (**robustez, escalabilidade, mínimo de requisições, observabilidade**, animações leves), arquitetura §5 (Ports & Adapters), gestão de schema/RLS (DAT §2), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–1 + C06–C08 entregues):**
- C04: **app shell** (sidebar + shell branco); **modal**; **toasts**; **fundação de motion**.
- C05: **`access-matrix.ts`** + middleware + `useAuthorization` + **helpers de RLS** + propagação de claims (ADR-008). *A tabela `system_settings` foi listada na intenção de RLS do C05, mas (como `provas`/`movimentacoes`/`audit_log`) é criada pelo componente que a possui — este (ver DP-1).*
- C06: geração de **etiqueta** com **template padrão parametrizável** (o C09 configura essa parametrização — RN-011).
- C07/C08: listagem/detalhe de provas. **Reuse tudo isso — não recrie.**

**Insumo confirmado:** o design da tela "Configurações do sistema" no Figma, anexado. **Atenção:** o design é um **scaffold de padrão** — mostra o card "Tempo de atraso" **duplicado** (placeholder) e um card **"Outras configs"** vazio. A **lista real** de configurações vem do RF-022 (ver §1.1 e DP-6).

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — modelo de settings, RLS/leitura, significado de "template personalizado", cache vs. imediatismo, lista de parâmetros — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, confirme o estado das Waves 0–1 + C06–C08 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas.
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte.
4. **Nunca invente** parâmetros de configuração, nomes de chave/coluna/variável, o conjunto de itens customizáveis do template, ou valores de design. Em dúvida, **pergunte**.

---

## 0.2 Fidelidade ao design

**Tela "Configurações do sistema"** (dentro do shell do C04): título "Configurações do sistema"; uma sequência de **cards de configuração** (shell-branco-interno), cada um com **título**, **descrição** e os **campos** da configuração + um botão **"Salvar"** (amarelo) **por card** (save granular). O design ilustra o card **"Tempo de atraso"** (descrição "Uma prova digital sem movimentação por mais que esse tempo é considerada atrasada", campo **"Tempo (horas úteis)" = 48**) e um card **"Outras configs"** (placeholder).

> **O card "Tempo de atraso" aparece duplicado no design — isso é placeholder, não dois settings iguais.** Implemente os settings **reais** (§1.1 / DP-6), no **mesmo padrão visual** (card + Salvar por item).

Tokens, cores e tipografia seguem o que já está estabelecido (C04/C07/C08); **não chute** — se houver link do Figma, extraia via Dev Mode/MCP; senão, confirme.

---

## 1. Objetivo do componente

Entregar a **tela de Configurações do Sistema**, **exclusiva do 3Studio**, com os parâmetros configuráveis do RF-022 — em especial o **tempo de atraso** (horas úteis, padrão 48; aplicado **imediatamente** aos cálculos) e a **configuração do template de etiqueta** (padrão/personalizado) — persistidos em `system_settings` com **RLS 3Studio-only**, e consumíveis pelas features que dependem deles (dashboard C16, etiqueta C06).

Referências: Backlog **C09** · Requisitos **RF-022, RN-008, RN-011, US-016, RNF-011, RNF-020** · §7 (Matriz — 3Studio only) · C06 (template parametrizável) · C05 (`access-matrix`, RLS, propagação de claims).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **Acesso (Matriz §7 / RF-022):** a tela é **exclusiva do 3Studio** — gateada pelo **middleware** (C05) **e** com **escrita 3Studio-only** na RLS. Perfis não-3Studio recebem acesso negado.
2. **Parâmetros do RF-022:** (a) **tempo em horas úteis sem movimentação** para classificar como **Atrasada** (padrão **48**) — RN-008, US-016; (b) **template de etiqueta** (padrão/personalizado) — RN-011; (c) **demais parâmetros operacionais** definidos pelo administrador.
3. **Imediatismo (US-016):** ao salvar o tempo de atraso, o novo valor é **aplicado imediatamente** a todos os cálculos. *(Como configurações podem ser cacheadas — RNF-020, stale-while-revalidate/TTL —, o save precisa invalidar o cache. Ver DP-4.)*
4. **Fronteira de cálculo:** o C09 **armazena** o tempo de atraso; **quem computa** "atrasada" (contagem em **horas úteis** sobre o tempo no **mesmo status** — RN-008) é o **C16 (Dashboard)**. A janela de horário comercial é **fixa** (RNF-011: seg–sex 07–18). O C09 **não** computa atraso.
5. **Template de etiqueta:** o C06 entregou um **template padrão parametrizável**; o C09 configura essa parametrização ("padrão" = defaults; "personalizado" = sobrescritas). O significado exato de "personalizado" precisa ser definido (DP-5). A **geração** continua no C06 (que **lê** a config server-side).
6. **`system_settings`** ainda **não existe** — este componente a cria (DP-1).

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Tela "Configurações do sistema"** dentro do shell do C04, fiel ao padrão do design (cards + "Salvar" por item), **gateada ao 3Studio**: card **Tempo de atraso** + card(s) de **template de etiqueta** + os parâmetros reais definidos (DP-6).
- **Backend / Banco — `system_settings`:** migration criando a tabela (modelo da DP-1) + **RLS** (escrita 3Studio-only; leitura conforme DP-2), versionada em `/migrations/rls/`; um **registro/serviço de settings** com tipo/validação/default por chave conhecida.
- **Endpoints (Ports & Adapters):** ler e **salvar** settings (validação por chave; 3Studio-only via guard + RLS); **invalidação de cache** no save (DP-4). Logs estruturados.
- **Consumo:** garantir que o **tempo de atraso** e o **template de etiqueta** sejam **legíveis server-side** pelas features que os usam (dashboard C16 — futuro; etiqueta C06 — agora), conforme DP-2. *(Integrar a config do template ao gerador do C06: a etiqueta passa a respeitar a configuração salva.)*
- **UI:** cards com **save granular** + feedback por card (toast/inline); estados de loading/erro; validação em tempo real (ex.: tempo de atraso numérico, > 0).
- **Animações** (continuidade, sobre os tokens; GPU-only; `prefers-reduced-motion`).
- **Documentação** (`docs/configuracoes.md`): o modelo de `system_settings`, as chaves conhecidas e validações, a RLS, a integração com a etiqueta (C06) e a fronteira do cálculo de atraso (C16). **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Cálculo de "atrasada" / contador "Atrasadas"** (Componente **16** — Dashboard). O C09 só **armazena** o tempo de atraso.
- ❌ **A lógica de horário comercial** para a contagem de atraso (é do C16); a janela é fixa (RNF-011).
- ❌ **Upload de template totalmente custom** (a menos que a DP-5 decida o contrário — provavelmente fora do v1.0).
- ❌ Relatórios, dashboard, ou qualquer item de Waves 3+.

> Vontade de adiantar o cálculo de atraso, o dashboard ou um editor de template completo: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Acesso 3Studio:** página gateada pelo middleware (C05) **e** escrita na RLS 3Studio-only — **defesa em profundidade** (não confie só no middleware).
2. **`system_settings` com RLS** versionada em `/migrations/rls/` (escrita 3Studio-only; leitura conforme DP-2); reaplicável após recriação de tabela; o backend lê server-side com claims propagados onde aplicável (ADR-008).
3. **Imediatismo + cache (US-016 × RNF-020):** se as configurações forem cacheadas, o **save invalida o cache** (e/ou usa stale-while-revalidate com revalidação no save) para a mudança **valer na hora**.
4. **Validação por chave:** cada setting tem **tipo/validação/default** definidos (ex.: tempo de atraso = inteiro positivo em horas úteis); validar no **front e no back**.
5. **Integração com a etiqueta (C06):** o gerador de etiqueta passa a **respeitar a configuração** salva (template padrão/personalizado) — sem reimplementar a geração.
6. **Estilização:** **CSS Modules**; fidelidade ao padrão do design; consistente com C04/C07/C08. Animações `transform`/`opacity`; **`prefers-reduced-motion`** obrigatório.
7. **Estados de loading/erro** e **error boundary** na rota (RNF-014/016).
8. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada.

### Bloco A — Modelo de configurações e acesso

**DP-1 — Modelo da tabela `system_settings`.**
**[Recomendado]** **chave-valor** (`key`, `value` jsonb, `updated_at`, `updated_by`) + um **registro de settings no app** definindo, por chave conhecida, o **tipo/validação/default** — extensível para "Outras configs". Alternativa: tabela **tipada de linha única** (uma coluna por setting; type-safe, mas migration por novo setting). Confirmar o modelo.

**DP-2 — RLS e leitura por features compartilhadas.**
**Escrita 3Studio-only.** Mas o **tempo de atraso** alimenta o dashboard (C16, **todos** os perfis) e o **template** alimenta a etiqueta (C06) — ambos **lidos server-side**. **[Recomendado]** leitura **client-side 3Studio-only**; o **backend** lê `system_settings` em **contexto server-side** para essas computações (o valor bruto não precisa ser exposto a clientes não-admin). Confirmar (vs. liberar leitura `authenticated` para chaves não sensíveis).

**DP-3 — Acesso à página.**
**[Recomendado]** exclusiva do **3Studio** (middleware C05 + RLS) — caso claro da Matriz §7. Confirmar.

### Bloco B — Os parâmetros

**DP-4 — Tempo de atraso: imediatismo vs. cache.**
Inteiro, **horas úteis**, default **48** (RF-022a/RN-008). **Aplicado imediatamente** ao salvar (US-016). **[Recomendado]** se houver cache de configurações (RNF-020), o **save invalida o cache**. Confirmar. *(Fronteira: o **cálculo** de "atrasada" em horas úteis é do **C16**; a janela de horário comercial é **fixa** — RNF-011. Confirmar se feriados/calendário devem ser configuráveis — provável fora do v1.0.)*

**DP-5 — Configuração do template de etiqueta (RN-011 / RF-022b).**
"Padrão ou personalizado" — **"personalizado" é subespecificado.** **[Recomendado]** "personalizado" = **sobrescrever os parâmetros que o C06 já expôs** no template parametrizável (ex.: alternar o logo "studio&ART", quais campos opcionais aparecem, ajustes do layout), com "padrão" = os defaults — **não** um editor/upload de template totalmente custom (maior, provável fora do v1.0). Confirmar o **conjunto exato de parâmetros customizáveis** (alinhado ao que o C06 parametrizou).

**DP-6 — Lista real de settings e padrão de UI.**
O design é **scaffold** (card "Tempo de atraso" **duplicado** + "Outras configs" vazio). A lista real (RF-022) é: **tempo de atraso** + **template de etiqueta** + **demais parâmetros** que você definir. **[Recomendado]** implementar **tempo de atraso + template de etiqueta** agora; "demais parâmetros" só se você especificar quais. Padrão de UI: **card por setting com "Salvar" próprio** (save granular + feedback por card). Confirmar a **lista desta sessão** e o padrão de save.

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Backend / Banco — `apps/api/`
- **Migration** (`versions/00xx_system_settings.py`): tabela `system_settings` (modelo da DP-1); `downgrade`. **RLS** versionada em `migrations/rls/system_settings_*.sql` (DP-2/DP-3).
- **Registro/serviço de settings:** definição por chave (tipo/validação/default — ex.: `delay_horas_uteis` int>0 default 48; chaves do template — DP-5); leitura/escrita; **invalidação de cache** no save (DP-4).
- **Endpoints HTTP:** `GET /api/settings` (3Studio) e `PATCH/PUT /api/settings/{key}` (salvar; validação; guard 3Studio + RLS). Logs estruturados.
- **Integração com o gerador de etiqueta (C06):** a geração passa a **ler** a config do template e respeitá-la.

### 5.2 Frontend — `apps/web/`
- **`app/(app)/configuracoes/page.tsx`** — tela de Configurações, **gateada ao 3Studio**: cards de **Tempo de atraso** e **Template de etiqueta** (DP-5/DP-6), com **"Salvar" por card** + feedback; validação em tempo real; estados de loading/erro.
- Animações sobre os tokens (GPU-only, `prefers-reduced-motion`).

### 5.3 Documentação — `docs/`
- `docs/configuracoes.md`: modelo de `system_settings`, chaves conhecidas + validações, RLS, integração com a etiqueta (C06), e a **fronteira do cálculo de atraso** (C16). Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Acesso negado a perfis não-3Studio** (middleware **+** RLS) — defesa em profundidade; query direta de escrita por não-3Studio → bloqueada.
2. ✅ **Tempo de atraso** salvo (inteiro, horas úteis, default 48) e **aplicado imediatamente** (US-016) — o cache, se houver, é **invalidado** no save.
3. ✅ **Template de etiqueta** configurável (padrão/personalizado — DP-5); a **geração da etiqueta (C06) respeita** a configuração salva.
4. ✅ **`system_settings`** criada com **RLS** versionada; leitura conforme DP-2 (features compartilhadas continuam funcionando server-side).
5. ✅ **UI**: cards com **save granular** + feedback; validação em tempo real; **fidelidade ao padrão do design**; **animações** com `prefers-reduced-motion`; responsivo.
6. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**; migration `upgrade`/`downgrade` limpa; RLS reaplicável.

---

## 7. Testes desta camada

**Backend / Banco**
- Acesso: 3Studio salva; **não-3Studio → negado** (guard **e** RLS — query direta de escrita por não-3Studio bloqueada).
- Validação por chave: tempo de atraso rejeita não-inteiro/≤ 0; chaves de template validadas.
- Imediatismo: após salvar, a leitura subsequente (e o consumo server-side) reflete o novo valor (cache invalidado).
- Integração etiqueta: a geração (C06) reflete a config salva (padrão vs. personalizado).
- Migration `upgrade`/`downgrade`; RLS aplicada/reaplicável.
- Roda **offline** (Postgres local; JWTs de teste por perfil).

**Frontend**
- Render fiel ao padrão; **save por card** + feedback; validação em tempo real; estados de loading/erro.
- Página **negada a perfil não-3Studio** (gating do C05).
- `prefers-reduced-motion`.
- **E2E (Playwright):** salvar tempo de atraso como 3Studio; tentar acessar como Vendedor → negado; configurar template e verificar reflexo na etiqueta.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, confirme Waves 0–1 + C06–C08 (template parametrizável do C06, middleware/RLS do C05).
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. Backend: migration de `system_settings` + RLS; registro/serviço de settings (tipos/validações/defaults); endpoints (3Studio + RLS); invalidação de cache. Testes verdes.
4. Integração com o gerador de etiqueta (C06): respeitar a config do template.
5. Frontend: tela de Configurações (cards + save granular), gateada ao 3Studio; validação; estados de loading/erro.
6. Animações sobre os tokens; responsividade; `prefers-reduced-motion`.
7. `docs/configuracoes.md`.
8. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
9. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: tela de Configurações; tabela `system_settings` + RLS; parâmetro de tempo de atraso; configuração do template de etiqueta (integrada ao C06).
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **modelo de `system_settings`** (DP-1); (b) **RLS e leitura por features compartilhadas** (DP-2); (c) **imediatismo vs. cache** (DP-4); (d) **escopo de "template personalizado"** (DP-5). Status *Aceita* onde aplicável.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes/cobertura, **pendências**, e **próximo passo** = **W3-C10 · Escaneamento por Câmera + Fallback Manual (Mobile-First)** — *e registre que a **Wave 2 está concluída** (sugerir auditoria da Wave 2 antes da Wave 3, como foi feito na Wave 1).*
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre o **modelo de `system_settings`**, as **chaves de configuração** e a **integração da etiqueta** com a config. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap: **Wave 2 concluída**.
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **acesso negado a não-3Studio** em middleware **e** RLS), **migration e RLS versionadas/documentadas**, sem erro de console/log crítico, docs do módulo, error boundary, animações com `prefers-reduced-motion`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w2-c09): ...`, `chore(w2-c09): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. acesso negado a não-3Studio nas duas camadas, imediatismo do tempo de atraso e a etiqueta respeitando a config), decisões registradas, pendências, o **status da Wave 2 (concluída)** e o **comando exato** para iniciar a próxima sessão (**W3-C10**), sugerindo a **auditoria da Wave 2** antes.

---

### Lembrete final
Configurações parecem simples, mas guardam duas pegadinhas: o **acesso** (precisa ser negado a não-3Studio nas **duas** camadas — middleware **e** RLS) e o **imediatismo** (de nada adianta salvar o tempo de atraso se um **cache** segura o valor antigo — invalide-o). E o **template de etiqueta** fecha o laço com o C06: a config salva aqui tem que **de fato** mudar a etiqueta gerada lá. **Na dúvida, pare e pergunte.** Esta sessão fecha a Wave 2 — deixe-a sólida para auditar antes de entrar no fluxo de movimentação (Wave 3).
