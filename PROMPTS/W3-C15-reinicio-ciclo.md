# Prompt de Execução — W3-C15 · Reinício de Ciclo (Reprovação)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–2 auditadas (GO)** e os **C08, C11 e C13 mergeados** (e o restante da Wave 3). Este componente **fecha a Wave 3** — completa o laço da reprovação. Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (robustez, escalabilidade, mínimo de requisições, observabilidade, animações leves), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–2 + Wave 3 até C13/C14 entregues):**
- C04: **app shell**; **modal reutilizável** (reuse na confirmação); **toasts**; **fundação de motion**.
- C05: middleware + `useAuthorization` + helpers de RLS + propagação de claims (ADR-008).
- C06/C08: `provas` com `rota` (imutável) e **`ciclo_atual`** (criado no C08, default 1) — o C15 **incrementa** este campo. O botão "Reiniciar Ciclo" vive no **detalhe (C08)**.
- C11: **máquina de estados** — a transição **"Reprovada pelo Vendedor → Criada (novo ciclo)"** já está **modelada** em `transition_rules`; o **serviço/endpoint de transição** (atômico, idempotente, valida perfil) grava a **movimentação** no log imutável. **Reiniciar passa por aqui — não abra um segundo caminho de status.**
- C13: **timeline** que agrupa por **ciclo** — depende do carimbo de `ciclo` nas movimentações (ver DP-3). **Reuse — não recrie.**

**Insumo:** **não há design do Figma** desta ação/modal — ver DP-5 (seguir o padrão do C04/C08 e confirmar/fornecer o Figma).

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — caminho do reinício, incremento de ciclo, carimbo de ciclo, assinatura/motivo, acesso — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, **leia o ADR/schema do C11** (a transição de reinício, o serviço de transição e se as `movimentacoes` carimbam `ciclo`) e o do **C13** (como ele agrupa por ciclo), confirme o estado das Waves 0–2 + Wave 3 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas.
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte. **Nunca invente** um caminho de status fora do motor do C11 nem a forma de atribuir ciclos.

---

## 1. Objetivo do componente

Entregar a **ação administrativa de reiniciar o ciclo** de uma prova reprovada — disponível ao **3Studio** apenas em **"Reprovada pelo Vendedor"** — retornando o status a **"Criada"**, **preservando a rota original e o histórico integral do ciclo anterior**, **incrementando `ciclo_atual`**, **via o motor de transição do C11** e de forma atômica.

Referências: Backlog **C15** · Requisitos **RF-009, RN-006, RNF-006** · §6.6 (transição de reinício) · §7 (Reiniciar = 3Studio, ação no detalhe) · C11 (motor) · C08 (`ciclo_atual`) · C13 (agrupamento por ciclo).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **Disponibilidade (RF-009, RN-006, US-010, §6.6):** reinício **só** em **"Reprovada pelo Vendedor"**, **exclusivo do 3Studio**. Retorna o status a **"Criada"**, **mantém a rota original** e **preserva integralmente o histórico do ciclo anterior** no log de auditoria.
2. **Sem assinatura e sem motivo:** a §6.6 define o reinício como **"Ação administrativa: Reiniciar Ciclo"** — **sem** "Assinar" (ao contrário da reprovação). US-010 pede **confirmação** — **sem campo de motivo** (diferente de cancelar/reprovar). Ver DP-2.
3. **Via o motor do C11:** a transição "Reprovada pelo Vendedor → Criada" já está **modelada** no C11; o C15 a **invoca** (registrando a movimentação no log imutável — RNF-006). **Não** há segundo caminho de status.
4. **Mesma prova, novo ciclo:** o reinício **não cria uma nova prova** — é o **mesmo registro** (mesmo `codigo`/QR/etiqueta), com **`ciclo_atual` incrementado**; a etiqueta física continua válida.
5. **Acesso (§7, "Reiniciar Ciclo"):** **exclusivo do 3Studio**; **ação dentro da página de detalhe** (C08).

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Botão "Reiniciar Ciclo"** no **detalhe (C08)** — visível **só ao 3Studio** e **só em "Reprovada pelo Vendedor"**, usando `useAuthorization` + o estado da prova.
- **Modal de confirmação** (reusar o do C04): **sem motivo**, explicando que o ciclo recomeça (status volta a "Criada", **mesma rota**, **novo ciclo**, **histórico preservado**); confirmar/cancelar; **animação** (RF-024; `prefers-reduced-motion`).
- **Integração com o motor do C11:** ao confirmar, **invocar a transição** "Reprovada pelo Vendedor → Criada" **e incrementar `ciclo_atual` na mesma transação atômica**. Após o sucesso, a UI reflete "Criada" e a timeline mostra o novo ciclo separado.
- **Carimbo de ciclo nas movimentações** (DP-3): garantir que cada `movimentacao` carregue o **`ciclo`** a que pertence, para o agrupamento do C13.
- **Acesso em duas camadas:** 3Studio-only no **middleware/UI** **e** garantido pela **validação de perfil do motor/RLS** do C11.
- **Documentação** (`docs/reinicio-ciclo.md`): a ação, a integração com o C11, o incremento/carimbo de ciclo, o acesso, e a preservação do histórico. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **A lógica/transição da máquina de estados** — é do **C11**. O C15 **invoca** o motor; não cria caminho de status próprio.
- ❌ **Cancelamento** (Componente **14**) — o reinício é a alternativa ao cancelamento, mas é fluxo distinto.
- ❌ **Reprovação** em si (é do fluxo de assinatura, C11/C12) — o C15 atua **depois** dela (no estado "Reprovada pelo Vendedor").
- ❌ **Criar nova prova com rota diferente** (RF-009 menciona isso como alternativa, mas é cancelar + criar — C14/C06, fora daqui).
- ❌ Dashboard, relatórios (Wave 4+).

