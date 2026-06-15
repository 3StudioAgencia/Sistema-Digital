# Prompt de Execução — W2-C08 · Visualização de Prova (Detalhe)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–1 concluídas e auditadas (GO)** e os **C06 e C07 mergeados**, e a **imagem do design anexada** (tela de detalhe da prova). Este é um componente da **Wave 2**. Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (robustez, escalabilidade, mínimo de requisições, observabilidade, animações leves), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–1 + C06 + C07 entregues):**
- C04: **app shell** (sidebar + shell branco) — a tela de detalhe pluga aqui; **modal reutilizável**; **toasts**; **fundação de motion**.
- C05: **`access-matrix.ts`** + middleware + hook **`useAuthorization(page) → { hasAccess, scope }`** + **helpers de RLS** + propagação de claims (ADR-008).
- C06: tabela **`provas`** (`codigo`, `vendedor_id` FK, `rota`, `status` default 'criada', `created_at`, arte no **R2** privado), **RLS por perfil de `provas`**, e o endpoint de **etiqueta** (`GET /api/provas/{id}/etiqueta.pdf`).
- C07: **listagem** (de onde vem o "Ver"), `GET /api/provas`, e o **módulo de rótulos de status** (`enum → rótulo`). **Reuse tudo isso — não recrie.**

**Insumo confirmado:** o design da tela de detalhe no Figma, anexado. **Layout fiel ao design** (com as reconciliações das DP-3 e DP-7). A tabela/estilo já estabelecidos no C04/C07 valem aqui.

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — campo de domínio, fronteira entre componentes, divergência design×backlog, segurança da arte, escopo — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, confirme o estado das Waves 0–1 + C06 + C07 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas.
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte.
4. **Nunca invente** nomes de campo/rota/variável, rótulos, contrato de endpoint ou valores de design. Em dúvida, **pergunte**.

---

## 0.2 Fidelidade ao design

**Tela de detalhe** (dentro do shell do C04): no topo, botão **"← Voltar"** (retorna à listagem). Um **card de detalhe** (shell-branco-interno): à esquerda a **arte da prova** (imagem); à direita os dados — **"Requerimento: 123456"** (acima), o **nome** em destaque ("Mussarela fatiada"), e um grid: **Cliente · Rota · Criada em · Vendedor · Ciclo Atual · Status**; abaixo, dois botões: **"Visualizar etiqueta"** (amarelo) e **"Baixar etiqueta"** (preto). Em seguida, um card escuro **"Histórico de movimentações"** com **empty state** ("Esta prova ainda não teve movimentações. A timeline visual fica disponível quando a prova for escaneada pela primeira vez.").

Tokens, cores e tipografia seguem o que já está estabelecido (C04/C07); **não chute** — se houver link do Figma, extraia via Dev Mode/MCP; senão, confirme.

---

## 1. Objetivo do componente

Entregar a **página de detalhe da prova**: arte, dados completos, rota e status atual, ações de etiqueta (visualizar/baixar), e a **seção de histórico de movimentações** (no momento, em empty state — a timeline visual rica é do C13). Acesso **restrito por perfil** (Matriz §7), com **escopo garantido pela RLS** e **redirecionamento sem vazar a existência** de provas fora do escopo.

