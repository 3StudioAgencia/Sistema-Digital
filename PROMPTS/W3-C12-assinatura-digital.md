# Prompt de Execução — W3-C12 · Assinatura Digital no Fluxo de Escaneamento

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–2 auditadas (GO)** e os **C10 e C11 mergeados**. Este componente **fecha o laço do fluxo de movimentação** — torna *identificar → assinar → confirmar → transição* funcional de ponta a ponta pela primeira vez. Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (**robustez/degradação graciosa**, escalabilidade, mínimo de requisições, observabilidade, animações leves), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–2 + C10 + C11 entregues):**
- C05: `useAuthorization(page) → { hasAccess, scope }` (reuse no frontend) + middleware + helpers de RLS + propagação de claims (ADR-008).
- C10: **identificação** (`POST /api/provas/identificar` / `resolver_prova()`) — a porta de entrada; resolve a prova (QR ou manual), respeitando a RLS e com anti-enumeração.
- C11: **máquina de estados** — `transition_rules` (em `/domain/state_machine/`), o **serviço/endpoint de transição** (atômico, idempotente, valida rota+estado+perfil → 422/403) e a tabela **`movimentacoes`** com a **referência de assinatura** (o C11 deixou esse contrato — leia o ADR/schema do C11; ver DP-1). **Reuse o motor do C11 — não reimplemente transição.**
- C08: detalhe (a seção "Histórico de movimentações" continua em empty state até o C13); **padrão de URL pré-assinada** (reuse se a assinatura for ao R2 — DP-2).

**Insumo:** **não há design do Figma desta tela neste pacote** — ver DP-6 (seguir o padrão visual estabelecido e confirmar/fornecer o Figma).

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — contrato de assinatura, armazenamento, reuso das regras do C11, branches do fluxo, layout — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, **leia o ADR/schema do C11** (o contrato da referência de assinatura e como obter a próxima transição), confirme o estado das Waves 0–2 + C10 + C11 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas.
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte. **Nunca invente** o contrato com o C11, o formato da assinatura, ou um comportamento de fluxo.

---

## 1. Objetivo do componente

Entregar a **assinatura digital como comprovante de cada movimentação** (RN-003) e a **orquestração do fluxo de escaneamento**: após identificar a prova (C10), detectar o ator logado, validar contra a próxima transição (regras do C11) e — se autorizado — apresentar **automaticamente** a tela de assinatura (RF-028), capturar a assinatura desenhada (+ Aprovar/Reprovar/motivo quando aplicável) e **invocar a transição do C11**, refletindo o novo estado. Tudo **mobile-first**, resiliente a falhas e seguro (anti-enumeração).

