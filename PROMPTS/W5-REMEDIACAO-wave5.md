# Prompt de Remediação — Wave 5 · Relatórios e Refinamento de UX

> **Como usar:** cole este prompt no Claude Code, no repositório onde a **auditoria de fechamento da Wave 5 já rodou** e produziu **`docs/audits/AUDITORIA-WAVE-5.md`** com veredito **NO-GO** (ou GO com achados a tratar). **Escopo da Wave 5:** apenas o **C17 (Relatórios)** — o **C18 (Atalhos Rápidos) foi CORTADO por decisão de produto**. Esta sessão **corrige os achados do relatório** — nada além disso. Ao final, **re-auditar**.

---

## 0. Contexto e autoridade

Você é um **engenheiro de software sênior** encarregado de **fechar os achados da auditoria de fechamento da Wave 5**.

**Leia, nesta ordem:**
1. **`docs/audits/AUDITORIA-WAVE-5.md`** — a **lista autoritativa do que corrigir** (achados de integração, regressão, corte do C18, qualidade transversal, e a incorporação do veredito do C17).
2. **`docs/audits/AUDITORIA-C17.md`** — se o relatório da wave apontou que o **núcleo do C17** ainda tem achados Críticos/Altos, eles seguem a **disciplina de remediação do C17** (recomputação independente — ver §3, cuidado E).
3. **`CLAUDE.md`, `DECISIONS.md`** — regras e decisões vigentes (incl. a **decisão de cortar o C18**). Uma correção não pode violar um ADR aceito sem nova decisão.

---

## 0.1 Princípio dominante — O RELATÓRIO É O MAPA; CAUSA RAIZ

- **Corrija somente o que o `AUDITORIA-WAVE-5.md` aponta.** Sem escopo novo, sem refatoração oportunista.
- **Causa raiz, não sintoma.** Não faça o teste passar mascarando o problema — elimine a causa.
- **PARE E PERGUNTE** se fechar um achado exigir uma **decisão** não trivial (ex.: como reconciliar uma divergência de acesso; qual comportamento correto numa borda). Exponha opções + recomendação e aguarde; registre em ADR.

---

## 0.2 Sem regressão — e os dois guardrails desta wave

- **Um teste de regressão por achado**, que reproduz o problema e prova o fechamento (para não voltar).
- **Rode a suíte inteira** após cada correção: fechar um achado **não pode quebrar** outro componente.
- **Guardrail 1 — integração é faca de dois gumes:** vários achados desta wave são sobre o **reuso compartilhado** (a função de horas úteis e a agregação que o **C16 e o C17 dividem**). Uma correção desse código **tem que manter os dois lados corretos** — o **número compartilhado** (ex.: "Atrasadas") **deve continuar batendo no dashboard e no relatório**. Consertar um lado e quebrar o outro **não é fechar o achado**.
- **Guardrail 2 — o C18 foi CORTADO:** achados sobre o corte do C18 (ex.: "existe um atalho de relatórios", "sobra órfã do C18", "docs não refletem o corte") se resolvem **REMOVENDO/LIMPANDO** — **nunca** construindo o C18. **Não** "ajude" implementando atalhos: a decisão de produto é **não tê-los**.

---

## 1. Objetivo

Levar a Wave 5 ao estado **GO**: **fechar todos os achados Críticos e Altos** do `AUDITORIA-WAVE-5.md` (obrigatório), tratar os **Médios** conforme decidido, e deixar a wave **re-auditável** com a suíte verde, **sem regressão** e com o **corte do C18 limpo**.

---

## 2. O que NÃO fazer (limites da remediação)

- ❌ **Não** corrija o que **não** está no relatório (salvo efeito colateral direto de uma correção — e, nesse caso, registre).
- ❌ **Não construa o C18** nem nenhuma parte dele. Achado de corte = **remoção/limpeza**.
- ❌ **Não** refatore além do necessário; **não** renomeie/reorganize por gosto.
- ❌ **Não** altere ADRs aceitos para "facilitar" uma correção sem nova decisão.
- ❌ **Não** feche um achado de integração quebrando o outro lado (dashboard ↔ relatório).

