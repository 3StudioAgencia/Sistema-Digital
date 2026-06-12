# Prompt de Execução — W1-C05 · Controle de Acesso por Perfil (Matriz RBAC em duas camadas)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz do repositório e o **C04 concluído e mergeado** (pré-condição obrigatória). Este componente **fecha a Wave 1**. Não há novas telas de design: o entregável é majoritariamente backend (hook + RLS) + middleware + a fiação da UI já existente (filtro da sidebar do C04). Trabalhe a sessão inteira neste único componente.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize em especial:
- **§2 / §2.1** — hierarquia de fontes e **divergências**. *A reconciliação do modelo Setor × Administrador foi decidida no C04 (DP-1) e registrada aqui — você vai consumi-la (ver §0.2).*
- **§3** — pilares: **robustez, escalabilidade, mínimo de requisições ao Supabase, observabilidade**.
- **§4 / §5** — stack e Ports & Adapters.
- A **Matriz de Acesso por Perfil (Requisitos v1.0, §7)** é a **fonte única de verdade** do controle de acesso. A arquitetura de RBAC (DAT **§7**) é **defesa em profundidade em duas camadas independentes**: **middleware do App Router (Next.js)** e **Row Level Security do PostgreSQL**.
- Propagação de claims para a RLS quando o acesso é via backend (**ADR-008**), e estratégia de conexão (**ADR-007**).

**Estado atual do repositório (Wave 0 + C03 + C04 entregues):**
- C03: `@supabase/ssr` (clients browser/server + `middleware.ts` **de refresh de sessão**, com marcador para o ponto onde o C05 adiciona enforcement), verificação de JWT no backend (**ES256/JWKS + HS256**), inatividade 30 min, fundação de motion.
- C04: **app shell** (sidebar + shell branco) reutilizável; tabela de domínio **`usuarios`** (PK = id do `auth.users`) com **RLS provisória restritiva**; provisionamento via Admin API gravando **setor/perfil no `app_metadata`**; sidebar com **itens de menu ainda sem filtro por perfil** (deixado para o C05) e páginas futuras como **placeholders**; sistema de **toasts** reutilizável.

**A Matriz de Acesso (Requisitos §7), por perfil — referência canônica:**
- Perfis: **3Studio** (Administrador), **Vendedor**, **Motorista**, **Clicheria**. Legenda: ● completo · ◐ parcial · ○ sem acesso.
- **Login, Escanear QR, Dashboard:** todos (●) — no Dashboard, os contadores respeitam o escopo da listagem.
- **Listagem / Detalhe / Timeline de Provas:** 3Studio e Clicheria ● (todas); **Vendedor ◐ (só as próprias)**; **Motorista ◐ (só as “Em Trânsito” / “Com Motorista (*)”)**. Acesso direto por URL fora do escopo é bloqueado.
- **Criar Prova, Cadastro de Usuários, Relatórios, Configurações, Log de Auditoria, Reiniciar Ciclo, Cancelar Prova:** **3Studio ●**, demais ○.

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — modelo, claims, escopo de RLS, comportamento do middleware, fronteira entre componentes — você **para, expõe o ponto com 2–3 opções e a sua recomendação, e aguarda a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, `DECISIONS.md` (a decisão da DP-1 do C04) e confirme o estado do C04 no repositório. **Apresente, de uma só vez e em bloco, todos os Pontos de Decisão da §4 — incluindo a Matriz derivada (DP-1) para confirmação.** Aguarde as respostas.
2. Só depois, comece a implementar na ordem da §8.
3. Surgindo nova ambiguidade, **pare imediatamente** e pergunte.
4. **Nunca invente** nomes de claims, de funções SQL, de rotas, de roles ou de variáveis. Em dúvida, **pergunte**.

---

## 0.2 Pré-condição e herança do C04 (leia antes de tudo)

