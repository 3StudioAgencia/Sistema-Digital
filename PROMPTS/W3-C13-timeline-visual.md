# Prompt de Execução — W3-C13 · Timeline Visual com 4 Rotas e Laminação

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–2 auditadas (GO)** e os **C10, C11 e C12 mergeados**. Este componente **preenche a seção "Histórico de movimentações"** do detalhe (C08), que ficou em empty state. Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (robustez, escalabilidade, **mínimo de requisições**, observabilidade, **animações leves e suaves**), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–2 + C10–C12 entregues):**
- C05: `useAuthorization` + helpers de RLS + propagação de claims (ADR-008).
- C06: `provas` (`rota`, `status`, `ciclo_atual`); rótulos de rota (módulo do C08).
- C07: **módulo de rótulos de status** (`enum → rótulo`). **Reuse-o.**
- C08: **página de detalhe** com a seção **"Histórico de movimentações" em empty state** — é **aqui** que a timeline entra. Reuse o padrão visual/tokens.
- C11: **`transition_rules`** (em `/domain/state_machine/`) — a fonte da sequência canônica por rota (ver DP-1) — e a tabela **`movimentacoes`** (ator, de→para, motivo, data/hora) com **RLS** por perfil. **Reuse — não duplique a §6.**
- C12: assinatura + transição ponta a ponta — gera as `movimentacoes` que a timeline lê.

**Insumo:** **não há design do Figma desta tela** — ver DP-5 (seguir o padrão visual estabelecido e confirmar/fornecer o Figma).

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — fonte do caminho canônico, agrupamento por ciclo, representação de estados especiais, layout — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, **leia o ADR/schema do C11** (as `transition_rules` e o schema de `movimentacoes` — em especial se há campo de `ciclo`), confirme o estado das Waves 0–2 + C10–C12 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas.
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte. **Nunca invente** a sequência de estágios de uma rota, os rótulos, ou a forma de agrupar ciclos.

---

## 1. Objetivo do componente

Entregar o componente **`<ProofTimeline rota historico estado_atual />`** — a **timeline visual** embutida no detalhe (C08) — que renderiza **adaptativamente** o caminho da prova conforme a **rota** (número de etapas variável), revela os estágios **progressivamente**, **destaca a etapa atual** (animado), indica **laminação** e o **contexto de cada travessia de motorista**, mostra **reprovações com motivo** e **múltiplos ciclos com separador**, lendo o histórico de `movimentacoes` (C11) com **respeito à RLS**.

Referências: Backlog **C13** · Requisitos **RF-012, RF-026, RN-006, RN-012, RNF-010** · §6 (caminhos por rota) · §7 (Timeline = mesmo escopo do detalhe) · C11 (regras + `movimentacoes`) · C08 (detalhe/empty state) · C07 (rótulos de status).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **Componente (Backlog C13):** `<ProofTimeline rota historico estado_atual />`, aceita as **4 rotas**; **renderização adaptativa por rota**; **badge da rota no topo**.
2. **O que a timeline mostra (RF-012, US-011):** estágios **percorridos**, a **rota** seguida, a **etapa de laminação quando aplicável**, **reprovações com motivo**, e o **responsável + timestamp** de cada etapa. Adapta-se ao **número de etapas** da rota (Lam. Matriz ~11; Filial ~4).
3. **Etapas de motorista indicam o contexto:** ida laminação, volta laminação, entrega final (os três estados distintos).
4. **Reprovações com motivo em destaque**; **múltiplos ciclos com separador claro** (RN-006: reinício preserva o histórico do ciclo anterior).
5. **Laminação diferenciada:** em rotas laminadas, as etapas de laminação têm **indicação visual diferenciada**.
6. **Animação (RF-026, RN-012, RNF-010):** **revelação progressiva** dos estágios percorridos + **destaque animado da etapa atual** (Framer Motion), respeitando **`prefers-reduced-motion`**.
7. **Acesso (§7):** a timeline é **embutida no detalhe** e segue **as mesmas regras** (3Studio/Clicheria todas; Vendedor/Motorista escopados) — a **RLS de `movimentacoes`** (C11) já garante o escopo dos dados.