> Impulso de "já que cortei o C18, deixo um atalho só de escanear mais bonitinho" ou "já que estou aqui, melhoro X": **pare** e anote como pendência — não é desta sessão.

---

## 3. Método de remediação (por achado)

Para **cada achado**, na ordem **🔴 Críticos → 🟠 Altos → 🟡 Médios (se no escopo) → ⚪ Baixos (opcional)**:

1. **Leia a evidência** do relatório e **reproduza** o problema (rode o comando/teste/query/navegação descritos).
2. **Identifique a causa raiz.**
3. **Corrija** respeitando a §2 e os **guardrails** da §0.2.
4. **Escreva/ative o teste de regressão** que prova o fechamento.
5. **Rode a suíte inteira** — confirme zero regressão.
6. **Atualize o `AUDITORIA-WAVE-5.md`**: marque o achado como **Resolvido**, com referência ao commit/teste.

**Cuidados específicos por tipo de achado:**
- **A — Reuso/integração (C16 ↔ C17):** corrija o código compartilhado e **prove com teste que o número compartilhado bate nos dois lados** (dashboard e relatório) na mesma fixture.
- **B — Regressão nas Waves 0–4:** restaure o comportamento quebrado; o teste vermelho que a auditoria achou deve ficar **verde** sem afrouxar a asserção.
- **C — Acesso (middleware × RLS):** reconcilie a divergência; teste **403** nos endpoints **e** o **redirect + toast** (RF-021) para não-3Studio. *(Se exigir decisão de qual lado é a verdade, PARE E PERGUNTE.)*
- **D — Corte do C18:** **remova** o atalho de relatórios / a rota órfã / o import morto / o TODO; **atualize** `CHANGELOG`/`SESSION_LOG`/`README`/roadmap para marcar o C18 como **descartado** (não "pendente"); se faltar, **registre o ADR** da decisão de cortar. **Sem construir nada.**
- **E — Núcleo do C17 (se o relatório implicar métricas):** correção de métrica é provada por **recomputação independente** (fixture com resposta conhecida → cálculo à mão/script → comparação), na disciplina da auditoria dedicada do C17 — não por "ajustar até o teste passar".

---

## 4. Pontos de Decisão (quando a correção exigir)

A maioria dos achados tem correção objetiva (a recomendação do relatório basta). **Mas** se algum exigir uma decisão — ex.: **qual lado é a verdade** numa divergência middleware × RLS; o **comportamento correto** numa borda não coberta; **onde** alocar uma correção que toca a fronteira C16/C17 — **apresente em bloco** (2–3 opções + recomendação) **e aguarde**. Registre em `DECISIONS.md`.

---

## 5. Entregáveis

1. **Correções de código** — focadas, de causa raiz, dentro do escopo do relatório (incl. **remoções** referentes ao corte do C18).
2. **Testes de regressão** — **um por achado** (no mínimo para Críticos e Altos); para achados de integração, o teste **prova os dois lados**.
3. **`docs/audits/AUDITORIA-WAVE-5.md` atualizado** — cada achado com status (**Resolvido** / **Não aplicável** com justificativa / **Adiado** com decisão).
4. **ADR do corte do C18** em `DECISIONS.md` (se ainda não existia) + atualização dos docs de contexto (§9).

---

## 6. Critérios de aceitação

1. ✅ **Todos os achados Críticos e Altos** do `AUDITORIA-WAVE-5.md` estão **Resolvidos**, cada um com **teste de regressão**.
2. ✅ **Integração intacta:** o número compartilhado (ex.: "Atrasadas") **bate no dashboard e no relatório**; nenhuma correção re-quebrou o outro lado.
3. ✅ **Zero regressão** nas Waves 0–4 (suíte inteira verde).
4. ✅ **Corte do C18 limpo:** **nenhum** atalho de relatórios, **nenhuma** sobra órfã; docs marcam o C18 como **descartado**; **nada do C18 foi construído**.
5. ✅ **Acesso coerente** (middleware × RLS) — 403 + redirect/toast conforme o esperado.
6. ✅ Suíte/lint/`mypy`/build **verdes**; migrations/RLS do repo aplicam limpo (se tocadas); **sem segredos versionados**; ADRs respeitados (ou novas decisões registradas).