1. **Modelo Setor × Administrador:** o C04 decidiu (DP-1) entre **(a)** `setor` + flag `administrador` ortogonal, ou **(b)** admin === setor 3Studio. **Leia a decisão registrada em `DECISIONS.md` / `CLAUDE.md §2.1` e derive a Matriz a partir dela.** A Matriz §7 acima está escrita no formato (b) (3Studio como administrador); se a decisão foi (a), aplique o ajuste documentado no C04 e **apresente a Matriz resultante para confirmação** (DP-1).
2. **A tabela `provas` ainda NÃO existe** — ela é criada no **C06** (que depende deste). Portanto o **escopo de dados de provas** (Vendedor vê as próprias; Motorista vê as “Em Trânsito”) **não pode ter RLS aplicada agora**. O C05 entrega a **fundação reutilizável**; o C06 aplica a RLS de linha das provas usando essa fundação (ver DP-3).

---

## 1. Objetivo do componente

Formalizar o **controle de acesso por perfil em duas camadas independentes (defesa em profundidade)**, tendo a **Matriz §7 como fonte única**:
1. **Camada superior — Middleware do App Router:** bloqueia **páginas** por perfil; acesso não autorizado → redireciona para a home do perfil com toast.
2. **Camada inferior — Row Level Security do PostgreSQL:** bloqueia **dados** por perfil; mesmo que o middleware seja burlado, a RLS protege.
Sustentadas por um **Custom Access Token Hook** que injeta os claims de perfil no JWT, pela **propagação desses claims** à sessão do banco quando o acesso é via backend (ADR-008), por um **`access-matrix.ts` centralizado** consumido pelo middleware e pela UI, e por um **harness de testes de equivalência** entre as duas camadas.

Referências: Backlog **C05** · Requisitos **§7** (Matriz), **RNF-006, RNF-018** · DAT **§7.1/§7.2** · **ADR-007, ADR-008**.

---

## 1.1 Fatos técnicos atuais (orientam a implementação)

1. **Custom Access Token Hook = função Postgres** `public.custom_access_token_hook(event jsonb) returns jsonb`, que **roda antes de cada emissão de token** (login **e** refresh). Deve ser **rápida**, **nunca quebrar a autenticação** e **preservar os claims obrigatórios** (`iss, aud, exp, iat, sub, role, aal, session_id, email, phone, is_anonymous`). Injeta os claims de perfil (**`setor`** e **`user_id`**, e `administrador`/perfil conforme DP-1).
2. **Posição dos claims:** a RLS do DAT §7.2 lê **`auth.jwt() ->> 'setor'`** e **`auth.jwt() ->> 'user_id'`** (nível superior). O hook **deve injetar os claims na mesma posição que a RLS lê** — alinhamento obrigatório, senão a RLS falha silenciosamente.
3. **Grants do hook (críticos):** `grant execute on function public.custom_access_token_hook to supabase_auth_admin;` + `grant usage on schema public to supabase_auth_admin;` + `revoke execute ... from authenticated, anon, public;`. Se o hook **ler a tabela `usuarios`** (que tem RLS), é preciso **conceder ao `supabase_auth_admin` acesso de leitura** a `usuarios` (grant + política RLS permitindo esse role).
4. **Leitura de claims no middleware:** use **`supabase.auth.getClaims()`** (verificação **local** com a chave assimétrica do C03) para a decisão de rota — é rápido e **não bate no servidor de auth a cada request** (pilar de mínimo de requisições). Reserve `getUser()` para quando precisar do estado confirmado pelo servidor.
5. **Propagação de claims à RLS via backend (ADR-008):** quando os dados são servidos pelo **FastAPI** (como a `usuarios` do C04), a RLS só se aplica se o backend **propagar os claims do JWT verificado para a sessão do Postgres** (ex.: `SET LOCAL request.jwt.claims` dentro da transação, conforme ADR-008/ADR-007). Sem isso, a RLS é contornada. **Finalize essa propagação nesta sessão.**
6. **Versionamento de RLS (DAT §2):** toda política RLS é arquivo `.sql` em `/migrations/rls/` **antes** de ser aplicada; **reaplicada manualmente após qualquer recriação de tabela**. Nunca criar RLS só pelo painel sem versionar.
7. **Fronteira C05↔C06:** `provas` é do C06. A RLS de linha das provas (`provas_select.sql` etc., padrão do DAT §7.2) é **aplicada no C06**, usando os helpers desta sessão (ver DP-3).

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Custom Access Token Hook** (migration: função + grants conforme §1.1.3), injetando `setor` + `user_id` (+ `administrador`/perfil conforme DP-1) na posição lida pela RLS. Fonte dos dados conforme DP-2. Versionado e documentado; instruções para configurar o hook no dashboard e no `config.toml` local.
- **`/lib/access-matrix.ts`** (frontend) — a Matriz §7 reconciliada com a DP-1, como **fonte única** consumida pelo middleware **e** pela UI; com um helper `can(perfil, recurso)` / `authorize(...)` reutilizável.
- **Camada superior — Middleware** (estender o `middleware.ts` do C03): após o refresh de sessão, **decisão de acesso por perfil** para **todas as linhas de página da Matriz** (inclusive as páginas ainda placeholder de provas/relatórios/config). Acesso não autorizado → **redirect para a home do perfil + toast** (DP-4), reusando o sistema de toasts do C04.
- **UI consumindo a Matriz:** **filtrar os itens da sidebar do C04 por perfil** (item deixado para cá); estabelecer o **padrão de gating de ações** (`can(...)`) que C06/C08 reutilizarão para botões como Criar Prova/Cancelar/Reiniciar.
- **Camada inferior — RLS:**
  - **`usuarios`:** substituir a RLS **provisória** do C04 pela **política por perfil definitiva** (DP-6), versionada em `/migrations/rls/`, incluindo o grant de leitura ao `supabase_auth_admin` (§1.1.3).
  - **Funções/helpers SQL reutilizáveis** de RLS (ex.: leitura padronizada de `auth.jwt() ->> 'setor'`, helpers como `is_3studio()` / `current_app_user_id()`), para o C06 compor a RLS de `provas` de forma consistente.