Referências: Backlog **C08** · Requisitos **RNF-001, RNF-014/016** · §7 (Matriz / escopo / redirect) · C05 (`useAuthorization`, RLS) · C06 (`provas`, arte R2, etiqueta) · C07 (rótulos de status, listagem).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **Acesso (Matriz §7):** o detalhe é acessível a **todos os perfis**, com **escopo de dados pela RLS** (3Studio/Clicheria todas; Vendedor as suas; Motorista as "Em Trânsito"). **Vendedor que acessa prova fora do escopo → redirecionamento + toast** (critério do Backlog C08) — **sem revelar se a prova existe**.
2. **Performance:** o detalhe carrega em **≤ 3 s** (RNF-001).
3. **Arte:** está no **R2 privado** (C06) — não há URL pública; a exibição exige **URL pré-assinada** ou proxy pelo backend (DP-5).
4. **Etiqueta:** "Baixar"/"Visualizar" reutilizam o endpoint do C06 (`GET /api/provas/{id}/etiqueta.pdf`) — **não** reimplemente a geração.
5. **Histórico de movimentações:** a tabela `movimentacoes` e as transições são do **C11**; a **timeline visual** é do **C13**. O C08 depende só do **06** → exibe o **empty state** (DP-2).
6. **Status/Rota:** rótulos de status vêm do **módulo do C07** (reuse-o; não crie outro). O display de rota tem uma divergência (DP-7).

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Página de detalhe** dentro do shell do C04, fiel ao design: "Voltar", card com **arte** + metadados (requerimento, nome, cliente, rota, criada em, vendedor, **ciclo atual**, status), botões **Visualizar/Baixar etiqueta**, e a seção **"Histórico de movimentações"** com **empty state** (DP-2).
- **Backend — endpoint de detalhe:** `GET /api/provas/{id}` com **claims propagados** (RLS); retorna a prova **apenas se no escopo**; expõe (ou referencia) a **URL pré-assinada da arte** (DP-5). Carrega em ≤ 3 s.
- **Acesso/escopo:** usar `useAuthorization`; **fora de escopo / inexistente → redirect + toast**, sem vazar existência (DP-6).
- **Campo `ciclo_atual`** (DP-1): se ausente do C06, migration aditiva (int, default 1, NOT NULL), exibido; **incrementado pelo C15**.
- **Ações de etiqueta** (DP-4): "Baixar" → download do PDF do C06; "Visualizar" → preview (modal reutilizando o do C04, ou nova aba).
- **Display de rota** reconciliado (DP-7) e **rótulos de status** reutilizando o módulo do C07.
- **Animações** (continuidade C03/C04/C07, sobre os tokens; GPU-only; `prefers-reduced-motion`): entrada do card, transições.
- **Documentação** (`docs/provas-detalhe.md`): contrato do endpoint, exibição da arte, escopo/redirect, a fronteira com C11/C13. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Tabela `movimentacoes` / máquina de estados / transições** (Componente **11**). O C08 **não** cria nem consulta `movimentacoes` (mostra empty state).
- ❌ **Timeline visual rica** (Componente **13**) — a seção fica estruturada para ela plugar depois.
- ❌ **Ações Cancelar Prova (C14) / Reiniciar Ciclo (C15)** — ver DP-3 (por padrão, o C08 entrega o detalhe **sem** esses botões, conforme o design; C14/C15 os plugam).
- ❌ **Geração de etiqueta** (já é do C06 — só **consumir** o endpoint).
- ❌ Dashboard, relatórios (Waves 4–5).

> Vontade de adiantar movimentações, timeline ou as ações de cancelar/reiniciar: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Escopo pela RLS, não pela UI:** o detalhe é servido pelo backend **com claims propagados** (ADR-008); fora do escopo, a query **não retorna** a prova. A UI então **redireciona + toast**, **sem diferenciar "não existe" de "fora do escopo"** (anti-vazamento de existência).
2. **Arte do R2 privado:** exibir via **URL pré-assinada de curta duração** ou **proxy pelo backend** (DP-5) — **nunca** expor URL pública nem a chave do R2 no cliente.
3. **Reuso, não reimplementação:** etiqueta = endpoint do C06; rótulos de status = módulo do C07; modal/toasts = C04. Não duplique.
4. **Performance ≤ 3 s** (RNF-001); consulta eficiente (sem N+1; a prova + dados relacionados em poucas queries).
5. **Estilização:** **CSS Modules**; fidelidade ao design; consistente com C04/C07. Animações `transform`/`opacity`; **`prefers-reduced-motion`** obrigatório.
6. **Estados de loading/erro** e **error boundary** na rota (RNF-014/016); empty state do histórico tratado.
7. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada.

### Bloco A — Dados e fronteiras

**DP-1 — Campo `ciclo_atual`.**
O detalhe exibe "Ciclo Atual: 1". **[Recomendado]** se não existir do C06, o C08 **adiciona `ciclo_atual` (int, default 1, NOT NULL)** via migration aditiva, exibido aqui e **incrementado pelo C15**. Confirmar (ou se já existe).

**DP-2 — Seção "Histórico de movimentações" (fronteira C08↔C11↔C13).**
**[Recomendado]** o C08 renderiza a seção com o **empty state** (conforme o design), **sem consultar** uma tabela `movimentacoes` inexistente, estruturada para o **C13** plugar a **timeline visual** (e o **C11** gerar os dados). Confirmar essa fronteira.

