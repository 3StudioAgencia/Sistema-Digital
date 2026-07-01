# Prompt de Execução — Redesign da Tela de Assinatura (frontend-only, fora do backlog)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, o **C12 (Assinatura) mergeado**, e a **imagem do design anexada** (Assinatura). **Isto NÃO é um item de backlog** — é uma **troca de layout** da tela de assinatura. **Leia a §0.1 antes de tudo: o escopo é travado.**

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio). Sua tarefa nesta sessão é **trocar o layout (frontend) da tela de assinatura** para o novo design anexado — **sem alterar comportamento e sem tocar em mais nada**.

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (animações leves), arquitetura §5, §9 (comandos), §11 (o que NÃO fazer). Localize a **tela de assinatura do C12** (o componente de frontend + seu CSS Module) — é o **único** alvo desta sessão.

---

## 0.1 ESCOPO TRAVADO — regra dominante e inegociável

**O escopo desta sessão é EXCLUSIVAMENTE o frontend da tela de assinatura. Nada mais. Em hipótese nenhuma toque em qualquer outro componente, no backend, em migrations, em RLS, ou em componentes compartilhados.**

- ✅ **Permitido:** editar **apenas** os arquivos de **frontend da própria tela de assinatura** (o componente da tela + o(s) CSS Module(s) dela).
- ❌ **Proibido:** alterar **qualquer outro componente/tela**; o **backend** (endpoints, serviços, agregações, transição); **migrations/RLS**; **componentes compartilhados/reutilizados** (botões, app shell, wrappers usados por outras telas); a **lógica de submissão/transição/assinatura**; **adicionar chamadas de API ou busca de dados nova**.
- 🛑 **Se o design parecer exigir QUALQUER coisa fora do frontend da tela de assinatura** — mexer num componente compartilhado, buscar um dado que a tela ainda não tem, ajustar o backend — **PARE IMEDIATAMENTE e pergunte.** Não decida por conta própria contornar o escopo. **"Parecia necessário" não é justificativa para sair do escopo.**

Ao final, a **auto-auditoria (§7)** vai **provar via `git diff`** que **somente** os arquivos da tela de assinatura mudaram. Qualquer arquivo fora disso no diff é uma falha da sessão.

---

## 0.2 PRESERVAR O COMPORTAMENTO — re-skin muda pixels, não conduta

A tela de assinatura tem um **contrato funcional** (do C12) que **permanece idêntico**. Você está trocando **aparência**, não comportamento. **Preserve integralmente:**
- A **captura da assinatura** (`react-signature-canvas`) — o traço, o limpar, a validação de "assinou".
- A **submissão** e a **invocação da transição do C11** (a assinatura + a movimentação continuam atômicas; o motor é o mesmo).
- A **anti-enumeração** (mensagens genéricas; sem vazar quem é o próximo ator).
- A **resiliência (RNF-016)** — falha na submissão **preserva o traço + a ação** e oferece **retry**.
- O fluxo em **≤ 3 toques** (RNF-009) e o **mobile-first**.
- As **variantes Aprovar/Reprovar** (incl. o **motivo** na reprovação) — ver DP-1.
- **`prefers-reduced-motion`** e a contenção de animações.

Se uma mudança de layout **forçar** uma mudança de comportamento, isso é sinal de que você saiu do escopo — **PARE e pergunte** (§0.1).

---

## 0.3 Fidelidade ao novo design

**Tela de assinatura** (dentro do shell existente), conforme o design:
- **"← Voltar"** (topo, pill).
- Card com:
  - **Título** = nome da prova (ex.: "Mussarela Fatiada") + **badge "Requerimento: {nº}"**.
  - **Linha de metadados** (rótulo em cima, valor embaixo, em colunas): **Cliente** · **Vendedor** · **Rota** · **Ciclo** · **Criada em** · **Status**.
  - Rótulo **"Assinatura Digital"**.
  - **Área de canvas** ampla (caixa clara) com um **X** tênue e uma **linha** horizontal próxima à base, legenda **"Assine no espaço acima da linha"**.
  - **Rodapé:** ícone de info + texto **"Ao confirmar, você aprova as cores da prova digital"** (à esquerda); botões **"Cancelar"** (contorno) e **"Confirmar assinatura"** (escuro, com check) (à direita).

