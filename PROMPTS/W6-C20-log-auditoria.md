# Prompt de Execução — W6-C20 · Interface de Log de Auditoria (fiel ao design)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–5 auditadas (GO)**, o **C11 mergeado** (e C06/C10/C19), e a **imagem do design anexada** (Auditoria). Este é o **último componente do backlog v1.0**. **Leia a DP-1 antes de tudo: o design expande o escopo além do backlog — é preciso decidir conscientemente.**

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (robustez, **mínimo de requisições**, observabilidade, **segurança**), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–5 entregues):**
- C04: **app shell** (item **"Auditoria"** da sidebar — só 3Studio); **`<DataTable>`**; **fundação de motion**.
- C05: `access-matrix.ts` + middleware + `useAuthorization` + **helpers de RLS** + claims (ADR-008).
- C06: **criação de prova** (evento "Criou Prova" no design — **não** é `movimentacao`).
- C10: **escaneamento** (evento "Escaneou Qr Code" no design — **não** é `movimentacao`).
- C11: **`movimentacoes`** — tabela **imutável** (append-only) que registra **transições, reprovações, reinícios, cancelamentos, travessias de motorista**, com **RLS** (3Studio vê tudo). É o **log de movimentações de provas** (RNF-006).
- C07: **filtros + paginação server-side + URL state** — **reuse** (DP-2). C19: camada de animações — **consuma**.

**Insumo:** o **design do Figma está anexado** — siga-o (§0.2). **Atenção:** o design mostra um log **mais amplo** do que o `movimentacoes` do C11 (todas as ações do sistema + IP + origem + hash de integridade). Isso **expande o backlog C20 e o RNF-006** — ver **DP-1 (bloqueante)**.

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em especial, **não** construa um subsistema de auditoria amplo (capturar todas as ações + IP + origem + hash) **sem decisão explícita** — isso vai muito além de "interface de consulta" e toca vários componentes.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, **leia o schema/RLS de `movimentacoes` (C11)** e os padrões do C07, confirme as Waves 0–5 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas. **DP-1 (escopo/fonte do log) condiciona TODO o resto — é bloqueante.**
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte. **Nunca invente** uma forma de editar o log (ele é imutável) nem um mecanismo de captura/hash sem decisão.

---

## 0.2 Fidelidade ao design

**Tela "Auditoria"** (3Studio-only), conforme o design:
- **Cabeçalho:** título **"Auditoria"** + subtítulo **"Log imutável de todas as ações do sistema"**.
- **Barra de filtros:** presets **Hoje / 7d / 30d / 90d**; **Eventos** (dropdown, "Todos"); **Ator** (dropdown, "Todos"); **Ordem** (dropdown, "Recentes"); **busca** ("Motivo, cliente ou nº requerimento"); **De / Até** (datas); **Linhas** (dropdown, "50" — tamanho de página).
- **Master-detail** (dois painéis):
  - **Lista** (esquerda, rolável): cada item com um **ponto colorido por tipo de evento**, o **nome do evento** ("Mudou status", "Aprovou prova", "Escaneou Qr Code", "Criou Prova", "Reprovou Prova"…), o **ator** e o **horário**.
  - **Detalhe** (direita) do item selecionado: título do evento + "Registrado por {ator}"; campos **Ator**, **Setor**, **Prova**, **Endereço IP**, **Origem** (ex.: "Aplicação Web · Chrome"), **Data e hora**; e um rodapé **"Registro íntegro e imutável"** com um **hash** (ex.: `sha256:538453d75fb3ab5691…`).

**Os dados do design são ilustrativos.** Layout/cores/tipografia seguem o design. **Atenção:** os campos **Endereço IP**, **Origem** e o **hash de integridade**, e os eventos que **não** são movimentações (Criou Prova, Escaneou Qr Code), **dependem da decisão da DP-1** — não os invente sobre dados que não existem.

---

## 1. Objetivo do componente

Entregar a **interface de Auditoria** (3Studio-only, **read-only**) **fiel ao design** (master-detail, filtros, color-coding, painel de detalhe com metadados e hash de integridade), exibindo o **log imutável** — com o **escopo do log (movimentações × todas as ações do sistema) e os campos IP/origem/hash definidos na DP-1**.