- **Propagação de claims (ADR-008):** finalizar a propagação dos claims do JWT verificado para a sessão do Postgres no backend, de modo que a RLS se aplique às consultas servidas via FastAPI; **generalizar o guard de admin do C04** em uma dependência de autorização reutilizável alinhada à Matriz.
- **Harness de testes de equivalência** middleware↔RLS (§1.1 risco documentado): para cada célula testável **agora** (páginas via middleware; `usuarios` via RLS), assegura que as duas camadas concordam.
- **Documentação** (`docs/rbac.md`): as duas camadas, o hook, a posição dos claims, a propagação (ADR-008), a regra do **PR único** para mudanças futuras na Matriz, e como o C06 pluga a RLS de `provas`.
- **Testes** (§7) e **Protocolo de Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Tabela `provas` e a RLS de linha das provas** (`provas_select.sql` etc.) — **C06** as aplica usando os helpers desta sessão. *(A aceitação “Vendedor vê só as suas / Motorista só as Em Trânsito” a nível de dado é validada de ponta a ponta no C06 — ver DP-3 e §6.)*
- ❌ **Conteúdo das páginas** ainda inexistentes (Dashboard=C16, Relatórios=C17, Configurações=C09, Provas=C06–08, Escanear=C10). Aqui só o **gating** dessas rotas pelo middleware e as entradas na sidebar.
- ❌ Máquina de estados, domínio de provas, dashboard, relatórios — Waves 2+.
- ❌ Camada de animações do C19 (os toasts reutilizam o sistema do C04).

