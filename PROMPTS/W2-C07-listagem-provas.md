# Prompt de Execução — W2-C07 · Listagem, Pesquisa e Filtros de Provas

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0 e 1 concluídas e auditadas (GO)** e o **C06 mergeado**, e a **imagem do design anexada** (tela "Provas digitais"). Este é um componente da **Wave 2**. Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (**robustez, escalabilidade, mínimo de requisições, observabilidade**, animações leves), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–1 + C06 entregues):**
- C04: **app shell** (sidebar + shell branco) — a tela de listagem pluga aqui; **componente de tabela** da tela de usuários (o ponto-chave deste componente — ver §0.2 e DP-1); sistema de **toasts** e **fundação de motion**.
- C05: **`access-matrix.ts`** + **middleware** + hook **`useAuthorization(page) → { hasAccess, scope }`** (a UI usa o `scope` para adaptar o que mostra) + **helpers de RLS** + propagação de claims (ADR-008).
- C06: tabela de domínio **`provas`** (com `codigo`, `vendedor_id` FK→`usuarios`, `rota`, `status` default 'criada', `created_at`, **índices** em `status`/`rota`/`vendedor_id`/`created_at`) e a **RLS por perfil de `provas`** (3Studio/Clicheria todas; Vendedor as próprias; Motorista as "Em Trânsito"). **Reuse tudo isso — não recrie.**

**Insumo confirmado:** o design da tela "Provas digitais" no Figma, anexado. **Layout fiel ao design**, e — instrução explícita do dono — **a tabela de provas usa o MESMO componente/estilo da tabela da tela de Gerenciar Usuários (C04)**, para ficar exatamente igual (ver DP-1).

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — reuso de componente, escopo por perfil, colunas/rótulos, paginação, contrato de endpoint — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, confirme o estado das Waves 0–1 + C06 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas.
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte.
4. **Nunca invente** rótulos de status, nomes de rota/coluna/variável, contrato de endpoint ou valores de design. Em dúvida, **pergunte**.

---

## 0.2 Fidelidade ao design e reuso da tabela

**Tela "Provas digitais"** (dentro do shell do C04): título "Provas digitais"; uma **barra de filtros** em duas linhas — linha 1: **"Buscar nome ou requerimento"** (input), **"Cliente"** (input "Nome do cliente"), **"Status"** (dropdown "Todos"), **"Rota"** (dropdown "Todos"); linha 2: **"Vendedor"** (dropdown "Todos"), **"Criada em"** (date "dd/mm/aaaa"), **"Finalizada em"** (date "dd/mm/aaaa"), e o botão **"Limpar"** (preto). Abaixo, a **tabela** (shell-branco-interno) com colunas **Requerimento · Nome · Cliente · Vendedor · Status · Rota · Criada em** e uma coluna de ação com o botão **"Ver"** (amarelo) por linha. A tabela é rolável.

**A tabela deve ser o mesmo componente da tela de usuários (C04)** — mesmo estilo visual, mesmo comportamento de paginação/rolagem, parametrizado para as colunas de provas e a ação "Ver". Se o componente do C04 ainda não for reutilizável, ver **DP-1** (extração em `<DataTable>` genérico, preservando o C04).

Tokens da barra de filtros (date pickers, dropdowns, o botão "Limpar") devem bater com o design e o estilo já estabelecido; **não chute** — se houver link do Figma, extraia via Dev Mode/MCP; senão, confirme.

---

## 1. Objetivo do componente

Entregar a **tela de operação diária**: listar provas com **paginação server-side**, **busca** (nome/requerimento) e **filtros combináveis** (cliente, status, rota, vendedor, período de criação e de finalização), **respeitando o escopo de visibilidade por perfil** (Matriz §7) tanto na **UI** quanto na **RLS**, com performance e mínimo de requisições.