Referências: Backlog **C12** · Requisitos **RF-006, RF-007, RF-008, RF-028, RN-003, RN-014, RNF-009, RNF-013, RNF-016** · §6 (mecanismo) · C10 (identificar) · C11 (motor) · C05 (`useAuthorization`).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **A assinatura é desenhada (Backlog C12):** captura via **`react-signature-canvas`** (o usuário desenha a assinatura). É o **comprovante** da movimentação (RN-003), reutilizado por **todas** as transições.
2. **Apresentação automática (RF-028):** identificada a prova, **se o usuário logado é o próximo ator habilitado** pela máquina de estados, a tela de assinatura aparece **automaticamente** — no mesmo fluxo do escaneamento, sem navegação extra.
3. **Não-autorizado → mensagem genérica (RF-006, RN-014, US-019.4):** se o usuário **não** é o próximo ator, exibir **mensagem genérica de bloqueio**, **sem revelar quem é** o próximo ator e **sem habilitar** a assinatura.
4. **Aprovar/Reprovar (RF-008, US-003/004):** nos estados "Retirada pelo Vendedor" / "Encaminhada para o Vendedor", o vendedor escolhe **Aprovar** (→ "Aprovada pelo Vendedor") ou **Reprovar** (→ "Reprovada pelo Vendedor", com **motivo obrigatório**).
5. **A transição é do C11:** o C12 **captura a assinatura e invoca** o serviço/endpoint de transição do C11 (atômico, idempotente — RNF-015/017). O C12 **não** reimplementa a transição.
6. **Resiliência (RNF-016):** falha na submissão **preserva os dados localmente** (a assinatura desenhada + a ação) e **oferece retry** — sem perder o traço.
7. **UX (RNF-009/013):** fluxo **identificar → assinar → confirmar em ≤ 3 toques**; tela **responsiva mobile**.

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Tela de assinatura** (no fluxo de escaneamento, pós-identificação), **mobile-first** (DP-6): canvas de assinatura (`react-signature-canvas`); nos estados de posse do vendedor, **Aprovar/Reprovar** + **motivo** (reprovar); botão de **confirmar**; **≤ 3 toques** no caminho feliz.
- **Orquestração do fluxo:** após o identificar do C10, **detectar o ator** + **determinar a próxima transição** (reusando as `transition_rules` do C11 — DP-3); **branch autorizado** (apresenta assinatura automaticamente) / **não-autorizado** (mensagem genérica — anti-enumeração). Reusar **`useAuthorization`** (frontend) e a **validação de perfil do backend** (C11 → 403).
- **Backend — tabela de assinaturas** (DP-1): migration criando `assinaturas`/`signatures` (a imagem da assinatura + `ator`, `created_at`, vínculo com a `movimentacao`); **RLS** versionada; cumprir o **contrato de referência de assinatura do C11**.
- **Submissão da transição:** capturar a assinatura → persistir → **invocar a transição do C11** (passando a referência real); UI reflete o novo estado.
- **Resiliência offline** (RNF-016): preservar a assinatura/ação localmente em falha + **retry**.
- **Animações leves** (sobre os tokens; GPU-only; `prefers-reduced-motion`): apresentação da tela, feedback de sucesso.
- **Documentação** (`docs/assinatura.md`): a tabela de assinaturas + vínculo com `movimentacoes`, a orquestração do fluxo, as branches/anti-enumeração, a resiliência. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Lógica de transição / `transition_rules` / `movimentacoes`** — é do **C11**. O C12 **invoca** o motor e **cria a tabela de assinaturas**; não reimplementa transição.
- ❌ **Timeline visual** (Componente **13**) — o histórico continua em empty state até o C13.
- ❌ **Cancelar (C14) / Reiniciar Ciclo (C15)** — fluxos administrativos próprios (embora também usem assinatura/motor; fora daqui).
- ❌ **Identificação por câmera/manual** (já é do C10 — só **consome** o resultado).
- ❌ Dashboard, relatórios (Waves 4–5).

> Vontade de adiantar timeline, cancelar/reiniciar ou mexer nas regras do C11: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Reuso, não reimplementação:** a transição é do **C11** (atômica/idempotente); o C12 captura a assinatura e **invoca** o motor com a **referência de assinatura** (contrato do C11 — DP-1). A determinação da próxima transição reusa as **`transition_rules` do C11** (DP-3) — **não duplique** a lógica.
2. **Anti-enumeração (RN-014):** não-autorizado → **mensagem genérica**, **sem revelar** o próximo ator; consistente com o C10/C08.
3. **Motivo obrigatório** na reprovação (validado front e back).
4. **Resiliência (RNF-016):** falha de submissão **não perde** a assinatura desenhada nem a ação; **retry** disponível; perda de conexão preserva a operação localmente.
5. **Segurança da assinatura:** se armazenada no **R2** (DP-2), bucket **privado** + **URL pré-assinada** para leitura (padrão do C08); **nunca** URL pública. **RLS** na tabela de assinaturas.
6. **Estilização:** **CSS Modules mobile-first**; padrão visual do C04/C10 (DP-6). Animações `transform`/`opacity`; **`prefers-reduced-motion`** obrigatório; **≤ 3 toques** (RNF-009).
7. **Error boundary** na rota; **stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada.

### Bloco A — A assinatura e a orquestração

**DP-1 — Tabela de assinaturas + contrato com o C11.**
**[Recomendado]** o C12 cria a tabela **`assinaturas`** (a imagem da assinatura + `ator`, `created_at`, vínculo com a `movimentacao`) e **cumpre o contrato de referência de assinatura do C11** (leia o ADR/schema do C11: a coluna em `movimentacoes` é **nullable + vira FK para `assinaturas`** agora, ou é uma **referência genérica**?). Confirmar a forma do vínculo `movimentacao` ↔ `assinatura` (e a ordem de criação na transação: a assinatura é criada antes/junto com a movimentação?).