> Vontade de adiantar a RLS de `provas` ou páginas futuras: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Matriz = fonte única.** `access-matrix.ts` e a RLS são **duas representações da mesma política**. Documente e teste a **equivalência**; estabeleça a regra de que **toda alteração futura na Matriz exige PR único cobrindo as duas camadas** (`access-matrix.ts` E migrations de RLS) — risco registrado no backlog.
2. **Hook:** rápido, idempotente, **nunca quebra auth**, preserva claims obrigatórios, injeta os claims **na posição lida pela RLS** (§1.1.2). Grants conforme §1.1.3.
3. **Middleware:** lê claims via **`getClaims()`** (verificação local, sem bater no auth server a cada request); decisão baseada **exclusivamente** no `access-matrix.ts`; não autorizado → redirect + toast.
4. **RLS:** versionada em `/migrations/rls/` **antes** de aplicar; reaplicável após recriação de tabela; **defesa em profundidade** (o middleware bloqueia a página, a RLS bloqueia o dado).
5. **Propagação de claims (ADR-008):** consultas do backend que tocam tabelas com RLS rodam **com os claims do usuário propagados** à sessão do Postgres; jamais servir dado de domínio por um caminho que ignore a RLS.
6. **Mínimo de requisições / escalabilidade:** sem chamadas redundantes ao auth server; o hook não faz trabalho pesado; consultas eficientes.
7. **Estilização** (mudanças de UI — sidebar/toast): **CSS Modules**; nada que quebre a fidelidade do shell do C04.
8. **Stateless** (RNF-018); **sem segredos versionados**; **custo R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada. Não comece a §5 sem as respostas.

**DP-1 — Matriz derivada do modelo do C04 (confirmação).**
Apresente a **Matriz de Acesso resultante** da decisão da DP-1 do C04 (lida de `DECISIONS.md`/`CLAUDE.md §2.1`): se foi **(b)** admin=3Studio, a Matriz §7 vale como está; se foi **(a)** setor+flag, mostre o ajuste (quais células passam a chavear por `administrador` vs `setor`). **Confirme a Matriz antes de codificar.**

**DP-2 — Fonte dos claims do hook e configuração.**
**[Recomendado]** o hook lê o perfil da **tabela `usuarios`** (fonte autoritativa de domínio), com o grant de leitura ao `supabase_auth_admin`. Alternativa: ler do **`app_metadata`** já presente no evento (evita o read, mas exige o `app_metadata` sempre sincronizado pelo C04). Confirmar a fonte, a **posição dos claims** (nível superior, p/ casar com a RLS do DAT) e **quem configura o hook no dashboard** (+ `config.toml` local).

**DP-3 — Fronteira C05↔C06 (a mais importante).**
**[Recomendado]** o C05 entrega: hook + claims, `access-matrix.ts`, middleware para **todas** as páginas da Matriz (inclusive placeholders), **RLS definitiva de `usuarios`**, **helpers SQL reutilizáveis**, propagação de claims (ADR-008) e o **harness de equivalência** para tudo testável agora; o **C06** cria `provas` e aplica a **RLS de linha das provas** com esses helpers, estendendo o harness às células de provas. A aceitação de escopo de dados de provas é validada **no C06**. Confirmar essa divisão. *(Alternativa: pré-autorar os `.sql` de `provas` agora, prontos mas não aplicados — confirmar se deseja.)*

**DP-4 — Comportamento do middleware e “home por perfil”.**
**[Recomendado]** acesso não autorizado → redirect para a **home do perfil** (sugestão: **Dashboard**, que todos acessam) + **toast** (mecanismo: flash via cookie/param que a página de destino lê, já que o middleware não renderiza toast). Confirmar a home de cada perfil e o padrão de toast.

**DP-5 — UI: filtro da sidebar e gating de ações.**
**[Recomendado]** filtrar os itens da sidebar do C04 por perfil via `access-matrix.ts` (item deixado para cá) e definir o padrão `can(perfil, recurso)` para gating de botões que C06/C08 reutilizarão. Confirmar o escopo de UI desta sessão (sidebar agora; botões de páginas futuras só o padrão).

**DP-6 — RLS definitiva de `usuarios`.**
**[Recomendado]** definir a política por perfil de `usuarios` (substituindo a provisória do C04): 3Studio gerencia todos; demais perfis sem leitura direta do cadastro (dados servidos via backend com propagação de claims); incluir o grant de leitura ao `supabase_auth_admin` (hook). Confirmar a intenção da política.