Referências: Backlog **C20** · Requisitos **RNF-006** · §7 (Log de Auditoria = 3Studio) · C11 (`movimentacoes`) · C07 (filtros/paginação) · C04 (`<DataTable>`).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **O que o backlog/RNF-006 garantem (base):** um **log imutável de todas as movimentações de provas** — reprovações, reinícios, cancelamentos, travessias de motorista — **gerado pelo C11** e acessível **só ao 3Studio**. O backlog disse que o C20 é **"apenas a interface de consulta"**.
2. **O que o design ACRESCENTA (além do RNF-006 — ver DP-1):**
   - **Eventos que não são movimentações:** "Criou Prova" (C06), "Escaneou Qr Code" (C10) — exigem **logar ações que hoje não viram `movimentacao`**.
   - **Endereço IP** e **Origem** (Aplicação Web · navegador) — exigem **capturar IP/user-agent** por ação (middleware).
   - **Hash de integridade** por registro ("Registro íntegro e imutável", sha256) — exige um **mecanismo de tamper-evidence** (provável hash chain).
3. **Acesso (§7, Matriz):** **exclusivo do 3Studio** (`Log de Auditoria | ● | ○ | ○ | ○`). A **RLS de `movimentacoes`** já deixa o 3Studio ver tudo.
4. **Read-only / imutável:** o log **não** se edita; o C20 é uma **janela**, não uma porta.

---

## 2. Escopo e NÃO-escopo (depende da DP-1)

### Faz parte desta sessão — **camada de UI (independe da DP-1)**
- **Tela de Auditoria** (item "Auditoria" do shell — só 3Studio) **read-only**, **fiel ao design** (§0.2): cabeçalho, barra de filtros, **master-detail** (lista com color-coding + painel de detalhe), reusando padrões do C07 (filtros/paginação/URL state) e o C04/C19.
- **Filtros/busca/paginação** (DP-2): período (presets + De/Até), **Eventos**, **Ator**, **Ordem**, busca, **Linhas** (page size); **server-side**.
- **Acesso 3Studio em duas camadas** (DP-4).
- **Documentação** (`docs/auditoria.md`), **Testes** (§7), **Encerramento** (§9).

### Faz parte **SE** a DP-1 escolher expandir o log (backend de auditoria)
- **Captura de eventos não-movimentação** (Criou Prova, Escaneou Qr Code, …) e/ou **metadados IP/origem** e/ou **hash de integridade** — conforme a opção escolhida (ver DP-1). Isso é **backend** e **toca múltiplos componentes** (C06/C10/C11 + middleware) — **só** com decisão explícita.

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Construir o subsistema de auditoria amplo (IP/origem/hash/eventos extras) sem a decisão da DP-1.**
- ❌ **Gerar/alterar/editar o log** — é **read-only**; a imutabilidade é estrutural. **Nenhuma** mutação na UI.
- ❌ **Alterar a máquina de estados / a RLS do C11** por conta (salvo o que a DP-1 explicitamente decidir; em dúvida, **pare e pergunte**).
- ❌ **A timeline por-prova** (C13) — o log é global; não a recrie.

> Vontade de "já fazer o hash e o IP" sem confirmar: **pare**. Isso é exatamente a DP-1.

---

## 3. Restrições técnicas (obrigatórias)