Referências: Backlog **C07** · Requisitos **RF-013, RF-014, US-012, RNF-001, RNF-019, RNF-023** · §7 (Matriz / escopo) · DAT **§7** · C05 (`useAuthorization`, RLS) · C06 (`provas`, índices).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **Acesso à página:** a Listagem é acessível a **todos os perfis** (Matriz §7) — **não** é exclusiva do 3Studio. O que muda por perfil é o **escopo dos dados**: 3Studio/Clicheria veem **todas**; **Vendedor só as suas**; **Motorista só as "Em Trânsito"**. O escopo é **garantido pela RLS** (server-side); a UI usa `useAuthorization(...).scope` para se adaptar.
2. **Busca (RF-013):** por **nome e/ou número de requerimento**, com **debounce ≥ 300 ms** (RNF-023) — **não** dispara requisição a cada tecla.
3. **Filtros (RF-014, US-012):** período, status, vendedor, cliente e rota, **combináveis**.
4. **Paginação (RNF-019):** **server-side**, com **limite máximo por página**; índices já existem (C06).
5. **Performance (RNF-001):** a listagem carrega em **≤ 3 s**.
6. **Status:** os valores de status (e seus rótulos) vêm do `status_prova_enum` (C06 / Requisitos §6). Como o C11 ainda não liga as transições, na prática as provas estarão majoritariamente em "Criada" — mas o **filtro e a coluna de Status devem suportar os 14 estados** (ver DP-4).

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Tela "Provas digitais"** dentro do shell do C04, fiel ao design: barra de filtros (busca + cliente + status + rota + vendedor + criada em + finalizada em + "Limpar") e a **tabela reutilizando o componente do C04** (DP-1), com a ação **"Ver"** por linha (DP-6).
- **UI escopada por perfil:** usar `useAuthorization` do C05 para `{ hasAccess, scope }`; **adaptar a barra de filtros ao escopo** (DP-2). A página é acessível a **todos os perfis** (não gateá-la a 3Studio).
- **Backend — endpoint de listagem:** `GET /api/provas` paginado server-side, com **busca + filtros combináveis**, **claims propagados** (ADR-008) para a **RLS** valer, ordenação padrão por `created_at` desc; consulta **única e eficiente** (sem N+1, sem buscar-e-filtrar-na-aplicação).
- **Coluna `finalizada_em`** (DP-3): se ausente, migration aditiva nullable (populada pelo C11); o filtro "Finalizada em" a utiliza.
- **Rótulos de status** (DP-4): módulo de mapeamento `enum → rótulo` reutilizável, cobrindo os 14 estados.
- **Estado de filtros/paginação** (DP-5): preferencialmente sincronizado na **URL** (refresh-safe, compartilhável); botão **"Limpar"** reseta tudo.
- **Estados de UI robustos:** **loading** (skeleton), **vazio** (sem provas / sem resultados de filtro), **erro** (com recuperação). 
- **Animações** (continuidade C03/C04, sobre os tokens; GPU-only; `prefers-reduced-motion`): entrada da lista (stagger sutil das linhas), transições de filtro/loading.
- **Documentação** (`docs/provas-listagem.md`): contrato do endpoint, filtros, escopo por perfil, paginação. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Tela de detalhe da prova** (Componente **08**) — o "Ver" navega para a rota do detalhe (placeholder até o C08).
- ❌ **Transições/máquina de estados** (C11) — esta tela só **lê e filtra**; não muda status. `finalizada_em` é **populada** pelo C11.
- ❌ **Dashboard, relatórios, atalhos** (Waves 4–5).
- ❌ Edição de provas, ações de fluxo (cancelar/reiniciar — C14/C15) — fora daqui.

> Vontade de adiantar o detalhe, transições ou dashboard: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **RLS no servidor, não na aplicação:** o escopo por perfil é garantido pela **RLS** (C06), com **claims propagados** (ADR-008). **Nunca** busque tudo e filtre na aplicação. A UI **complementa** (esconde filtros sem sentido para o escopo), mas a **fonte da verdade do escopo é a RLS**.
2. **Paginação server-side** com limite por página (RNF-019); **sem N+1**; consulta combinada (filtros + escopo + paginação) **eficiente**, usando os índices do C06; carrega em **≤ 3 s** (RNF-001).
3. **Busca com debounce ≥ 300 ms** (RNF-023); filtros **combináveis** e idempotentes; "Limpar" reseta para o estado default.
4. **Reuso do componente de tabela do C04** (DP-1) — mesmo estilo/paginação; se extrair `<DataTable>`, é **refatoração que preserva comportamento**, com os **testes do C04 re-rodados** (a Wave 1 está auditada — não regrida).
5. **Estilização:** **CSS Modules**; fidelidade ao design; a tabela idêntica à do C04. Animações `transform`/`opacity`; **`prefers-reduced-motion`** obrigatório.
6. **Estados de loading/vazio/erro** tratados (robustez); error boundary na rota (RNF-014/016).
7. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada.

### Bloco A — Dados, filtros e escopo