**DP-3 — Botões Reiniciar Ciclo / Cancelar Prova (divergência backlog × design).**
O Backlog lista esses botões no C08 (visíveis só p/ 3Studio e em estados específicos), mas **o design os omite** e suas ações (**C14/C15**) + os estados (**C11**) ainda não existem. **[Recomendado]** o C08 entrega o detalhe **conforme o design (sem os botões de ação)**, estruturado para que **C14/C15 pluguem** seus botões (visibilidade por Matriz + estado) quando construídos. Confirmar (vs. criar agora os slots desabilitados).

### Bloco B — Etiqueta, arte e acesso

**DP-4 — Ação "Visualizar etiqueta".**
"Baixar" usa o endpoint de PDF do C06. **[Recomendado]** "Visualizar" abre um **preview em modal reutilizando o modal do C04** (ou nova aba). Confirmar a UX.

**DP-5 — Exibição da arte (R2 privado).**
**[Recomendado]** o backend fornece uma **URL pré-assinada de curta duração** para a arte (alternativa: **proxy** pelo backend). **Nunca** URL pública nem chave do R2 no cliente. Confirmar pré-assinada vs. proxy.

**DP-6 — Acesso, redirect e "Voltar".**
**[Recomendado]** detalhe acessível a todos os perfis (Matriz §7), servido com **claims propagados**; **fora do escopo / inexistente → redirect + toast**, **sem vazar existência**. O **"Voltar"** retorna à **listagem (C07)**, preservando os filtros (back do navegador / URL state). Confirmar o comportamento de fora-de-escopo e o destino do "Voltar".

**DP-7 — Display da rota (divergência design).**
O design mostra **"Rota direta"**, que **não é** um dos quatro valores do enum (Matriz/Lam. Matriz/Filial/Lam. Filial). Confirmar: é **placeholder** (deve mostrar o nome real da rota), ou uma **categoria derivada** (direta = Matriz/Filial; laminada = Lam. Matriz/Lam. Filial) exibida no detalhe? **[Recomendado]** mostrar o **nome real da rota** (consistente com C06/C07), opcionalmente com a categoria. Definir onde vivem os **rótulos de rota** (módulo reutilizável, como os de status).

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- **`app/(app)/provas/[id]/page.tsx`** (ou rota conforme o "Ver" do C07) — detalhe: "Voltar" (DP-6), card com **arte** (DP-5) + metadados (incl. **ciclo atual** — DP-1, **rota** — DP-7, **status** via módulo do C07), botões **Visualizar/Baixar etiqueta** (DP-4), seção **"Histórico de movimentações"** com **empty state** (DP-2). Acesso escopado; redirect+toast fora do escopo. Estados de loading/erro.
- **Módulo de rótulos de rota** (DP-7), reutilizável (espelhando o módulo de status do C07).
- Animações sobre os tokens (GPU-only, `prefers-reduced-motion`).

### 5.2 Backend — `apps/api/`
- **`GET /api/provas/{id}`** (Ports & Adapters): retorna a prova **só se no escopo** (claims propagados → RLS); inclui/expõe a **URL pré-assinada da arte** (DP-5); consulta eficiente; logs estruturados.
- **Migration aditiva** de `ciclo_atual` (DP-1), se aplicável; `downgrade`.
- (Reusar o endpoint de etiqueta do C06; não recriar.)

### 5.3 Documentação — `docs/`
- `docs/provas-detalhe.md`: contrato do endpoint de detalhe, exibição da arte (pré-assinada/proxy), escopo/redirect sem vazamento, e a **fronteira com C11/C13** (empty state agora; timeline depois). Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Detalhe carrega em < 3 s** (RNF-001); exibe arte, dados completos, **rota** (DP-7), **ciclo atual**, **status** (rótulo do C07).
2. ✅ **Vendedor que acessa prova fora do seu escopo → redirecionamento + toast** (Backlog C08); o acesso fora do escopo **não revela** se a prova existe (RLS + redirect uniforme).
3. ✅ **Arte exibida com segurança** (URL pré-assinada/proxy; **sem** URL pública nem chave do R2 no cliente).
4. ✅ **"Baixar etiqueta"** baixa o PDF do C06; **"Visualizar etiqueta"** mostra o preview (DP-4).
5. ✅ Seção **"Histórico de movimentações"** com **empty state** conforme o design (DP-2); estruturada para a timeline do C13.
6. ✅ **"Voltar"** retorna à listagem preservando filtros; **fidelidade ao design**; **animações** com `prefers-reduced-motion`; responsivo.
7. ✅ (Se DP-1 = migration) `ciclo_atual` adicionado (default 1) e exibido; migration `upgrade`/`downgrade` limpa.
8. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**.

