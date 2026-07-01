# Prompt de Remediação — Wave 3 · Movimentação (C10–C15)

> **Como usar:** cole este prompt no Claude Code, no repositório onde a **auditoria da Wave 3 já rodou** e produziu **`docs/audits/AUDITORIA-WAVE-3.md`** com veredito **NO-GO** (ou GO com achados a tratar). Esta sessão **corrige os achados do relatório** — nada além disso. Ao final, recomenda-se **re-auditar**.

---

## 0. Contexto e autoridade

Você é um **engenheiro de software sênior** encarregado de **fechar os achados da auditoria da Wave 3** (C10 escaneamento, C11 máquina de estados, C12 assinatura, C13 timeline, C14 cancelamento, C15 reinício de ciclo). Esta é a wave que toca o **estado das provas** — corrija com o mesmo rigor com que ela foi auditada.

**Leia, nesta ordem:**
1. **`docs/audits/AUDITORIA-WAVE-3.md`** — a **lista autoritativa do que corrigir**. Cada achado tem evidência, impacto e uma recomendação.
2. **`CLAUDE.md`, `DECISIONS.md`** — as regras e decisões vigentes (uma correção não pode violar um ADR aceito sem nova decisão).
3. Os **requisitos** (§6, §7, RF/RN/RNF) citados nos achados — a fonte da verdade do comportamento esperado.

---

## 0.1 Princípio dominante — O RELATÓRIO É O MAPA; CORRIJA A CAUSA RAIZ

- **Corrija somente o que o relatório aponta.** Não "aproveite para melhorar" o que não foi flagrado. Escopo novo, refatoração oportunista e features não estão nesta sessão.
- **Causa raiz, não sintoma.** Não faça o teste passar mascarando o problema — elimine a causa. Se o achado é "status muda fora do motor", a correção **roteia pelo motor**, não adiciona um `if` que esconde o sintoma.
- **PARE E PERGUNTE.** Se fechar um achado exigir uma **decisão de design** não trivial (ex.: como resolver uma divergência design×requisito, qual o comportamento correto numa borda que o requisito não cobre), **pare, exponha as opções e a recomendação, e aguarde** — não decida sozinho.
- **Uma correção não pode abrir outro buraco.** Em particular (Wave 3): nenhuma correção pode **criar um caminho de status fora do motor do C11**, **quebrar atomicidade/idempotência**, ou **enfraquecer a RLS/anti-enumeração**. Se a única saída aparente faz isso, **pare e pergunte**.

---

## 0.2 Sem regressão — cada correção é blindada por um teste

- Para **cada achado** corrigido, escreva (ou ative) um **teste de regressão** que **reproduz o problema e prova o fechamento** — de modo que o defeito **não possa voltar silenciosamente**.
- Rode a **suíte inteira** após cada correção: fechar um achado **não pode quebrar** outro componente. Se quebrar, isso é parte da remediação.

---

## 1. Objetivo

Levar a Wave 3 ao estado **GO**: **fechar todos os achados Críticos e Altos** do relatório (obrigatório), tratar os **Médios** conforme decidido, e deixar a wave **re-auditável** com a suíte verde e sem regressão.

---

## 2. O que NÃO fazer (limites da remediação)

- ❌ **Não** corrija o que **não** está no relatório (a menos que seja um efeito colateral direto de uma correção — e, nesse caso, registre).
- ❌ **Não** refatore além do necessário para a correção; **não** renomeie/reorganize por gosto.
- ❌ **Não** adicione features, contadores, telas, campos que o relatório não pediu.
- ❌ **Não** altere ADRs aceitos para "facilitar" uma correção sem uma nova decisão registrada.
- ❌ **Não** feche um achado de forma que abra outro (caminho de status paralelo, perda de atomicidade, RLS enfraquecida).

> Impulso de "já que estou aqui, melhoro X": **pare** e anote como pendência — não é desta sessão.

---

## 3. Método de remediação (por achado)

Para **cada achado**, na ordem **🔴 Críticos → 🟠 Altos → 🟡 Médios (se no escopo) → ⚪ Baixos (opcional)**:

1. **Leia a evidência** do relatório e **reproduza** o problema (rode o comando/teste/query que o achado descreve) — confirme que você está vendo o mesmo defeito.
2. **Identifique a causa raiz** (não o sintoma).
3. **Corrija** a causa, respeitando os limites da §2 e o princípio da §0.1 (sem abrir outro buraco).
4. **Escreva/ative o teste de regressão** que prova o fechamento.
5. **Rode a suíte inteira** — confirme zero regressão.
6. **Atualize o relatório** (`AUDITORIA-WAVE-3.md`): marque o achado como **Resolvido**, com a referência ao commit/teste que o fecha.

**Cuidados específicos da Wave 3** (conforme o tipo de achado):
- **Caminho de status fora do motor** → roteie a mudança pelo **serviço de transição do C11**; teste que **não há** `UPDATE` em `status` fora do motor.
- **Atomicidade (C12 assinatura+movimentação; C15 transição+ciclo)** → envolva na **mesma transação**; teste o **rollback** sob falha injetada.
- **Idempotência** → garanta a chave/lock; teste o **reenvio** (não duplica).
- **Anti-enumeração (C10/C12)** → **unifique** as respostas; teste a **igualdade** entre "inválido" e "fora de escopo".
- **RLS / `BYPASSRLS` / `FORCE RLS`** → corrija o privilégio/política; teste **acesso fora de escopo → 0 registros**.
- **Carimbo/agrupamento de ciclo (C13/C15)** → corrija o carimbo no insert; teste o **agrupamento** e a **preservação do histórico** após reinício.
- **Acesso administrativo (C14/C15)** → garanta a **segunda camada** (motor/RLS); teste a **chamada direta** por não-3Studio → 403.