**DP-7 — Harness de equivalência e a regra do PR único.**
**[Recomendado]** harness que, para cada célula (perfil × página/recurso) testável agora, assegura que **middleware e RLS concordam** (●/◐ ⇒ acessa; ○ ⇒ 0 registros / bloqueado); e documentar o **processo** de PR único para futuras mudanças na Matriz. Confirmar a localização/forma do harness.

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; use nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Backend / Banco — `apps/api/`
- **Migration do hook** (`versions/00xx_custom_access_token_hook.py`): cria `public.custom_access_token_hook` + grants (§1.1.3); `downgrade` remove. Documentar a config no dashboard e no `config.toml` local.
- **Migration/RLS de `usuarios`** (`migrations/rls/usuarios_*.sql` + ajuste na migration se necessário): política por perfil definitiva (DP-6) + grant de leitura ao `supabase_auth_admin`.
- **Helpers SQL de RLS** (`/migrations/rls/_helpers.sql` ou equivalente): funções reutilizáveis (`is_3studio()`, `current_app_user_id()`, leitura padronizada de `setor`) para o C06 compor a RLS de `provas`.
- **Propagação de claims (ADR-008):** finalizar no `infrastructure/database.py` (ou dependência de request) a propagação dos claims do JWT verificado para a sessão do Postgres; **dependência de autorização reutilizável** (generalização do guard de admin do C04) alinhada à Matriz.

### 5.2 Frontend — `apps/web/`
- **`src/lib/access-matrix.ts`** — a Matriz (DP-1) como fonte única + `can(perfil, recurso)`.
- **`middleware.ts`** (estendido) — após `updateSession()`, lê claims via `getClaims()` e decide acesso pela Matriz; não autorizado → redirect (DP-4) + toast.
- **Sidebar** — filtrar itens por perfil (DP-5), reusando o componente do C04.
- **Toast de acesso negado** — reusar o sistema do C04 (DP-4).

### 5.3 Documentação — `docs/`
- `docs/rbac.md`: as duas camadas, o hook (função + grants + config), posição dos claims, propagação ADR-008, **regra do PR único**, e o plano de como o C06 pluga a RLS de `provas`. Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Cada perfil acessa apenas as páginas ● ou ◐** da Matriz (middleware); **acesso direto por URL a página não autorizada é redirecionado com toast**.
2. ✅ **Hook** injeta `setor` + `user_id` (+ perfil conforme DP-1) no JWT, na posição lida pela RLS; auth continua funcionando (login e refresh).
3. ✅ **RLS de `usuarios` por perfil** ativa e versionada; **query SQL direta fora do escopo retorna 0 registros**; o `supabase_auth_admin` consegue ler `usuarios` para o hook.
4. ✅ **Propagação de claims (ADR-008)** funcionando: consultas servidas pelo backend respeitam a RLS (dado fora do escopo não vaza por esse caminho).
5. ✅ **Sidebar filtrada por perfil**; padrão `can(...)` disponível para gating de ações.
6. ✅ **Harness de equivalência** cobre **100% das células testáveis agora** (páginas via middleware; `usuarios` via RLS) — para cada ●/◐ o perfil acessa; para cada ○ recebe 0 registros/bloqueio. *(As células de `provas` — Vendedor/Motorista — são cobertas no **C06**, conforme DP-3; isto deve estar explicitamente documentado.)*
7. ✅ **Regra do PR único** para mudanças futuras na Matriz documentada.
8. ✅ **Mínimo de requisições** (sem bater no auth server por request — `getClaims()` local); **stateless**; **sem segredos versionados**; **R$ 0**.
9. ✅ `ruff`, `mypy (strict)`, `pytest`, `pnpm lint`/`build` **verdes**; migrations `upgrade`/`downgrade` aplicam em ambiente limpo; RLS reaplicável a partir de `/migrations/rls/`.

---

## 7. Testes desta camada

**Banco / RLS / hook**
- Hook: para cada perfil, o JWT emitido contém os claims corretos na posição certa; claims obrigatórios preservados; usuário inexistente/sem perfil não quebra a emissão.
- RLS de `usuarios`: 3Studio lê todos; perfil não autorizado → 0 registros em query direta; `supabase_auth_admin` lê o necessário.
- Propagação (ADR-008): consulta do backend com claims propagados respeita a RLS; sem propagação, a proteção não é contornável por engano (teste negativo).