## 1.2 Caminhos por rota (§6 — referência; a fonte oficial prevalece)

- **Matriz:** Criada → Retirada pelo Vendedor → Aprovada pelo Vendedor → De volta à 3Studio → Com Motorista (entrega final) → Recebida pela Clicheria.
- **Lam. Matriz:** Criada → Encaminhada para Laminação → Com Motorista (ida laminação) → Laminação Concluída → Com Motorista (volta laminação) → De volta à 3Studio (pós-laminação) → Retirada pelo Vendedor → Aprovada pelo Vendedor → De volta à 3Studio → Com Motorista (entrega final) → Recebida pela Clicheria.
- **Filial:** Criada → Encaminhada para o Vendedor → Aprovada pelo Vendedor → Recebida pela Clicheria.
- **Lam. Filial:** Criada → Encaminhada para Laminação → Com Motorista (ida laminação) → Laminação Concluída → Encaminhada para o Vendedor → Aprovada pelo Vendedor → Recebida pela Clicheria.
- **Transversais:** Reprovação (a partir dos estados de posse do vendedor) → "Reprovada pelo Vendedor"; **Cancelamento** (qualquer estado ativo) → "Cancelada".

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão (predominantemente frontend)
- **Componente `<ProofTimeline rota historico estado_atual />`** embutido na seção "Histórico de movimentações" do **detalhe (C08)** — substituindo o empty state: badge da rota; **renderização adaptativa por rota** (caminho canônico — DP-1); estágios percorridos (com **responsável + timestamp**), **etapa atual destacada** (animada), futuros esmaecidos; **laminação diferenciada**; **contexto das travessias de motorista**; **reprovações com motivo em destaque**; **múltiplos ciclos com separador** (DP-3).
- **Fetch das movimentações** (DP-2): a lista de `movimentacoes` da prova, **respeitando a RLS** (C11).
- **Animação** (RF-026): revelação progressiva + destaque da etapa atual (Framer Motion; GPU-only; **`prefers-reduced-motion`**).
- **Estados de loading/erro/vazio** (se ainda sem movimentação — DP-4) tratados.
- **Documentação** (`docs/timeline.md`): o componente, a fonte do caminho canônico, o fetch/RLS, o agrupamento por ciclo, e a representação dos estados especiais. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Lógica de transição / `transition_rules` / `movimentacoes`** — é do **C11**. O C13 **lê** e **renderiza**; não cria nem altera.
- ❌ **Cancelamento (C14) / Reinício de ciclo (C15)** — a timeline **representa** reprovação/cancelamento/ciclos, mas as **ações** são C14/C15.
- ❌ **Assinatura / identificação** (C10/C12).
- ❌ Dashboard, relatórios (Waves 4–5).

> Vontade de adiantar ações de cancelar/reiniciar ou mexer no C11: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Fonte única do caminho canônico:** **não duplique a §6** — derive das **`transition_rules` do C11** (DP-1). Se uma representação no frontend for inevitável, ela tem **teste de consistência** contra as regras do C11.
2. **RLS respeitada:** o fetch de `movimentacoes` passa por **claims propagados** (a RLS do C11 escopa os dados); a timeline **não** contorna o escopo. **Mínimo de requisições:** idealmente a timeline aproveita o que o detalhe (C08) já carrega + uma chamada para o histórico (DP-2), sem refetch redundante.
3. **Representação fiel:** laminação diferenciada; contexto de motorista (ida/volta/entrega); reprovação com motivo em destaque; ciclos com separador.
4. **Animação contida (RF-026/RNF-010):** apenas `transform`/`opacity`, durações curtas, **`prefers-reduced-motion`** obrigatório (revelação instantânea quando ativo).
5. **Estilização:** **CSS Modules**; padrão visual do C08/C04; **responsivo** (o detalhe é visto no mobile).
6. **Robustez:** estados de loading/erro/vazio; não derruba o detalhe se o histórico falhar (degradação graciosa).
7. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada.

### Bloco A — Dados

