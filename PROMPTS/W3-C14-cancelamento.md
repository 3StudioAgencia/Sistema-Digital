# Prompt de Execução — W3-C14 · Cancelamento de Prova Digital

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–2 auditadas (GO)** e os **C08 e C11 mergeados** (e idealmente C10/C12/C13 da Wave 3). Este componente adiciona a **ação administrativa de cancelar** uma prova. Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (robustez, escalabilidade, mínimo de requisições, observabilidade, animações leves), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–2 + C11 entregues):**
- C04: **app shell**; **modal reutilizável** (reuse para a confirmação); **toasts**; **fundação de motion**.
- C05: `access-matrix.ts` + middleware + `useAuthorization` + **helpers de RLS** + propagação de claims (ADR-008).
- C08: **página de detalhe** — é **aqui** que o botão "Cancelar Prova" vive (o C08 deixou esse slot para o C14 plugar).
- C11: **máquina de estados** — a transição **"estado ativo → Cancelada"** já está **modelada** em `transition_rules`, e o **serviço/endpoint de transição** (atômico, idempotente, valida perfil) grava a **movimentação** no log imutável. **Cancelar passa por aqui — não abra um segundo caminho de status.**

**Insumo:** **não há design do Figma** desta ação/modal — ver DP-5 (seguir o padrão do C04/C08 e confirmar/fornecer o Figma).

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — caminho do cancelamento, assinatura, UX de confirmação, acesso — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, **leia o ADR/schema do C11** (a transição de cancelar e o endpoint/serviço de transição), confirme o estado das Waves 0–2 + C11 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas.
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte. **Nunca invente** um caminho de mudança de status fora do motor do C11.

---

## 1. Objetivo do componente

Entregar a **ação administrativa de cancelar uma prova** — disponível ao **3Studio** em **qualquer estado ativo** (exceto Cancelada e Recebida pela Clicheria), com **motivo obrigatório**, registrando **usuário responsável + data/hora**, **invocando o motor de transição do C11** (transição → "Cancelada"), de forma **terminal e irreversível** (RN-005), preservando o histórico.

Referências: Backlog **C14** · Requisitos **RF-011, RN-005, RNF-006** · §6.6 (transição de cancelamento) · §7 (Cancelar = 3Studio, ação no detalhe) · C11 (motor) · C08 (detalhe).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **Disponibilidade (RF-011, §6.6):** cancelar em **qualquer estado ativo** (≠ Cancelada, ≠ Recebida pela Clicheria). **Motivo obrigatório**; registra **usuário responsável + data/hora**.
2. **Sem assinatura desenhada:** a §6.6 define o cancelamento como **"Ação administrativa: Cancelar Prova. Motivo obrigatório."** — **sem** o passo "Assinar" (ao contrário da reprovação, que tem "Informar motivo → Assinar → Confirmar"). Ver DP-2 (resolução da tensão com RN-003).
3. **Via o motor do C11:** a transição "→ Cancelada" já está **modelada** no C11; o C14 a **invoca** (passando motivo + ator) — atômica, idempotente, gravando a **movimentação** no log imutável (RNF-006). **Não** há segundo caminho de status.
4. **Terminal e irreversível (RN-005):** prova cancelada **não** pode ser reativada; cria-se um **novo registro** se necessário; o **histórico é preservado**. (Cancelada já é terminal no C11 — sem transição de saída.)
5. **Acesso (§7, "Cancelar Prova"):** **exclusivo do 3Studio**; **ação dentro da página de detalhe** (C08).

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Botão "Cancelar Prova"** no **detalhe (C08)** — visível **só ao 3Studio** e **só em estados ativos** (≠ Cancelada, ≠ Recebida pela Clicheria), usando `useAuthorization` + o estado da prova.
- **Modal de confirmação destrutiva** (reusar o modal do C04): **motivo obrigatório**, aviso de **irreversibilidade** (RN-005), confirmar/cancelar; **animação** de entrada/saída (RF-024; `prefers-reduced-motion`).
- **Integração com o motor do C11:** ao confirmar, **invocar a transição de cancelamento** (→ Cancelada) com o **motivo** e o **ator autenticado** (usuário + data/hora gravados na movimentação). Após o sucesso, a UI reflete o estado **Cancelada** (detalhe + timeline atualizados).
- **Acesso em duas camadas:** 3Studio-only no **middleware/UI** **e** garantido pela **validação de perfil do motor/RLS** do C11.
- **Documentação** (`docs/cancelamento.md`): a ação, a integração com o C11, o acesso, e a irreversibilidade. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **A lógica/transição da máquina de estados** — é do **C11**. O C14 **invoca** o motor; não cria caminho de status próprio.
- ❌ **Reinício de ciclo (reprovação)** — Componente **15**.
- ❌ **Criar nova prova** após o cancelamento (RN-005 menciona "criar novo registro", mas isso é o fluxo de criação do C06 — fora daqui).
- ❌ **Assinatura desenhada** (C12) — ver DP-2 (cancelar é administrativo, sem assinatura).
- ❌ Dashboard, relatórios (Waves 4–5).