**DP-2 — Armazenamento da imagem da assinatura.**
A assinatura é uma **imagem** (`react-signature-canvas`, PNG/data URL). **[Recomendado]** armazenar **na tabela `assinaturas`** (imagem pequena, ex.: `bytea`/base64) — simples e transacional; **alternativa:** objeto no **R2** privado (porta do C01) com **URL pré-assinada** para leitura. Confirmar o armazenamento e o formato.

**DP-3 — Determinação da próxima transição (reuso do C11).**
O C12 precisa saber, para a prova identificada + o ator logado, **se ele é o próximo ator e quais ações tem** (incl. Aprovar/Reprovar). **[Recomendado]** reutilizar as **`transition_rules` do C11** via uma **query** (um endpoint do C11 — `GET .../proxima-transicao` — se já existir, ou adicioná-lo aqui **reusando as regras do C11**, sem duplicar a lógica). Confirmar se o C11 já expôs essa query ou se o C12 a adiciona.

### Bloco B — Fluxo, segurança e UX

**DP-4 — As três branches do fluxo.**
**[Recomendado]** após identificar: (a) ator **é** o próximo → **assinatura automática** (RF-028); (b) estados de posse do vendedor → **Aprovar/Reprovar** (Reprovar exige **motivo** — RF-008); (c) ator **não** é o próximo → **mensagem genérica sem revelar quem é** (RN-014). Confirmar o tratamento das três branches e as mensagens.

**DP-5 — Resiliência e UX.**
**[Recomendado]** falha de submissão **preserva a assinatura desenhada + a ação localmente** e oferece **retry** (RNF-016, sem perder o traço); fluxo **≤ 3 toques** (RNF-009); **mobile-first** (RNF-013); animação leve de sucesso. Confirmar.

**DP-6 — Layout da tela (sem design no pacote).**
**Não recebi o design do Figma** desta tela. **[Recomendado]** seguir o padrão visual estabelecido (shell do C04, tokens, mobile-first do C10): canvas de assinatura + (quando aplicável) Aprovar/Reprovar + motivo + confirmar, botões em zona alcançável. **Confirmar/fornecer o Figma** para fidelidade exata.

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- **Tela de assinatura** (no fluxo de escaneamento, pós-identificação) — `react-signature-canvas`; branches autorizado / Aprovar-Reprovar (+motivo) / não-autorizado (DP-4); **≤ 3 toques**; **mobile-first** (DP-6); resiliência (preserva traço + retry — DP-5); reusa `useAuthorization`.
- Orquestração: consome o identificar do C10; obtém a próxima transição (DP-3); submete e invoca a transição do C11; UI reflete o novo estado.
- Animações sobre os tokens (GPU-only, `prefers-reduced-motion`).

### 5.2 Backend — `apps/api/`
- **Migration `assinaturas`** (DP-1/DP-2) + `downgrade`; **RLS** em `migrations/rls/assinaturas_*.sql`.
- **Persistência da assinatura** + **vínculo** com a `movimentacao` (contrato do C11); **invocação** do serviço/endpoint de transição do C11 (referência real de assinatura), **na mesma transação atômica** quando aplicável.
- (Se DP-3 = adicionar) **query de próxima transição** reusando as `transition_rules` do C11. Claims propagados; validação Pydantic; logs estruturados.

### 5.3 Documentação — `docs/`
- `docs/assinatura.md`: a tabela `assinaturas` + vínculo com `movimentacoes`, a orquestração do fluxo (identificar → validar → assinar → confirmar → transição), as branches/anti-enumeração, a resiliência (RNF-016). Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ Identificada a prova, **se o usuário é o próximo ator → a assinatura é apresentada automaticamente** (RF-028).
2. ✅ Se o usuário **não** é o próximo ator → **mensagem genérica sem revelar quem é** (anti-enumeração, RN-014); a assinatura **não** é habilitada.
3. ✅ **Assinatura submetida com sucesso movimenta a prova** conforme a máquina de estados (invocando o motor do C11; transição **atômica/idempotente**).
4. ✅ **Aprovar/Reprovar** nos estados de posse do vendedor; **Reprovar exige motivo** (sem motivo → bloqueado).
5. ✅ **Falha na submissão preserva os dados localmente e oferece retry** (RNF-016) — a assinatura desenhada **não** se perde.
6. ✅ Fluxo **identificar → assinar → confirmar em ≤ 3 toques** (RNF-009); **mobile-first** (RNF-013); animações com `prefers-reduced-motion`.
7. ✅ Tabela `assinaturas` com **RLS**; vínculo correto com `movimentacoes` (contrato do C11); se R2, **sem** URL pública.
8. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**; migration `upgrade`/`downgrade` limpa; RLS reaplicável.