**Os dados do design são ilustrativos.** Layout/medidas/cores/tipografia seguem o design (confirme tokens via Figma se houver link — DP-4). **A área de canvas continua sendo o `react-signature-canvas` existente** — apenas com a moldura/afford visual do novo design.

---

## 1. Objetivo

Aplicar o **novo layout** à tela de assinatura (frontend), **fiel ao design**, **preservando 100% do comportamento do C12**, **sem tocar em nada além do frontend dessa tela**, registrando a mudança nos docs (§9) e validando com **auto-auditoria de não-regressão** (§7).

---

## 2. Escopo e NÃO-escopo (rígido)

### Faz parte desta sessão
- **Re-layout do frontend da tela de assinatura** conforme §0.3: cabeçalho com título + badge de requerimento + metadados (Cliente/Vendedor/Rota/Ciclo/Criada em/Status); rótulo "Assinatura Digital"; moldura/afford do canvas ("X" + linha + "Assine no espaço acima da linha"); rodapé com o disclaimer + Cancelar + Confirmar assinatura; botão Voltar.
- **Estilos** (CSS Module **da própria tela**) e ajustes de marcação **dentro do componente da tela**.
- **Exibição de metadados a partir dos dados que a tela já possui** (DP-2) — **sem** nova busca.
- **Atualização dos docs de contexto** (§9) — registrar a mudança mesmo não sendo backlog.
- **Auto-auditoria** (§7).

### NÃO faz parte (proibido — §0.1)
- ❌ Qualquer **outro componente/tela** (detalhe, escaneamento, dashboard, etc.).
- ❌ **Backend**, endpoints, serviços, **transição**, **migrations**, **RLS**.
- ❌ **Componentes compartilhados/reutilizados** (botão global, shell, wrapper de canvas usado por outras telas) — se precisar de um botão/afford, faça **local** à tela.
- ❌ **Nova chamada de API / busca de dados**.
- ❌ **Mudança de comportamento** (submissão, anti-enum, resiliência, Aprovar/Reprovar, ≤3 toques).
- ❌ **Dependências novas** (a menos que triviais e **locais** à tela — e, em dúvida, **pare e pergunte**).

> Qualquer impulso de "aproveitar para arrumar/alinhar X em outro lugar": **pare** e registre como pendência. **Não** é desta sessão.

---

## 3. Restrições técnicas (obrigatórias)

1. **Contenção total:** todas as mudanças em **arquivos da tela de assinatura**. **Zero** alteração fora disso (provado por `git diff` na §7).
2. **Comportamento intacto (§0.2):** o `react-signature-canvas`, a submissão, a invocação da transição do C11, a anti-enumeração, a resiliência e as variantes Aprovar/Reprovar **continuam funcionando exatamente como antes**.
3. **Sem nova busca de dados:** exiba os metadados a partir do que a tela **já recebe**; se faltar um campo, **pare e pergunte** (não crie fetch/backend).
4. **Sem componente compartilhado:** estilos e afford **locais**; não modifique nada reutilizado por outras telas.
5. **Estilização:** **CSS Modules**; fiel ao design; **mobile-first** preservado; animações `transform`/`opacity` com **`prefers-reduced-motion`**.
6. **Acessibilidade:** o canvas continua utilizável no touch; contraste/labels coerentes.
7. **Stateless**; **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

**DP-1 — Variantes Aprovar/Reprovar.**
O design mostra a variante de **aprovação** (disclaimer "Ao confirmar, você aprova as cores da prova digital"). O C12 tem **Aprovar/Reprovar** (com **motivo** na reprovação). **[Recomendado]** aplicar o novo layout **preservando as variantes**: a reprovação mantém o **campo de motivo** e o fluxo atual, no mesmo idioma visual; o disclaimer de aprovação aparece na variante de aprovar. Confirmar como a **reprovação** deve aparecer (o design só cobre a aprovação) — ou **preservar o comportamento atual** com o novo estilo.