> Vontade de adiantar reinício de ciclo, criação de nova prova, ou criar um caminho de status fora do C11: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Cancelar passa pelo motor do C11 (integridade):** **uma única fonte** de mudança de status; o C14 **invoca** a transição de cancelamento do C11 (atômica, idempotente, validação de perfil, gravação da movimentação). **Proibido** alterar `prova.status` por fora do motor.
2. **Motivo obrigatório:** validado no **front e no back**; sem motivo → bloqueado.
3. **Irreversibilidade (RN-005):** Cancelada é **terminal** (já no C11); o C14 não oferece reativação; o **histórico** permanece intacto.
4. **Acesso 3Studio em duas camadas:** middleware/UI **e** validação de perfil do motor/RLS do C11 (perfil não-3Studio → bloqueado em ambas).
5. **Estilização:** **CSS Modules**; modal e botão no padrão do C04/C08; **animação** do modal (RF-024) com **`prefers-reduced-motion`**.
6. **Robustez:** falha na submissão **não** deixa estado inconsistente (o motor do C11 é atômico); feedback claro (toast) + possibilidade de tentar de novo; **error boundary**.
7. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada.

### Bloco A — O caminho do cancelamento

**DP-1 — Cancelar via o motor do C11 (integridade da máquina de estados).**
**[Recomendado]** o C14 **invoca o serviço/endpoint de transição do C11** (a transição "estado ativo → Cancelada" já modelada), passando **motivo + ator** — preservando a **fonte única** de transição, gravando a **movimentação** no log imutável (RNF-006), atômica/idempotente. **Não** introduzir um segundo caminho que altere `prova.status` diretamente. *(O backlog lista a dependência mínima 06+05 porque o C14 poderia subir antes do C11; como no nosso ordenamento o C11 já existe, use-o.)* Confirmar.

**DP-2 — Assinatura no cancelamento?**
RN-003 ("toda movimentação exige assinatura") **vs.** §6.6/RF-011 (cancelar = "Ação administrativa: Cancelar Prova. Motivo obrigatório." — **sem** "Assinar", ao contrário da reprovação). **[Recomendado]** o cancelamento **NÃO exige assinatura desenhada** — é ação administrativa com **motivo + ator autenticado + data/hora** (a §6.6 omite a assinatura para cancelar). Confirmar (resolução da tensão com RN-003) — e, se decidirem exigir assinatura, reusar o C12.

### Bloco B — UX e acesso

**DP-3 — UX da ação destrutiva.**
**[Recomendado]** botão **"Cancelar Prova"** no detalhe (C08), **visível só a 3Studio e só em estados ativos**; **modal de confirmação** (reusar o do C04) com **motivo obrigatório** e aviso explícito de **irreversibilidade** (RN-005: cancelada não reativa; criar nova se necessário). Confirmar a UX (texto do aviso, label do confirmar).

**DP-4 — Acesso em duas camadas.**
**[Recomendado]** 3Studio-only no **middleware/UI** (botão escondido + rota protegida) **e** garantido pela **validação de perfil do motor/RLS** do C11 (a transição de cancelar só por 3Studio → 403 caso contrário). Confirmar.

**DP-5 — Layout (sem design).**
**Não recebi o design** do modal/ação. **[Recomendado]** seguir o padrão do C04/C08 (modal de confirmação destrutiva com motivo). **Confirmar/fornecer o Figma** para fidelidade exata.

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- **Botão "Cancelar Prova"** no detalhe (C08) — visível só a 3Studio e só em estados ativos (DP-3/DP-4).
- **Modal de confirmação destrutiva** (reuso do C04): motivo obrigatório, aviso de irreversibilidade, confirmar/cancelar; animação (RF-024; `prefers-reduced-motion`); estados de loading/erro; ao sucesso, refletir "Cancelada" (detalhe + timeline).

### 5.2 Backend — `apps/api/`
- **Integração com o motor do C11** (DP-1): a ação de cancelar chama o **serviço/endpoint de transição** do C11 (→ Cancelada) com motivo + ator (claims propagados; validação de perfil → 403 para não-3Studio); **sem** novo caminho de status. Validação Pydantic (motivo obrigatório); logs estruturados.
- (Nenhuma migration nova esperada — `movimentacoes`/enum/estado Cancelada já existem no C11. Se algo faltar, **pare e pergunte**.)