> Vontade de adiantar dashboard, criar nova prova, ou criar um caminho de status fora do C11: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Reiniciar passa pelo motor do C11 (integridade):** **uma única fonte** de mudança de status; o C15 **invoca** a transição de reinício do C11 (atômica, idempotente, validação de perfil, gravação da movimentação). **Proibido** alterar `prova.status` por fora do motor.
2. **Incremento atômico de `ciclo_atual`:** o incremento acontece **na mesma transação** da transição — nunca um sem o outro (consistência).
3. **Preservação:** a **rota** é mantida (já imutável); o **histórico do ciclo anterior** permanece intacto (movimentações **não** são apagadas); a prova é o **mesmo registro**.
4. **Carimbo de ciclo (DP-3):** cada `movimentacao` carrega o `ciclo` correto, para o C13 agrupar; as movimentações do ciclo anterior ficam atribuídas ao ciclo antigo, as novas ao novo.
5. **Sem motivo, sem assinatura** (DP-2): apenas **confirmação** (3Studio autenticado).
6. **Acesso 3Studio em duas camadas:** middleware/UI **e** validação de perfil do motor/RLS do C11 (não-3Studio → bloqueado em ambas).
7. **Estilização:** **CSS Modules**; modal e botão no padrão do C04/C08; **animação** do modal (RF-024) com **`prefers-reduced-motion`**.
8. **Robustez:** falha na submissão **não** deixa estado inconsistente (transição + incremento atômicos); feedback claro (toast) + retry; **error boundary**.
9. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada.

### Bloco A — O caminho do reinício e o ciclo

**DP-1 — Reiniciar via o motor do C11 + incremento atômico de `ciclo_atual`.**
**[Recomendado]** o C15 **invoca o serviço/endpoint de transição do C11** ("Reprovada pelo Vendedor → Criada"), e o **incremento de `ciclo_atual`** acontece **na mesma transação atômica** (transição e incremento juntos, ou nenhum) — preservando a **fonte única** de status, gravando a **movimentação** no log imutável (RNF-006). **Não** introduzir um segundo caminho que altere `prova.status`/`ciclo_atual` por fora. Confirmar a integração (o incremento é o efeito especial do reinício).

**DP-2 — Assinatura e motivo no reinício?**
§6.6 reinício = "Ação administrativa: Reiniciar Ciclo" (**sem** "Assinar"); US-010 pede **confirmação** (sem motivo). **[Recomendado]** o reinício **NÃO exige assinatura desenhada nem motivo** — apenas **confirmação** do 3Studio autenticado (usuário + data/hora gravados na movimentação). Confirmar (resolução da tensão com RN-003, igual ao C14) e a ausência de campo de motivo.