---

## 4. Pontos de Decisão (quando a correção exigir)

A maioria dos achados tem correção objetiva (a recomendação do relatório basta). **Mas** se algum exigir uma decisão — por exemplo:
- **Como** resolver uma divergência design×requisito que o relatório apontou (seguir o design? complementar? qual comportamento é o correto?);
- **Qual** o comportamento esperado numa borda que o requisito **não** cobre;
- **Onde** alocar uma correção que toca a fronteira entre dois componentes —

**apresente em bloco** essas decisões (2–3 opções + recomendação) **e aguarde a resposta** antes de implementar. Registre cada decisão em `DECISIONS.md` (ADR).

---

## 5. Entregáveis

1. **Correções de código** — focadas, de causa raiz, dentro do escopo do relatório.
2. **Testes de regressão** — **um por achado** (no mínimo para Críticos e Altos), provando o fechamento.
3. **`docs/audits/AUDITORIA-WAVE-3.md` atualizado** — cada achado com status (**Resolvido** / **Não aplicável** com justificativa / **Adiado** com decisão registrada) e a referência ao commit/teste.
4. **Atualização dos docs de contexto** (§9) — `CHANGELOG`, `DECISIONS` (se houve decisão), `SESSION_LOG`, e `CLAUDE.md`/`README` se algo estrutural mudou.

---

## 6. Critérios de aceitação

1. ✅ **Todos os achados Críticos e Altos** do relatório estão **Resolvidos**, cada um com **teste de regressão** que prova o fechamento.
2. ✅ **Nenhuma correção abriu outro buraco**: nenhum novo caminho de status fora do motor, nenhuma perda de atomicidade/idempotência, nenhuma RLS/anti-enumeração enfraquecida (verificável por teste).
3. ✅ **Suíte inteira verde** (`ruff`, `mypy --strict`, `pytest` com a cobertura exigida, `pnpm lint`, `build`); **sem regressão** em outros componentes.
4. ✅ Migrations `upgrade`/`downgrade` limpas; RLS reaplicável (se a correção tocou banco/RLS).
5. ✅ O **relatório de auditoria** reflete o status real de cada achado.
6. ✅ **Sem escopo novo**; ADRs respeitados (ou novas decisões registradas); **sem segredos versionados**.

---

## 7. Testes desta sessão

- **Um teste de regressão por achado** Crítico/Alto (e por Médio corrigido), nomeado de forma rastreável ao ID do achado.
- **Re-execução da suíte inteira** — confirma fechamento **e** ausência de regressão.
- Onde a auditoria usou testes descartáveis em `audit/` para evidenciar o defeito, **promova** os relevantes a testes de regressão permanentes (na suíte oficial) quando fizer sentido — ou substitua-os por testes equivalentes bem alocados.
- Roda **offline** (Postgres local; JWTs de teste por perfil; fixtures de prova nos estados relevantes).

---

## 8. Ordem de execução sugerida

1. Leia o **relatório** e os ADRs/requisitos referenciados.
2. **Reproduza** os achados Críticos e Altos (confirme a linha de base).
3. Se algum achado exigir decisão, **apresente os Pontos de Decisão (§4) e aguarde**.
4. Corrija **na ordem de severidade**, um a um: causa raiz → teste de regressão → suíte verde → atualizar o relatório.
5. Trate Médios (se no escopo) e Baixos (opcional).
6. Rode a **suíte inteira** uma última vez; confirme todos os critérios (§6).
7. Execute o **Protocolo de Encerramento** (§9) e **recomende a re-auditoria**.

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida que envolva decisão, **pare e pergunte** (§0.1/§4).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

1. **`CHANGELOG.md`** — em `[Unreleased] → Fixed`: a lista das correções (referenciando os IDs dos achados).
2. **`DECISIONS.md`** — ADRs apenas se alguma correção exigiu uma **decisão** (§4); status *Aceita*.
3. **`SESSION_LOG.md`** — entrada: que foi uma **sessão de remediação** dirigida pelo relatório; achados fechados (por severidade); decisões tomadas; e o **próximo passo** = **re-auditar a Wave 3** (e, se GO, **W5-C17**).
4. **`docs/audits/AUDITORIA-WAVE-3.md`** — atualizado com o status final de cada achado.
5. **`CLAUDE.md` / `README.md`** — atualize **só** se algo estrutural mudou.
6. **Definition of Done** (`CLAUDE.md §8`): suíte verde com cobertura, migrations/RLS reaplicáveis (se tocadas), sem erro de console/log crítico, sem segredos versionados, **sem regressão**.
7. **Commits semânticos** — `fix(w3-cNN): <achado>` por correção; `test(w3-cNN): regressão do achado <ID>`; `chore(w3-audit): status dos achados`. Árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: os achados **Críticos e Altos fechados** (com o teste que prova cada um), quaisquer **decisões** tomadas, o **status atualizado do relatório**, a confirmação de **suíte verde sem regressão**, e a **recomendação de re-auditoria** (com o comando exato para iniciá-la).

---

### Lembrete final
Remediar não é "fazer o teste ficar verde" — é **eliminar a causa** sem abrir uma nova fenda. Nesta wave, a tentação mais perigosa é fechar um achado com um atalho que **contorne o motor**, **quebre a atomicidade** ou **afrouxe a RLS** — o que trocaria um bug visível por um invisível e pior. Cada correção é **blindada por um teste** para nunca mais voltar, e o relatório de auditoria é atualizado para contar a verdade. Quando terminar, **mande re-auditar**: a palavra final sobre o GO é da auditoria, não da remediação. **Na dúvida que envolva decisão, pare e pergunte.**