**DP-1 — Reuso/extração da tabela do C04.**
**[Recomendado]** reutilizar o componente de tabela do C04. Se ele estiver acoplado a usuários, **extrair um `<DataTable>` genérico** (config de colunas + linhas + ação de linha + estilo/paginação idênticos) e fazer **C04 e C07 usarem** — refatoração **sem mudança de comportamento**, com os **testes do C04 re-rodados** para provar que nada regrediu. Confirmar: o componente já é reutilizável ou precisa de extração?

**DP-2 — Acesso e adaptação por perfil.**
**[Recomendado]** a página é acessível a **todos os perfis** (Matriz §7), dados **escopados pela RLS**; a UI usa `useAuthorization(...).scope` e **adapta a barra de filtros** (ex.: esconder/desabilitar o filtro **Vendedor** quando o escopo é "as suas" — Vendedor). Confirmar (vs. mostrar todos os filtros, deixando a RLS torná-los no-op).

**DP-3 — Coluna `finalizada_em`.**
O filtro "Finalizada em" precisa dessa coluna. **[Recomendado]** se não existir do C06, o C07 **adiciona `finalizada_em` (timestamptz, nullable)** via migration aditiva, a ser **populada pelo C11** nas transições terminais; o filtro exclui provas sem valor. Confirmar (ou **adiar** o filtro "Finalizada em" para o C11).

**DP-4 — Rótulos de status.**
A UI precisa de `status_prova_enum → rótulo legível`, cobrindo os **14 estados** (§6), usado pelo **filtro** e pela **coluna Status**. O design usa formas curtas ("Aprovada", "Reprovada", "Na 3Studio", "Na clicheria", "Retirada"). **[Recomendado]** criar um **módulo de rótulos reutilizável** (C08/C13/C16 reusam). Confirmar **qual conjunto de rótulos** (curtos do design vs. nomes completos do §6) e a consistência com o enum.

### Bloco B — Listagem e estado

**DP-5 — Paginação e estado de filtros.**
Paginação **server-side** com limite por página (alinhar o **padrão ao do C04** — DP-1). **[Recomendado]** sincronizar **filtros e paginação na URL** (query params: refresh-safe, compartilhável, back-button); ordenação padrão por **`created_at` desc**. Confirmar o padrão de paginação (cursor/infinite-scroll vs. páginas numeradas, **coerente com o C04**) e o uso de URL state.

**DP-6 — Destino do "Ver" e contrato do endpoint.**
**[Recomendado]** o "Ver" navega para a rota do **detalhe (C08)** — `/provas/{id}` (placeholder até o C08); o backend expõe `GET /api/provas` paginado/filtrável com claims propagados. Confirmar a rota do "Ver" e o **contrato do endpoint** (parâmetros de busca/filtro/paginação, formato da resposta).

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- **`app/(app)/provas/page.tsx`** (ou rota conforme a sidebar) — tela "Provas digitais": barra de filtros (busca com debounce, cliente, status, rota, vendedor, criada em, finalizada em, "Limpar") + a **tabela reutilizada** (DP-1) com a ação "Ver" (DP-6). Acessível a todos os perfis; usa `useAuthorization` (DP-2). URL state (DP-5). Estados de loading/vazio/erro.
- **`<DataTable>` genérico** (se DP-1 = extração) em `src/components/ui/` — usado por C04 e C07.
- **Módulo de rótulos de status** (DP-4), reutilizável.
- Animações sobre os tokens (GPU-only, `prefers-reduced-motion`).

### 5.2 Backend — `apps/api/`
- **`GET /api/provas`** (Ports & Adapters): busca (nome/requerimento) + filtros (cliente, status, rota, vendedor, criada em, finalizada em), **paginação server-side**, ordenação default `created_at` desc, **claims propagados** (RLS ativa), consulta **única e eficiente** (sem N+1). Validação Pydantic dos parâmetros; logs estruturados.
- **Migration aditiva** de `finalizada_em` (DP-3), se aplicável; `downgrade`.
- Endpoint(s) auxiliares para popular os dropdowns de filtro (ex.: lista de vendedores e de status) — reusar o que já existir (C04/C06) quando possível.