---

## 7. Testes desta sessão

- **Um teste de regressão por achado** Crítico/Alto (e por Médio corrigido), rastreável ao ID do achado.
- **Teste dos dois lados** para achados de integração (dashboard e relatório com o mesmo número).
- **Teste do corte do C18:** garante a **ausência** de atalho de relatórios e de rota/código órfão (ex.: um teste/checagem que falharia se o atalho reaparecesse).
- **Re-execução da suíte inteira** — fechamento **e** ausência de regressão.
- Roda **offline** (Postgres local; JWTs por perfil; fixtures relevantes).

---

## 8. Ordem de execução sugerida

1. Leia o **`AUDITORIA-WAVE-5.md`** (e o `AUDITORIA-C17.md` se o núcleo for implicado) e os ADRs/requisitos referenciados.
2. **Reproduza** os achados Críticos e Altos (linha de base).
3. Se algum achado exigir decisão, **apresente os Pontos de Decisão (§4) e aguarde**.
4. Corrija **na ordem de severidade**: causa raiz → teste de regressão (dos dois lados, quando integração) → suíte verde → atualizar o relatório. **Achados de corte → remoção/limpeza.**
5. Trate Médios (se no escopo) e Baixos (opcional).
6. Rode a **suíte inteira** uma última vez; confirme todos os critérios (§6).
7. Execute o **Protocolo de Encerramento** (§9) e **recomende a re-auditoria da Wave 5**.

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida que envolva decisão, **pare e pergunte** (§0.1/§4).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

1. **`CHANGELOG.md`** — em `[Unreleased] → Fixed`/`Removed`: as correções (referenciando os IDs dos achados) e as **remoções** do corte do C18.
2. **`DECISIONS.md`** — ADRs apenas se alguma correção exigiu **decisão** (§4); e o **ADR do corte do C18** se ainda não existia. Status *Aceita*.
3. **`SESSION_LOG.md`** — entrada: **sessão de remediação da Wave 5** dirigida pelo relatório; achados fechados (por severidade); decisões; confirmação do **corte do C18 limpo**; **próximo passo** = **re-auditar a Wave 5** (e, se GO, **W6-C19 · Camada Transversal de Animações**).
4. **`docs/audits/AUDITORIA-WAVE-5.md`** — atualizado com o status final de cada achado.
5. **`CLAUDE.md` / `README.md`** — atualize o roadmap (C18 **descartado**; Wave 5 = C17) e o que mais for estrutural.
6. **Definition of Done** (`CLAUDE.md §8`): suíte verde, integração intacta (dois lados), migrations/RLS reaplicáveis (se tocadas), sem erro de console/log crítico, sem segredos versionados, **sem regressão**, **corte do C18 limpo**.
7. **Commits semânticos** — `fix(w5-c17): <achado>`, `test(w5-c17): regressão do achado <ID>`, `chore(w5): corte do C18` / `refactor(w5): remoção de atalho`, `chore(w5-audit): status dos achados`. Árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: os achados **Críticos e Altos fechados** (com o teste que prova cada um, incl. os **dois lados** da integração), as **decisões** tomadas, a confirmação do **corte do C18 limpo**, a **suíte verde sem regressão**, e a **recomendação de re-auditoria** (com o comando exato).

---

### Lembrete final
Remediar aqui é, mais do que consertar uma tela, **garantir que o sistema seguiu coeso**. Dois erros são os mais fáceis de cometer nesta wave: **consertar o relatório e quebrar o dashboard** (ou vice-versa) — porque eles **dividem** o mesmo código de horas úteis/agregação, então todo conserto desse código precisa **provar os dois lados**; e **"resolver" um achado de corte construindo o C18** — quando a decisão é **não tê-lo**, e o conserto certo é **remover** o que sobrou. Cada correção é **blindada por um teste** para não voltar, e o relatório é atualizado para contar a verdade. Quando terminar, **mande re-auditar** — a palavra final sobre o GO é da auditoria. **Na dúvida que envolva decisão, pare e pergunte.**