**DP-3 — Carimbo de ciclo nas movimentações (interplay C11/C13).**
Para o C13 agrupar por ciclo e o histórico ficar corretamente atribuído, cada `movimentacao` deve carregar o **`ciclo`** a que pertence (carimbado no insert com `prova.ciclo_atual`). **[Recomendado]** garantir que o **serviço de transição do C11 carimbe o `ciclo`** em cada movimentação; o reinício do C15 **incrementa `ciclo_atual`** atomicamente (movimentações do novo ciclo recebem o ciclo incrementado). Confirmar onde vive o carimbo (pode **retroagir** ao serviço de transição do C11, se ainda não o faz) e que as movimentações do ciclo anterior ficam atribuídas corretamente.

### Bloco B — UX e acesso

**DP-4 — UX da confirmação + acesso.**
**[Recomendado]** botão **"Reiniciar Ciclo"** no detalhe (C08), **visível só a 3Studio e só em "Reprovada pelo Vendedor"**; **modal de confirmação** (reusar o do C04), **sem campo de motivo**, explicando que o ciclo recomeça (mesma rota, novo ciclo, histórico preservado). Acesso 3Studio em **duas camadas** (middleware/UI + validação de perfil do motor/RLS do C11 → 403 caso contrário). Confirmar a UX e o acesso.

**DP-5 — Layout (sem design).**
**Não recebi o design** do modal/ação. **[Recomendado]** seguir o padrão do C04/C08 (modal de confirmação, sem motivo). **Confirmar/fornecer o Figma** para fidelidade exata.

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- **Botão "Reiniciar Ciclo"** no detalhe (C08) — visível só a 3Studio e só em "Reprovada pelo Vendedor" (DP-4).
- **Modal de confirmação** (reuso do C04): sem motivo, explicação do reinício, confirmar/cancelar; animação (RF-024; `prefers-reduced-motion`); estados de loading/erro; ao sucesso, refletir "Criada" + timeline com o novo ciclo.

### 5.2 Backend — `apps/api/`
- **Integração com o motor do C11** (DP-1): a ação de reiniciar chama o **serviço/endpoint de transição** do C11 ("Reprovada pelo Vendedor → Criada") **+ incremento de `ciclo_atual` na mesma transação**; claims propagados; validação de perfil → **403** para não-3Studio; **sem** novo caminho de status.
- **Carimbo de `ciclo`** nas movimentações (DP-3) — garantir no serviço de transição (pode retroagir ao C11). Se exigir migration (campo `ciclo` em `movimentacoes`), ela é **aditiva** + `downgrade` + backfill coerente. Logs estruturados.

### 5.3 Documentação — `docs/`
- `docs/reinicio-ciclo.md`: a ação, a **integração com o motor do C11**, o **incremento/carimbo de ciclo**, o acesso 3Studio em duas camadas, e a **preservação do histórico**. Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Só reinicia provas em "Reprovada pelo Vendedor"** (outros estados → bloqueado).
2. ✅ Reiniciar **invoca o motor do C11** ("Reprovada → Criada") **e incrementa `ciclo_atual`** na **mesma transação atômica**; a movimentação é gravada no **log imutável** (RNF-006); **nenhum** caminho altera `status`/`ciclo_atual` por fora do motor.
3. ✅ O **status volta a "Criada"** e a **rota original é mantida** (imutável).
4. ✅ O **histórico do ciclo anterior é preservado integralmente**; cada `movimentacao` carrega o **`ciclo`** correto, e a **timeline (C13) mostra os ciclos separados**.
5. ✅ **Sem motivo e sem assinatura** (apenas confirmação do 3Studio autenticado — DP-2).
6. ✅ **Ação indisponível a perfis não-3Studio** (middleware/UI **e** validação de perfil/RLS do C11 → 403); botão visível **só em "Reprovada pelo Vendedor"** para 3Studio; **animação** (RF-024) com `prefers-reduced-motion`.
7. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**; (se migration) `upgrade`/`downgrade` limpa.

---

## 7. Testes desta camada