### 5.3 Documentação — `docs/`
- `docs/provas-listagem.md`: contrato do endpoint, filtros, escopo por perfil (RLS + UI), paginação. Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Filtros combináveis**; os resultados **respeitam o escopo do perfil** em **UI e RLS** (3Studio/Clicheria todas; Vendedor só as suas; Motorista só as "Em Trânsito"); **query direta fora do escopo → 0 registros**.
2. ✅ A **busca não dispara requisição a cada tecla** (debounce ≥ 300 ms); a busca cobre nome **e** requerimento.
3. ✅ **Listagem carrega em ≤ 3 s** (RNF-001); paginação **server-side** com limite por página; **sem N+1**; usa os índices do C06.
4. ✅ A **tabela é visualmente idêntica à do C04** (mesmo componente/estilo) e fiel ao design; a barra de filtros bate com o design; ação **"Ver"** presente.
5. ✅ **"Limpar"** reseta todos os filtros; (se DP-5 = URL state) filtros sobrevivem a refresh e são compartilháveis.
6. ✅ Estados de **loading/vazio/erro** tratados; **animações** com `prefers-reduced-motion`; responsivo.
7. ✅ Se DP-1 = extração: **testes do C04 re-rodados e verdes** (sem regressão).
8. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**.

---

## 7. Testes desta camada

**Backend**
- Listagem com **escopo por perfil** (claims propagados): cada perfil recebe o conjunto correto; **query direta fora do escopo → 0 registros**.
- Filtros combináveis (status + rota + vendedor + cliente + períodos) retornam o subconjunto correto; busca por nome e por requerimento.
- Paginação server-side (limite por página; navegação entre páginas/cursor); **sem N+1** (verificar nº de queries); ordenação default.
- Roda **offline** (Postgres local; JWTs de teste com claims por perfil; provas inseridas via fixture em vários status, inclusive "Em Trânsito" para o caso Motorista).

**Frontend**
- Render fiel + tabela idêntica à do C04; barra de filtros conforme o design; ação "Ver".
- Debounce comprovado (não dispara a cada tecla); "Limpar" reseta; (URL state, se DP-5) refresh preserva filtros.
- Adaptação por perfil (DP-2): o filtro de Vendedor não aparece para o escopo "as suas".
- Estados de loading/vazio/erro; `prefers-reduced-motion`.
- **E2E (Playwright):** filtrar/buscar/paginar como 3Studio; como Vendedor (vê só as suas); "Ver" navega ao detalhe (placeholder).

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, confirme Waves 0–1 + C06 (RLS de `provas`, índices, `useAuthorization`, tabela do C04).
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. (Se DP-1 = extração) extrair `<DataTable>` genérico e migrar o C04 para ele; **re-rodar os testes do C04** (sem regressão).
4. Backend: `GET /api/provas` (busca + filtros + paginação + claims propagados); migration de `finalizada_em` se aplicável; testes verdes (escopo, filtros, paginação, sem N+1).
5. Frontend: tela "Provas digitais" — barra de filtros (debounce, "Limpar", URL state), tabela reutilizada, ação "Ver", adaptação por perfil; módulo de rótulos de status; estados de loading/vazio/erro.
6. Animações sobre os tokens; responsividade; `prefers-reduced-motion`.
7. `docs/provas-listagem.md`.
8. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
9. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: listagem de provas com busca/filtros/paginação escopada por perfil; (se aplicável) `<DataTable>` genérico; coluna `finalizada_em`; módulo de rótulos de status.
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **reuso/extração da tabela** (`<DataTable>`); (b) **estado de filtros na URL** + padrão de paginação; (c) **rótulos de status** (conjunto adotado); (d) **`finalizada_em`** (origem e quem popula). Status *Aceita* onde aplicável.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes/cobertura (citar os testes de escopo por perfil e sem-N+1), **pendências** e **próximo passo** = **W2-C08 · Visualização de Prova (Detalhe)**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre o **`<DataTable>`** (se criado), o **módulo de rótulos de status** e o **contrato de `GET /api/provas`**. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap (C07 concluído).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **escopo por perfil** e **sem N+1**), migration (se houve) versionada/documentada, sem erro de console/log crítico, docs do módulo, error boundary, animações com `prefers-reduced-motion`, **sem segredos versionados**. *(Se extraiu `<DataTable>`: os testes do C04 seguem verdes.)*
7. **Commits semânticos** (`feat(w2-c07): ...`, `refactor(w2-c07): extrai DataTable`, `chore(w2-c07): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. prova de que o escopo por perfil é respeitado e de que a tabela é idêntica à do C04), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W2-C08**).

---

### Lembrete final
Esta é a **tela de operação diária** da 3Studio — precisa ser **rápida e correta sob escopo**. O erro mais perigoso aqui é **escopo vazando**: nunca confie na UI para esconder dados; o escopo é da **RLS** (claims propagados), e a UI só adapta o que faz sentido mostrar. Reaproveite a **tabela do C04** para ficar idêntica e evitar divergência. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