**Middleware / equivalência**
- Para cada (perfil × página) da Matriz: middleware permite ●/◐ e redireciona ○ (com toast).
- **Equivalência:** o harness assegura que toda página bloqueada pelo middleware também tem dado bloqueado pela RLS (nas tabelas existentes agora).
- Mintar JWTs de teste **com claims customizados** por perfil; rodar **offline** (Postgres local; sem auth server real).

**UI**
- Sidebar mostra apenas os itens permitidos por perfil; `can(...)` retorna o esperado por célula.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md` + `DECISIONS.md` (decisão da DP-1 do C04) e confirme o estado do C04.
2. **Apresente em bloco os Pontos de Decisão (§4), incluindo a Matriz derivada (DP-1), e aguarde as respostas.**
3. Hook (migration + grants) + configuração; teste de emissão de claims por perfil.
4. RLS definitiva de `usuarios` + helpers SQL + grant ao `supabase_auth_admin`; testes de RLS.
5. Propagação de claims (ADR-008) no backend + dependência de autorização reutilizável; testes (incl. negativo).
6. `access-matrix.ts` + middleware estendido (decisão por perfil + redirect/toast); testes por célula.
7. Filtro da sidebar + padrão `can(...)`.
8. Harness de equivalência; cobertura das células testáveis agora.
9. `docs/rbac.md`.
10. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
11. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`, descreva o que o W1-C05 entregou (hook de claims; `access-matrix.ts`; middleware de RBAC; RLS definitiva de `usuarios`; helpers SQL; propagação de claims ADR-008; harness de equivalência; sidebar filtrada).
2. **`DECISIONS.md`** — novos ADRs: (a) **Custom Access Token Hook** + posição dos claims + grants; (b) **RBAC em duas camadas** (middleware espelha a RLS) e o **padrão de equivalência / regra do PR único**; (c) **propagação de claims à RLS** (finaliza/relaciona **ADR-008**); (d) **RLS definitiva de `usuarios`** (substitui a provisória do C04); (e) **fronteira C05↔C06** (RLS de `provas` aplicada no C06 com os helpers desta sessão). Ajuste status para *Aceita* onde aplicável.
3. **`SESSION_LOG.md`** — nova entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão + Matriz confirmada)**, testes/cobertura (citar a cobertura de células da Matriz), **pendências** (explicitar que a RLS de `provas` e suas células ficam para o C06) e **próximo passo** = **W2-C06 · Cadastro de Prova com Seleção de Rota + Etiqueta**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** (configurar/testar o hook localmente; rodar o harness de equivalência); registre a **localização do `access-matrix.ts`**, a **regra do PR único**, o padrão **`getClaims()`** e os **helpers de RLS** que o C06 vai usar. Enxuto e verdadeiro.
5. **`README.md`** — atualize setup (configuração do hook no dashboard; política do `supabase_auth_admin`) e o roadmap: **Wave 1 concluída** (autenticação + RBAC). 
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **tentativa de acesso não autorizado por perfil** e **equivalência**), **RLS versionada em `/migrations/rls/`**, migrations `upgrade`/`downgrade`, sem erro de console/log crítico, docs do módulo, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w1-c05): ...`, `chore(w1-c05): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. matriz de cobertura das células e prova de que a RLS bloqueia query direta), decisões registradas, pendências (RLS de `provas` → C06) e o **comando exato** para iniciar a próxima sessão (**W2-C06**).

---

### Lembrete final
Este é o componente de **segurança** do sistema e o que **fecha a Wave 1**. As duas camadas existem justamente para que **uma falha não vire brecha**: o middleware bloqueia a página, a RLS bloqueia o dado, e a **propagação de claims** garante que o caminho via backend não escape da RLS. O maior risco é a **divergência entre `access-matrix.ts` e a RLS** — trate a Matriz como fonte única, com equivalência testada e a regra do PR único. Deixe os **helpers de RLS** prontos para o C06 plugar `provas` sem retrabalho. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