**Backend**
- Reiniciar **via o motor do C11**: estado vai para "Criada"; **`ciclo_atual` incrementado** na **mesma transação**; **movimentação** registrada; rota preservada; **atômico/idempotente** (reenvio não duplica nem incrementa duas vezes).
- **Estados inválidos:** tentar reiniciar prova que **não** está em "Reprovada pelo Vendedor" → bloqueado (transição não definida no C11 → 422).
- **Acesso:** perfil **não-3Studio** → **403** (validação do motor/RLS), mesmo chamando o endpoint diretamente.
- **Carimbo de ciclo (DP-3):** movimentações do ciclo anterior atribuídas ao ciclo antigo; as do novo ciclo ao incrementado; consistência verificável pelo C13.
- **Atomicidade:** falha no meio → status e `ciclo_atual` **não** mudam (rollback).
- Roda **offline** (Postgres local; JWTs de teste por perfil; provas via fixture em "Reprovada pelo Vendedor" e outros estados).

**Frontend**
- Botão visível **só a 3Studio** e **só em "Reprovada pelo Vendedor"**; modal **sem motivo**; confirmar → estado "Criada" refletido + timeline com novo ciclo separado.
- `prefers-reduced-motion` no modal.
- **E2E (Playwright):** 3Studio reinicia uma prova reprovada → "Criada", ciclo incrementado, timeline mostra ciclo 1 + ciclo 2; tentar em outro estado → indisponível; como Vendedor → ação indisponível.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md` e os **ADRs/schema do C11** (transição de reinício, serviço de transição, carimbo de `ciclo`) **e do C13** (agrupamento por ciclo); confirme Waves 0–2 + Wave 3 e o `ciclo_atual` do C08.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. Backend: integração com o motor do C11 (reiniciar → Criada + incremento atômico de `ciclo_atual`); carimbo de `ciclo` nas movimentações (DP-3); testes (motor, estados inválidos, acesso, atomicidade, carimbo).
4. Frontend: botão no detalhe (visível só a 3Studio, só em "Reprovada pelo Vendedor") + modal de confirmação (sem motivo, explicação); refletir "Criada" + timeline.
5. `prefers-reduced-motion`; revisão da animação do modal.
6. `docs/reinicio-ciclo.md`.
7. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
8. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: ação de reinício de ciclo (3Studio), via o motor do C11, com incremento de `ciclo_atual` e preservação do histórico.
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **reiniciar via o motor do C11 + incremento atômico** (DP-1); (b) **reinício sem assinatura nem motivo** (DP-2); (c) **carimbo de ciclo nas movimentações** (DP-3, incl. eventual retroação ao C11). Status *Aceita* onde aplicável.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes, **pendências**, e registre que a **Wave 3 está concluída** (sugerir **auditoria da Wave 3** antes da Wave 4, como nas anteriores); **próximo passo** = **W4-C16 · Dashboard com Contadores em Tempo Real**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre a **ação de reinício**, o **incremento/carimbo de ciclo** e que ela **passa pelo motor do C11**. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap: **Wave 3 concluída**.
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **acesso não-3Studio bloqueado** em duas camadas, **só em "Reprovada pelo Vendedor"**, **atomicidade transição+incremento**, **carimbo de ciclo**), (se migration) versionada/documentada, sem erro de console/log crítico, docs do módulo, animação do modal com `prefers-reduced-motion`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w3-c15): ...`, `chore(w3-c15): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. reinício via o motor do C11 com incremento atômico de ciclo, rota e histórico preservados, ciclos separados na timeline e acesso 3Studio em duas camadas), decisões registradas, o **status da Wave 3 (concluída)** e o **comando exato** para iniciar a próxima sessão (**W4-C16**), sugerindo a **auditoria da Wave 3** antes.

---

### Lembrete final
O reinício fecha o laço da reprovação — e seu cuidado central é a **consistência do par transição + incremento de ciclo**: os dois precisam acontecer **juntos, atomicamente, via o motor do C11**; nunca um sem o outro, nunca por fora do motor. E como **a mesma prova** ganha um novo ciclo (mesmo código/etiqueta), o **histórico anterior é sagrado** — preserve-o e **carimbe o ciclo** em cada movimentação para que a timeline conte a história certa. Reiniciar é **administrativo**: só confirmação (sem assinatura, sem motivo — §6.6). **Na dúvida, pare e pergunte.** Esta sessão fecha a Wave 3 — deixe-a sólida para auditar antes do dashboard.