---

## 7. Testes desta camada

**Backend**
- Persistência da assinatura + vínculo com a `movimentacao` (contrato do C11); transição invocada corretamente (estado muda conforme a máquina).
- **Atomicidade:** falha ao gravar assinatura ou movimentação → **nada** é persistido (rollback) — sem assinatura órfã nem transição sem assinatura.
- **Anti-enumeração:** ator não autorizado → bloqueado (403 no motor do C11) + mensagem genérica; sem vazar o próximo ator.
- RLS de `assinaturas` por perfil; (se R2) URL pré-assinada e sem exposição pública.
- Roda **offline** (Postgres local; R2 mockado se aplicável; JWTs de teste por perfil; provas via fixture em estados que demandam cada ator).

**Frontend**
- Branches: autorizado (assinatura automática) / Aprovar-Reprovar (+motivo obrigatório) / não-autorizado (mensagem genérica).
- **Resiliência:** simular falha de submissão → o traço e a ação **persistem** localmente + retry funciona.
- **≤ 3 toques**; mobile-first (canvas utilizável no touch, 360px+); `prefers-reduced-motion`.
- **E2E (Playwright):** ponta a ponta — identificar (C10) → assinar → confirmar → estado avança (C11); reprovar com motivo; ator errado → mensagem genérica.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md` e o **ADR/schema do C11** (contrato da referência de assinatura + como obter a próxima transição); confirme Waves 0–2 + C10 + C11.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. Backend: migration `assinaturas` + RLS; persistência + vínculo com `movimentacoes`; (se DP-3) query de próxima transição reusando o C11; invocação do motor de transição. Testes (atomicidade, anti-enumeração, RLS).
4. Frontend: tela de assinatura (canvas, branches, Aprovar/Reprovar+motivo), orquestração pós-identificação, resiliência (preserva traço + retry), ≤3 toques, mobile-first.
5. Animações sobre os tokens; `prefers-reduced-motion`.
6. `docs/assinatura.md`.
7. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
8. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: assinatura digital no fluxo de escaneamento (canvas); tabela `assinaturas` + RLS; orquestração identificar→assinar→confirmar→transição (fluxo de movimentação completo de ponta a ponta).
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **tabela de assinaturas + contrato com o C11** (DP-1); (b) **armazenamento da imagem** (DP-2); (c) **reuso das regras do C11 para a próxima transição** (DP-3). Status *Aceita* onde aplicável.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes/cobertura (citar atomicidade assinatura↔transição e anti-enumeração), **pendências** (timeline = C13; cancelar/reiniciar = C14/C15), e registre que **o fluxo de movimentação ponta a ponta está operacional**; **próximo passo** = **W3-C13 · Timeline Visual com 4 Rotas e Laminação**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre a **tabela `assinaturas`**, o **vínculo com `movimentacoes`** e o **fluxo de assinatura/transição**. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap (C12 concluído).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **atomicidade assinatura↔transição**, **anti-enumeração**, **RLS de `assinaturas`**, **resiliência/retry**), migration + RLS versionadas/documentadas, sem erro de console/log crítico, docs do módulo, error boundary, animações com `prefers-reduced-motion`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w3-c12): ...`, `chore(w3-c12): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. o fluxo ponta a ponta movimentando a prova, a mensagem genérica para ator errado, e a resiliência que não perde a assinatura), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W3-C13**).

---

### Lembrete final
A assinatura é o **comprovante** de cada movimentação — e o C12 é o que finalmente faz o fluxo **andar de ponta a ponta** (identificar → assinar → confirmar → transição). Três cuidados: **não reimplemente a transição** (ela é do C11 — atômica e idempotente; você captura a assinatura e a invoca, e a assinatura + a movimentação precisam nascer/falhar **juntas**); **anti-enumeração** (ator errado recebe mensagem genérica, sem revelar quem é o próximo); e **resiliência** (uma falha de rede **não pode** apagar a assinatura que o operador acabou de desenhar — preserve e ofereça retry). **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