**DP-1 — Fonte do caminho canônico por rota.**
A timeline renderiza adaptativamente a sequência de estágios da rota. **[Recomendado]** **derivar das `transition_rules` do C11** (fonte única — não duplicar a §6): um helper/endpoint que, dada a `rota`, retorna a **sequência canônica de estágios**; o frontend a usa com os **rótulos** (status do C07, rota do C08). **Alternativa:** estrutura no frontend espelhando a §6 (1.2), com **teste de consistência** contra as regras do C11. Confirmar a fonte.

**DP-2 — Fetch das movimentações.**
O `historico` é a lista de `movimentacoes` (ator + data/hora + de→para + motivo), **respeitando a RLS** (C11). **[Recomendado]** `GET /api/provas/{id}/movimentacoes` (ou **estender o detalhe do C08** para já trazer o histórico — menos requisições), claims propagados. Confirmar onde vive o fetch.

**DP-3 — Agrupamento por ciclo (múltiplos ciclos).**
O critério exige "cada ciclo com separador claro". Para isso, as `movimentacoes` precisam ser **agrupáveis por ciclo**. **[Recomendado]** as `movimentacoes` carregam o **`ciclo`** (carimbado na transição) — se o C11/C15 ainda **não** carimba, **isto retroage** (adicionar o campo + popular). **Alternativa:** derivar as fronteiras de ciclo dos **eventos de reinício** (transição "Reprovada pelo Vendedor → Criada"). Confirmar a abordagem (e se retroage ao C11/C15).

### Bloco B — Representação e UX

**DP-4 — Quando a timeline aparece + estados especiais.**
**[Recomendado]** mostrar o **caminho esperado completo** desde a criação (percorridos preenchidos, atual destacado, futuros esmaecidos); **reprovação** com **motivo em destaque**; **cancelamento** como **terminal**; **laminação** com **indicação visual diferenciada**; **travessias de motorista** com o **contexto** (ida/volta laminação, entrega final); **múltiplos ciclos** com **separador**. **Alternativa** (quando aparece): manter o **empty state** do C08 até a 1ª movimentação. Confirmar.

**DP-5 — Animação + layout (sem design).**
**[Recomendado]** `<ProofTimeline rota historico estado_atual />` embutido no detalhe (C08); **badge da rota no topo**; **revelação progressiva** + **destaque animado da etapa atual** (Framer Motion; GPU-only; **`prefers-reduced-motion`**); layout **responsivo** (vertical no mobile). **Não há design** — confirmar/fornecer o Figma para fidelidade exata.

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- **`<ProofTimeline rota historico estado_atual />`** — renderização adaptativa por rota (caminho canônico — DP-1); estágios percorridos (responsável + timestamp), atual destacado (animado), futuros esmaecidos; laminação diferenciada; contexto de motorista; reprovação com motivo; **ciclos com separador** (DP-3); reusa os rótulos (C07/C08). Embutido no detalhe (C08), substituindo o empty state.
- Animação (Framer Motion; GPU-only; `prefers-reduced-motion`); estados de loading/erro/vazio; responsivo.

### 5.2 Backend — `apps/api/` (se aplicável)
- **Fetch de `movimentacoes`** (DP-2): `GET /api/provas/{id}/movimentacoes` (ou extensão do detalhe), claims propagados (RLS); (se DP-1 = endpoint) a **sequência canônica por rota** derivada das regras do C11; (se DP-3 = retroação) o campo `ciclo` em `movimentacoes`. Logs estruturados.

### 5.3 Documentação — `docs/`
- `docs/timeline.md`: o componente `<ProofTimeline>`, a **fonte do caminho canônico**, o fetch/RLS, o **agrupamento por ciclo**, e a representação de laminação/motorista/reprovação/cancelamento. Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Renderiza corretamente para as 4 rotas** (Matriz, Lam. Matriz, Filial, Lam. Filial), adaptando-se ao número de etapas; **badge da rota** no topo.
2. ✅ Cada etapa percorrida mostra **responsável + data/hora**; a **etapa atual é destacada** (animada).
3. ✅ Em **rotas laminadas**, as etapas de laminação têm **indicação visual diferenciada**; **travessias de motorista** indicam o **contexto** (ida/volta laminação, entrega final).
4. ✅ **Reprovações** exibidas com **motivo em destaque**; **provas com múltiplos ciclos** exibem **cada ciclo com separador claro** (DP-3).
5. ✅ O **acesso respeita a Matriz §7** (mesmo escopo do detalhe; dados escopados pela RLS de `movimentacoes`).
6. ✅ A **revelação respeita `prefers-reduced-motion`** (RN-012, RNF-010); o caminho canônico **não duplica** a §6 (DP-1); responsivo.
7. ✅ Estados de loading/erro/vazio; a falha do histórico **não derruba** o detalhe.
8. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**; (se houve migration) `upgrade`/`downgrade` limpa.