---

## 7. Testes desta camada

**Backend**
- Detalhe com **escopo por perfil** (claims propagados): perfil no escopo recebe a prova; **fora do escopo → não retorna** (e o front redireciona); 3Studio/Clicheria acessam qualquer prova; Vendedor só as suas; Motorista só as "Em Trânsito".
- **Anti-vazamento:** prova inexistente e prova fora do escopo resultam no **mesmo** comportamento (sem distinção observável).
- Arte: URL pré-assinada gerada corretamente (ou proxy funciona) e expira; sem exposição da chave do R2.
- Eficiência (sem N+1).
- Roda **offline** (Postgres local; R2 mockado; JWTs de teste com claims por perfil; provas via fixture em vários status/escopos).

**Frontend**
- Render fiel; arte, metadados, botões de etiqueta, empty state do histórico; "Voltar" preserva filtros.
- Fora de escopo → redirect + toast; "Visualizar etiqueta" abre o preview; "Baixar" baixa.
- Estados de loading/erro; `prefers-reduced-motion`.
- **E2E (Playwright):** abrir detalhe a partir do "Ver" (C07) como 3Studio; como Vendedor tentar prova de outro vendedor → redirect+toast; baixar/visualizar etiqueta.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, confirme Waves 0–1 + C06 + C07 (RLS de `provas`, arte no R2, endpoint de etiqueta, módulo de rótulos de status, `useAuthorization`).
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. Backend: `GET /api/provas/{id}` (escopo via claims propagados; URL pré-assinada da arte); migration de `ciclo_atual` se aplicável; testes (escopo, anti-vazamento, arte, sem N+1).
4. Frontend: página de detalhe (Voltar, card com arte + metadados, botões de etiqueta, empty state do histórico), redirect+toast fora do escopo; módulo de rótulos de rota.
5. Animações sobre os tokens; responsividade; `prefers-reduced-motion`.
6. `docs/provas-detalhe.md`.
7. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
8. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: página de detalhe da prova (arte, metadados, etiqueta, empty state do histórico); (se aplicável) campo `ciclo_atual`; módulo de rótulos de rota.
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **`ciclo_atual`** (origem/quem incrementa); (b) **fronteira C08↔C11↔C13** (empty state agora; timeline no C13); (c) **divergência dos botões Cancelar/Reiniciar** (resolução); (d) **exibição da arte** (pré-assinada/proxy); (e) **display/rótulos de rota** (resolução da DP-7). Status *Aceita* onde aplicável; **atualize `CLAUDE.md §2.1`** com as reconciliações de design.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes/cobertura (citar escopo por perfil e anti-vazamento), **pendências** e **próximo passo** = **W2-C09 · Tela de Configurações do Sistema**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre o **contrato de `GET /api/provas/{id}`**, a **estratégia de arte (pré-assinada/proxy)** e os **módulos de rótulos** (status do C07 + rota). Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap (C08 concluído).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **escopo por perfil** e **anti-vazamento de existência**), migration (se houve) versionada/documentada, sem erro de console/log crítico, docs do módulo, error boundary, animações com `prefers-reduced-motion`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w2-c08): ...`, `chore(w2-c08): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. prova de que o acesso fora do escopo redireciona sem vazar existência e que a arte não é exposta publicamente), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W2-C09**).

---

### Lembrete final
O detalhe é onde a prova "se abre" — e onde dois riscos silenciosos moram: **vazar a existência** de uma prova fora do escopo (trate inexistente e fora-de-escopo de forma idêntica) e **expor a arte** por URL pública (use pré-assinada/proxy). A seção de histórico nasce em **empty state** de propósito — ela é o lugar onde a **timeline do C13** vai entrar, e os **dados do C11**. Reaproveite etiqueta (C06), rótulos (C07), modal/toasts (C04). **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