**DP-2 — Origem dos metadados (sem nova busca).**
O cabeçalho mostra Cliente/Vendedor/Rota/Ciclo/Criada em/Status. **[Recomendado]** usar **os dados que a tela já recebe** (da prova identificada). **Se algum campo exibido não estiver disponível hoje na tela → PARE e pergunte** (não criar fetch nem mexer no backend). Confirmar a disponibilidade dos campos.

**DP-3 — Componentes compartilhados.**
**[Recomendado]** conter tudo em **estilos locais** da tela. **Se o layout parecer exigir mudar um componente compartilhado** (botão/shell/wrapper) → **PARE e pergunte** (não tocar — risco de regressão noutras telas). Confirmar.

**DP-4 — Tokens, "Cancelar" e "Voltar".**
**[Recomendado]** confirmar tokens/medidas via Figma (se houver link); **"Cancelar"** = abandonar a assinatura (comportamento atual) e **"Voltar"** = navegação de volta — **preservar** o que já existe. Confirmar.

---

## 5. Entregáveis

> Em dúvida, **pare e pergunte** (§0.1).

1. **Tela de assinatura re-estilizada** (frontend), fiel ao design (§0.3), com **comportamento idêntico** (§0.2), **contida** aos arquivos da própria tela.
2. **Atualização dos docs de contexto** (§9) registrando a mudança de layout (mesmo fora do backlog).
3. **Relatório da auto-auditoria** (§7) — incluído no resumo final e/ou em `docs/audits/AUTOAUDITORIA-ASSINATURA.md`.

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ A tela de assinatura está **fiel ao design** (Voltar; título + badge de requerimento; metadados Cliente/Vendedor/Rota/Ciclo/Criada em/Status; rótulo "Assinatura Digital"; canvas com "X" + linha + legenda; rodapé com disclaimer + Cancelar + Confirmar assinatura).
2. ✅ O **comportamento é idêntico ao anterior**: captura do traço, submissão, **invocação da transição do C11**, anti-enumeração, **resiliência (RNF-016)**, **≤ 3 toques**, variantes **Aprovar/Reprovar** (motivo na reprovação) — **tudo funcionando**.
3. ✅ **Nenhum arquivo fora do frontend da tela de assinatura foi alterado** (provado por `git diff` — §7).
4. ✅ **Nenhuma nova chamada de API/busca** foi adicionada; **nenhum** componente compartilhado/back foi tocado.
5. ✅ **`prefers-reduced-motion`** preservado; **mobile-first** preservado; responsivo.
6. ✅ **Suíte inteira verde, sem regressão**; `pnpm lint`/`build` (e `ruff`/`mypy`/`pytest` — que **não deveriam** ter mudado) **verdes**.

---

## 7. Auto-auditoria de não-regressão (OBRIGATÓRIA — antes do encerramento)

Antes de fechar a sessão, **você mesmo audita** o seu trabalho e **prova** que nada regrediu:

1. **Escopo (git diff):** rode `git status`/`git diff --stat` e **liste os arquivos alterados**. **Todos** devem ser do **frontend da tela de assinatura**. **Qualquer** arquivo fora disso = **falha** → reverta a alteração indevida (ou, se acredita ser necessária, **pare e pergunte** — não deixe no diff).
2. **Comportamento preservado:** rode os **testes existentes do C12** (e o E2E do fluxo identificar→assinar→confirmar, se houver) — **todos verdes**. Verifique manualmente/por teste: o traço é capturado; a submissão invoca a transição; a reprovação ainda exige motivo; a resiliência preserva o traço numa falha simulada; ≤ 3 toques.
3. **Sem regressão no resto:** rode a **suíte inteira** + `lint`/`build` — **verde**. Confirme que **nenhum** outro componente/tela foi afetado (o diff já prova; a suíte confirma).
4. **Fidelidade ao design:** confira item a item contra o design (§0.3 / §6.1).
5. **Sem novas dependências/chamadas:** confirme que não há nova lib (salvo trivial e local, se aprovado na DP) nem nova chamada de API.
6. **Registre o resultado** — um pequeno relatório (no resumo final e/ou `docs/audits/AUTOAUDITORIA-ASSINATURA.md`) com: a **lista de arquivos alterados** (provando o escopo), o **status dos testes/suíte**, e a **confirmação de não-regressão**. Se **qualquer** item falhar, **não feche** — corrija ou **pare e pergunte**.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, **localize a tela de assinatura do C12** (componente + CSS Module) e entenda o **comportamento atual** (submissão, anti-enum, resiliência, Aprovar/Reprovar).
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. Re-estilize **apenas** a tela: cabeçalho + metadados, moldura/afford do canvas, rodapé com disclaimer + botões, Voltar — **preservando todo o comportamento**.
4. `prefers-reduced-motion`; responsividade; revisão de acessibilidade do canvas.
5. **Auto-auditoria (§7)** — git diff escopado + testes + suíte + fidelidade.
6. **Atualização dos docs (§9).**
7. Verifique **todos** os critérios de aceitação (§6).

> Em qualquer dúvida que toque algo fora da tela de assinatura, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — atualizar TODOS os docs, mesmo fora do backlog)

Esta mudança **não** é item de backlog, mas **deve ficar registrada** para o projeto seguir alinhado. **Execute e confirme:**

1. **`CHANGELOG.md`** — em `[Unreleased] → Changed`: **redesign do layout da tela de assinatura** (frontend; comportamento inalterado).
2. **`DECISIONS.md`** — **ADR** registrando: a **decisão de trocar o layout** da tela de assinatura (mudança de UX fora do backlog), o **escopo travado** (somente frontend dessa tela), e a **confirmação de que o comportamento do C12 foi preservado**. Inclua as respostas dos Pontos de Decisão (DP-1 reprovação, DP-2 metadados, etc.). Status *Aceita*.
3. **`SESSION_LOG.md`** — entrada: que foi uma **sessão de redesign frontend da tela de assinatura (fora do backlog)**, o que mudou, as decisões, o **resultado da auto-auditoria** (escopo respeitado + sem regressão), e que **nenhum outro componente foi tocado**.
4. **`CLAUDE.md`** — se a tela de assinatura é descrita/aludida lá, **atualize** a descrição do layout (mantendo o registro do comportamento). Enxuto e verdadeiro.
5. **`README.md`** — atualize se houver menção à tela (screenshots/descrição).
6. **Definition of Done** (`CLAUDE.md §8`): comportamento preservado, **auto-auditoria verde**, **git diff escopado**, suíte verde, animações com `prefers-reduced-motion`, sem segredos versionados.
7. **Commits semânticos** — `style(assinatura): novo layout da tela de assinatura` (e `docs: registro do redesign da tela de assinatura`). Árvore limpa, lockfiles commitados. **Use `style`/`refactor`** (não `feat`) — não há nova funcionalidade.

Ao concluir, **apresente um resumo** com: o que mudou no layout, a **evidência de cada critério de aceitação (§6)**, o **relatório da auto-auditoria** (lista de arquivos alterados provando o escopo + suíte verde + não-regressão), as decisões registradas nos docs, e a confirmação de que **nada além da tela de assinatura foi tocado**.

---

### Lembrete final
Esta sessão é uma **troca de roupa**, não uma cirurgia: a tela de assinatura **veste** um novo layout, mas **faz exatamente o que fazia** — assina, submete, transiciona, resiste a falhas, respeita perfis. Dois compromissos acima de tudo: **não saia do frontend desta tela** (se algo parecer exigir mexer em outro componente, no backend, num componente compartilhado, ou numa busca nova — **pare e pergunte**, nunca contorne); e **não mude o comportamento** (re-skin é pixel, não conduta). No fim, **prove** com `git diff` que só a tela de assinatura mudou e com a suíte verde que nada regrediu. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