---

## 7. Testes desta camada

**Frontend**
- Renderização das **4 rotas** com o número correto de etapas; badge da rota; estágios percorridos (responsável + timestamp), atual destacado, futuros esmaecidos.
- **Laminação diferenciada**; **contexto de motorista** correto (ida/volta/entrega).
- **Reprovação** com motivo em destaque; **múltiplos ciclos** com separador (fixture de prova reiniciada).
- **`prefers-reduced-motion`** → revelação instantânea.
- Responsivo (vertical no mobile); estados de loading/erro/vazio.

**Backend (se aplicável)**
- Fetch de `movimentacoes` **respeitando a RLS** (por perfil; fora do escopo → 0 registros); (se DP-1 = endpoint) sequência canônica por rota **consistente com as regras do C11**.
- (Se DP-3 = retroação) `ciclo` carimbado corretamente; migration `upgrade`/`downgrade`.
- **Consistência do caminho canônico** (DP-1): teste que confirma que a sequência usada bate com as `transition_rules` do C11.

**E2E (Playwright)**
- Abrir o detalhe de uma prova com histórico → timeline renderiza o caminho da rota com a etapa atual destacada; prova reiniciada → ciclos separados; reprovada → motivo em destaque.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md` e o **ADR/schema do C11** (regras + `movimentacoes`, campo de `ciclo`); confirme Waves 0–2 + C10–C12 e o empty state do C08.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. (Se aplicável) backend: fetch de `movimentacoes` (DP-2); sequência canônica por rota (DP-1); campo `ciclo` (DP-3); testes (RLS, consistência com o C11).
4. Frontend: `<ProofTimeline>` (adaptativo por rota, etapas com responsável/timestamp, atual destacado, laminação/motorista/reprovação/ciclos), embutido no detalhe (C08); animação + `prefers-reduced-motion`; estados de loading/erro/vazio.
5. Responsividade; revisão da animação contida.
6. `docs/timeline.md`.
7. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
8. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: timeline visual (`<ProofTimeline>`) embutida no detalhe; (se aplicável) endpoint de `movimentacoes` e/ou campo `ciclo`.
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **fonte do caminho canônico** (DP-1); (b) **fetch de movimentações** (DP-2); (c) **agrupamento por ciclo** (DP-3, incl. eventual retroação ao C11/C15); (d) **representação dos estados especiais** (DP-4). Status *Aceita* onde aplicável.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes, **pendências** (ações de cancelar = C14; reiniciar = C15) e **próximo passo** = **W3-C14 · Cancelamento de Prova Digital**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre o **componente `<ProofTimeline>`**, a **fonte do caminho canônico** e (se houve) o campo `ciclo`. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap (C13 concluído).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. as **4 rotas**, **múltiplos ciclos**, **RLS** do histórico), animações com **`prefers-reduced-motion`**, sem erro de console/log crítico, docs do módulo, (se migration) versionada/documentada, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w3-c13): ...`, `chore(w3-c13): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. a renderização das 4 rotas, laminação diferenciada, ciclos separados e reprovação com motivo), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W3-C14**).

---

### Lembrete final
A timeline é como o usuário **enxerga a verdade** do fluxo — por isso ela deve **espelhar exatamente** a máquina de estados: o caminho canônico vem das **regras do C11 (fonte única)**, não de uma cópia da §6 que pode divergir. Os casos que diferenciam uma boa timeline de uma confusa são os **especiais**: a **laminação** (visualmente distinta), o **contexto da travessia do motorista**, a **reprovação com motivo** e os **múltiplos ciclos com separador** — trate-os com cuidado. E a animação é **enfeite contido**: leve, GPU-only, e **instantânea** sob `prefers-reduced-motion`. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