### 5.3 Documentação — `docs/`
- `docs/cancelamento.md`: a ação, a **integração com o motor do C11**, o acesso 3Studio em duas camadas, e a **irreversibilidade** (RN-005). Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Cancelar sem motivo é bloqueado** (front e back).
2. ✅ Cancelar **invoca o motor do C11** (→ Cancelada), gravando a **movimentação** (ator + data/hora + motivo) no **log imutável** (RNF-006); **nenhum** caminho altera `status` por fora do motor.
3. ✅ **Prova cancelada não pode ser reativada** (RN-005); **Cancelada é terminal**; o **histórico é preservado**.
4. ✅ **Ação indisponível a perfis não-3Studio** (middleware/UI **e** validação de perfil/RLS do C11 → 403); botão visível **só em estados ativos** para 3Studio.
5. ✅ **Modal de confirmação destrutiva** com aviso de irreversibilidade; **animação** (RF-024) com **`prefers-reduced-motion`**; ao sucesso, detalhe + timeline refletem "Cancelada".
6. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**.

---

## 7. Testes desta camada

**Backend**
- Cancelar **via o motor do C11**: estado vai para Cancelada; **movimentação** registrada (ator + data/hora + motivo); **atômico/idempotente** (reenvio não duplica).
- **Sem motivo → bloqueado.**
- **Estados inválidos:** tentar cancelar prova já **Cancelada** ou **Recebida pela Clicheria** → bloqueado (transição não definida no C11 → 422).
- **Acesso:** perfil **não-3Studio** → **403** (validação do motor/RLS), mesmo se chamar o endpoint diretamente.
- **Irreversibilidade:** após cancelar, não há transição de saída (Cancelada terminal).
- Roda **offline** (Postgres local; JWTs de teste por perfil; provas via fixture em vários estados).

**Frontend**
- Botão visível **só a 3Studio** e **só em estados ativos**; modal exige **motivo**; aviso de irreversibilidade; confirmar → estado Cancelada refletido (detalhe + timeline).
- `prefers-reduced-motion` no modal.
- **E2E (Playwright):** 3Studio cancela uma prova ativa (com motivo) → Cancelada; tentar sem motivo → bloqueado; como Vendedor, a ação não está disponível.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md` e o **ADR/schema do C11** (transição de cancelar + endpoint/serviço de transição); confirme Waves 0–2 + C11 e o slot do botão no C08.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. Backend: integração com o motor do C11 (cancelar → Cancelada, motivo + ator, 403 para não-3Studio); testes (motor, sem motivo, estados inválidos, acesso, irreversibilidade).
4. Frontend: botão no detalhe (visível só a 3Studio, só em estados ativos) + modal de confirmação destrutiva (motivo, aviso, animação); refletir "Cancelada".
5. `prefers-reduced-motion`; revisão da animação do modal.
6. `docs/cancelamento.md`.
7. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
8. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: ação de cancelamento de prova (3Studio), via o motor do C11, com motivo obrigatório.
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **cancelar via o motor do C11** (DP-1); (b) **cancelamento sem assinatura** (DP-2, resolução da tensão com RN-003); (c) **UX/acesso** (DP-3/DP-4). Status *Aceita* onde aplicável.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes, **pendências** e **próximo passo** = **W3-C15 · Reinício de Ciclo (Reprovação)**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre a **ação de cancelamento** e que ela **passa pelo motor do C11**. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap (C14 concluído).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **acesso não-3Studio bloqueado** em duas camadas, **sem motivo bloqueado**, **irreversibilidade**), sem erro de console/log crítico, docs do módulo, animação do modal com `prefers-reduced-motion`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w3-c14): ...`, `chore(w3-c14): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. cancelamento via o motor do C11 com movimentação registrada, bloqueio sem motivo, irreversibilidade e acesso 3Studio em duas camadas), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W3-C15**).

---

### Lembrete final
Cancelar é simples na superfície, mas guarda um princípio de **integridade**: **toda** mudança de status passa por **um único motor** (o C11) — abrir um atalho que altere `prova.status` por fora aqui significaria ter duas verdades sobre o estado de uma prova, exatamente o que a máquina de estados existe para impedir. Cancelar é **administrativo** (motivo + ator autenticado, **sem** assinatura desenhada — §6.6) e **irreversível** (RN-005): deixe isso explícito ao usuário antes de confirmar. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