1. **Estritamente read-only:** a UI **não** oferece **nenhuma** mutação. A imutabilidade é estrutural (append-only); o C20 **não** a enfraquece — e, **se** a DP-1 incluir o **hash de integridade**, ele **reforça** a tamper-evidence.
2. **Acesso 3Studio em duas camadas:** middleware/UI (item "Auditoria" escondido para não-3Studio) **e** endpoint/RLS → **403** caso contrário. Reuse a RLS de `movimentacoes` (3Studio vê tudo).
3. **Paginação server-side / mínimo de requisições:** o log pode ser **grande** — pagine no servidor (a opção "Linhas" controla o page size); filtros no servidor; **sem N+1** (join eficiente com `provas`).
4. **Reuso:** `<DataTable>`/listas (C04) e os padrões de filtro/URL state/paginação (C07); rótulos de status (C07); animações via C19 (`prefers-reduced-motion`).
5. **Honestidade de dados:** **não** exiba campos (IP, origem, hash, eventos extras) que a DP-1 **não** habilitou — sem placeholders falsos. Se a DP-1 adiar algo, a UI **não** mostra esse campo (ou mostra "—" só se fizer sentido e for combinado).
6. **(Se DP-1 = expandir)**: a captura de IP/origem é no **middleware** (não confiar em header forjável sem cuidado); o **hash** é determinístico e, se for chain, encadeia o registro anterior; a expansão **não** altera o comportamento dos componentes que passam a logar (logar é efeito colateral, não muda a regra).
7. **Estilização:** **CSS Modules**; fiel ao design (master-detail, color-coding); responsivo; **stateless**; **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada. **DP-1 é BLOQUEANTE e condiciona o restante.**

### Bloco A — Escopo e fonte do log (decisão central)

**DP-1 — O que o log captura, e o C20 constrói essa captura ou só exibe o que existe? (BLOQUEANTE)**
O backlog disse que o log é o **`movimentacoes`** (C11) e o C20 é **só a UI**. O **design mostra mais**: eventos não-movimentação (**Criou Prova**, **Escaneou Qr Code**), **Endereço IP**, **Origem**, e **hash de integridade** — isso **expande o RNF-006** e exige **backend** que toca C06/C10/C11 + middleware. Opções:
- **(A) UI agora sobre o `movimentacoes` existente; expansão depois.** Construir o master-detail **fiel ao design**, backed pelo `movimentacoes`; exibir os campos **que existem** (ator, ação, prova, motivo, ciclo, data/hora). **IP, origem, hash e eventos extras ficam como esforço seguinte** (backend de auditoria), explicitamente registrados como pendência. *(Menor risco; honra o backlog; entrega a UI já.)*
- **(B) Subsistema de auditoria completo agora.** Criar uma camada de **audit log** que captura **todas as ações** (incl. criação, escaneamento) com **IP/origem** (middleware) e **hash** (tamper-evidence/chain), e a UI sobre ela. *(Escopo grande; toca vários componentes; precisa de design próprio; provavelmente uma sessão/wave à parte.)*
- **(C) Meio-termo focado [Recomendado se você quer o design agora].** Criar uma tabela **`audit_log`** que **una as movimentações (do C11) + os eventos-chave** (criação C06, escaneamento C10) com **IP/origem** (middleware) e **hash de integridade**; a UI lê dela. **Adiar** eventos periféricos (login, mudança de config) se não essenciais. *(Entrega a visão do design com escopo limitado, mas ainda é backend que toca C06/C10/C11.)*

**[Recomendado]** decidir conscientemente entre **(A)** (UI já, expansão depois — mais alinhado ao "C20 = interface") e **(C)** (visão do design com escopo focado). Em qualquer caso, **registre a decisão e o que fica adiado**. *(Nota: a dependência do C20 deixa de ser só o C11 nas opções B/C.)*

### Bloco B — UI, filtros, eventos

**DP-2 — Filtros, ordenação, paginação (do design).**
**[Recomendado]** período (presets Hoje/7d/30d/90d + De/Até), **Eventos** (tipo), **Ator**, **Ordem** (recentes/antigos), **busca** ("Motivo, cliente ou nº requerimento" — confirmar o que busca), **Linhas** (page size) — **server-side**, reusando o C07 (URL state). Confirmar o conjunto e o default (Hoje, Recentes, 50).

**DP-3 — Tipos de evento + color-coding.**
O design mostra eventos com **pontos coloridos** ("Mudou status"=amarelo, "Aprovou prova"=preto, "Escaneou Qr Code"=laranja…). **[Recomendado]** definir o **conjunto de tipos de evento** (derivado da DP-1: só movimentações, ou movimentações + criação/escaneamento) e o **mapa de cores**. Confirmar os tipos e as cores.

**DP-4 — Read-only, imutabilidade e (se aplicável) hash.**
**[Recomendado]** UI **estritamente read-only**; a imutabilidade é estrutural; **se** a DP-1 incluir o **hash**, exibir "Registro íntegro e imutável" + o hash, e (idealmente) permitir **verificar a integridade** (recomputar/conferir o chain) — **sem** expor como alterar. Confirmar.

**DP-5 — Acesso e layout (master-detail).**
**[Recomendado]** 3Studio em **duas camadas** (middleware/UI + endpoint/RLS → 403); **master-detail** fiel ao design (lista rolável + painel de detalhe), responsivo (no mobile, lista → detalhe em navegação). Confirmar tokens via Figma (se houver link) e o comportamento mobile.

---

## 5. Entregáveis detalhados

> A **fatia desta sessão depende da DP-1**. Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/` (sempre)
- **Tela de Auditoria** (`app/(app)/auditoria/page.tsx` ou conforme a sidebar) **read-only**, **fiel ao design**: cabeçalho + filtros (DP-2) + **master-detail** (lista com color-coding por tipo — DP-3 — e painel de detalhe com os campos disponíveis + "Registro íntegro e imutável"/hash **se** habilitado); estados de loading/erro/vazio; responsivo; animações via C19.

### 5.2 Backend — `apps/api/`
- **Endpoint de consulta** (Ports & Adapters): lê o log (movimentacoes — opção A — ou a `audit_log` — opções B/C), join eficiente com `provas`, **sob RLS**, com filtros + paginação server-side; **3Studio-only**; **read-only**.
- **(Se DP-1 = B/C):** a **tabela `audit_log`** + a **captura de eventos** (movimentações + criação/escaneamento) + **IP/origem** (middleware) + **hash de integridade** (e verificação) — **migration aditiva** + `downgrade`; **RLS**; sem alterar a regra dos componentes que passam a logar.

### 5.3 Documentação — `docs/`
- `docs/auditoria.md`: a **fonte e o escopo do log** (conforme a DP-1), a natureza **read-only/imutável**, os **tipos de evento + cores**, os **filtros**, o **acesso 3Studio**, e (se aplicável) o **mecanismo de hash/integridade** e o que ficou **adiado**. Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ A tela está **fiel ao design** (cabeçalho + subtítulo; filtros; **master-detail** com color-coding e painel de detalhe; rodapé de integridade conforme a DP-1).
2. ✅ **Acesso restrito ao 3Studio** (middleware/UI **e** endpoint/RLS → 403 para os demais, mesmo chamando direto).
3. ✅ **Reprovações, reinícios de ciclo e cancelamentos** estão **todos visíveis** (RNF-006); em **rotas laminadas, todas as travessias de motorista** aparecem.
4. ✅ A tela é **read-only** — **nenhuma** mutação; a **imutabilidade** é preservada (e, se DP-1 incluir, o **hash** confere a integridade).
5. ✅ **Filtros/busca/ordenação/paginação server-side** funcionam (período/eventos/ator/ordem/linhas); **sem N+1**.
6. ✅ **A UI não exibe campos não habilitados** pela DP-1 (sem placeholders falsos de IP/origem/hash); o que foi **adiado** está **registrado**.
7. ✅ **(Se DP-1 = B/C)** a captura de eventos/IP/origem/hash funciona **sem alterar a regra** dos componentes; migration/RLS aditivas e limpas.
8. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**; **sem regressão** nos componentes tocados (se B/C).

---

## 7. Testes desta camada

**Backend**
- Consulta retorna os registros corretos (incl. reprovação/reinício/cancelamento/travessias de motorista) para fixtures; **filtros e paginação** corretos; **sem N+1**.
- **Acesso:** não-3Studio → **403** (middleware/RLS), mesmo direto; 3Studio vê tudo.
- **Read-only:** não há rota de mutação do log.
- **(Se B/C):** a captura registra os eventos certos (criação, escaneamento, transições) com IP/origem; o **hash** é determinístico e (se chain) **detecta adulteração** (teste que altera um registro e vê o chain quebrar); a captura **não** muda o comportamento dos componentes (seus testes seguem verdes).
- Roda **offline** (Postgres local; JWTs por perfil; fixtures variadas).

**Frontend**
- Render do master-detail (lista com color-coding por tipo; painel de detalhe com os campos disponíveis + integridade se habilitada); filtros/busca/ordenação/paginação (URL state); estados de loading/erro/vazio.
- Item "Auditoria" **ausente** para não-3Studio; rota redireciona (RF-021).
- `prefers-reduced-motion`; responsivo (master-detail no mobile).
- **E2E (Playwright):** como 3Studio, filtrar por evento/ator/período e abrir o detalhe; como não-3Studio, inacessível.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, o **schema/RLS de `movimentacoes` (C11)** e os padrões do C07; confirme Waves 0–5.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde — DP-1 é bloqueante** (define se há backend de auditoria e o que fica adiado).
3. **Backend de consulta** (read-only, RLS 3Studio, filtros + paginação, join eficiente). **(Se B/C):** a `audit_log` + captura (eventos/IP/origem) + hash, com testes (inclusive o teste de adulteração) — **sem** mexer na regra dos componentes.
4. **Frontend:** master-detail fiel ao design (color-coding, painel de detalhe, integridade se habilitada) + filtros (C07).
5. Animações via C19; `prefers-reduced-motion`; responsividade.
6. `docs/auditoria.md`.
7. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
8. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: interface de Auditoria (read-only, 3Studio, master-detail, filtros); **(se B/C)** a camada de captura/IP/origem/hash de integridade.
2. **`DECISIONS.md`** — ADRs: (a) **DP-1 — escopo/fonte do log e o que foi adiado** (a decisão **mais importante** — registre a opção A/B/C e o racional, e que expande/ não o RNF-006); (b) filtros/ordenação (DP-2); (c) tipos de evento + cores (DP-3); (d) read-only/hash (DP-4); (e) acesso/layout (DP-5). Status *Aceita*.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (especialmente a DP-1)**, **pendências adiadas** (se A/C deixou IP/origem/hash/eventos para depois), testes (acesso 3Studio, registros visíveis, travessias de motorista, e — se B/C — o teste de adulteração), e — por ser o **último componente** — registre que o **backlog v1.0 está completo** (com as pendências de auditoria, se houver); **próximo passo** = **auditoria de fechamento da Wave 6** / **revisão final de sistema**.
4. **`CLAUDE.md`** — registre a **tela de Auditoria** (read-only, fonte/escopo do log conforme a DP-1, 3Studio) e, se B/C, a **camada de auditoria/hash**. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap: **Wave 6 e backlog v1.0 concluídos** (anotando pendências de auditoria, se houver).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **acesso não-3Studio bloqueado** em duas camadas, **read-only**, **travessias de motorista**, **sem N+1**, e — se B/C — **adulteração detectada** e **sem regressão**), (se migration) versionada/documentada, sem erro de console/log crítico, docs do módulo, `prefers-reduced-motion`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w6-c20): ...`, e se B/C `feat(w6-c20): audit log + hash`, `chore(w6-c20): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue (UI + o que a DP-1 definiu), **evidência de cada critério (§6)**, a **decisão da DP-1 e as pendências adiadas**, e a **recomendação de próximo passo** (auditoria de fechamento da Wave 6 / revisão final).

---

### Lembrete final
Este é o **último componente** — e o design elevou a aposta: de "janela para as movimentações" para "**log imutável de todas as ações do sistema**", com **IP, origem e hash de integridade**. Isso é mais ambicioso (e mais valioso) que o RNF-006 pedia — mas é **backend que toca vários componentes**, então **não o construa sem a decisão da DP-1**: escolha conscientemente entre entregar a **UI sobre o que existe agora** (e agendar a expansão) ou a **visão do design com escopo focado**. Em qualquer caminho, três coisas são inegociáveis: **só leitura** (o log é memória inviolável, nunca uma porta), **3Studio em duas camadas** (revela tudo sobre tudo), e **honestidade de dados** (não pinte na tela um IP ou um hash que o backend não produz). **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível — esta sessão fecha o backlog v1.0.
