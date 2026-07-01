# Prompt de Auditoria de Fechamento — Wave 5 · Relatórios e Refinamento de UX

> **Como usar:** cole este prompt no Claude Code, no repositório com o **C17 mergeado** e os arquivos de contexto na raiz. **Escopo da Wave 5 nesta entrega:** apenas o **C17 (Relatórios)** — o **C18 (Atalhos Rápidos) foi CORTADO por decisão de produto** (não se quer o atalho de relatórios). Esta auditoria **fecha a wave**: ela **não repete** a auditoria dedicada do C17 (métrica por métrica) — ela **se apoia** nela e cobre o que falta (**integração, regressão, limpeza do corte do C18 e go/no-go da wave**).

---

## 0. Contexto e autoridade

Você é um **engenheiro de software sênior atuando como auditor adversarial independente**, agora no papel de **fechamento de wave** — verificar se a Wave 5 pode ser dada como concluída **no conjunto do sistema**.

**Leia, nesta ordem:**
1. **`docs/audits/AUDITORIA-C17.md`** — a **auditoria dedicada do C17** (a recomputação métrica por métrica). **É o insumo principal:** o veredito dela sobre a correção interna do C17 é **assumido** aqui (ver Área A). **Se esse relatório não existir ou estiver NO-GO, esta auditoria de wave é NO-GO automaticamente** — rode/feche a auditoria dedicada do C17 primeiro.
2. **`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `SESSION_LOG.md`** — o estado declarado, incl. o **corte do C18**.
3. O **código do C16** (a função de horas úteis e o padrão de agregação que o C17 **reusou**) e o **roadmap/Matriz §7**.

---

## 0.1 Princípio dominante — EXECUTAR, NÃO CONFIAR (e NÃO REPETIR)

- **Não confie** no `CHANGELOG`/`SESSION_LOG`: rode a suíte, consulte o banco, navegue o app.
- **Não repita** a recomputação métrica por métrica do C17 — isso é da auditoria dedicada (`AUDITORIA-C17.md`). Aqui o foco é **o que aquela auditoria não cobre**: a **integração** do C17 com o resto, a **regressão** nas waves anteriores, e a **limpeza do corte do C18**.
- Evidência válida = **comando + saída** / **teste + resultado** / **query + linhas** / **navegação + observação**.
- Onde faltar teste, escreva um **teste de auditoria descartável** em `audit/` (temporário) — **sem** alterar código de produção.

---

## 1. Objetivo

Emitir o **veredito Go/No-Go da Wave 5**, confirmando que: (a) o **C17 passou** na sua auditoria dedicada (insumo); (b) o C17 **integra** com as Waves 0–4 **sem regressão**; (c) o **corte do C18** está **limpo** (sem sobras, sem atalho de relatórios, docs coerentes); e (d) a qualidade transversal do repositório está verde.

---

## 2. O que NÃO fazer

- ❌ **Não corrija, não refatore, não implemente** nada no código de produção.
- ❌ **Não re-execute** a auditoria interna do C17 (métrica por métrica) — **referencie** o `AUDITORIA-C17.md`.
- ❌ **Não** commite mudanças de produção (apenas o relatório e `audit/` temporário).
- ✅ **Pode** rodar tudo, navegar o app, criar testes de auditoria descartáveis, escrever o relatório.

---

## 3. Áreas de verificação

### Área A — Incorporar o veredito da auditoria dedicada do C17
- **A1.** `docs/audits/AUDITORIA-C17.md` **existe**? Qual o **veredito** (GO/NO-GO)?
- **A2.** Se houve achados **Críticos/Altos**, eles foram **remediados** (verifique o status no relatório e, por amostragem, que a correção está no código)?
- **A3.** **Se o C17 não está GO** (relatório ausente, ou Críticos/Altos abertos) → **a Wave 5 é NO-GO**; registre e instrua a fechar a auditoria/remediação do C17 antes. *(Não prossiga fingindo que o núcleo está são.)*

### Área B — Integração e regressão (o foco real desta auditoria)
- **B1. Reuso sem dano:** o C17 **reusou** a função de horas úteis e o padrão de agregação do C16. Confirme que essas peças **continuam servindo o dashboard (C16)** corretamente (rode os testes do C16; compare um número compartilhado — ex.: "Atrasadas" — entre dashboard e relatório para a mesma fixture; devem **bater**).
- **B2. Regressão nas Waves 0–4:** **rode a suíte inteira** do repositório. Construir o C17 **quebrou** algo (auth/RBAC, domínio, movimentação, dashboard)? Liste qualquer teste vermelho.
- **B3. Migrations/RLS coerentes:** se o C17 criou função/migration, o `upgrade`/`downgrade` do **repositório inteiro** aplica limpo; a RLS continua reaplicável; nenhuma colisão com objetos anteriores.
- **B4. Acesso consistente:** "Relatórios = 3Studio" no `access-matrix` **bate** com a verificação 3Studio nos endpoints do C17 (sem divergência middleware × backend); navegar como não-3Studio redireciona com toast (RF-021) e os endpoints dão 403.
- **B5. Navegação geral:** a sidebar/rotas continuam coerentes com o C17 incluído (o item "Relatórios" aparece só para 3Studio; as demais telas seguem funcionando).

### Área C — Limpeza do corte do C18 (Atalhos Rápidos)
- **C1. Sem atalho de relatórios:** **não existe**, em lugar nenhum (dashboard ou outro), um atalho/CTA que leve a **Relatórios** (a decisão de produto é **não** tê-lo). Procure ativamente (grep por rotas/links de relatórios fora da sidebar).
- **C2. Sem sobra meio-construída:** **não há** componente/rota/arquivo do C18 **parcialmente** implementado, import morto, feature flag pendente, ou TODO referenciando "atalhos".
- **C3. Atalhos do C16 coerentes sozinhos:** os atalhos que o C16 já trouxe (ex.: **Escanear**, **Nova Prova**) **funcionam e fazem sentido** sem o C18 — cada um leva ao módulo certo, role-aware.
- **C4. Docs refletem o corte:** `CHANGELOG`/`SESSION_LOG`/`README`/roadmap marcam o **C18 como descartado/fora de escopo** — **não** como "pendente" (para não virar dívida fantasma). `DECISIONS.md` registra a **decisão de cortar** (ou recomende registrá-la).

### Área D — Coerência transversal e qualidade
- **D1.** `ruff`, `mypy --strict`, `pytest` (repo inteiro), `pnpm lint`, `build` — **todos verdes**? Cole as saídas.
- **D2.** **Sem segredos versionados**; **stateless**; sem erro de console/log crítico em uso normal das telas da Wave 5.
- **D3.** Os **5 docs de contexto** refletem a realidade pós-Wave 5 (C17 concluído, C18 cortado) — divergência é achado.
- **D4.** Animações do C17 com **`prefers-reduced-motion`**; responsivo (sanidade rápida — o detalhe é do audit dedicado).

---

## 4. Classificação de severidade

- **🔴 Crítico** — o **C17 não está GO** (núcleo não confiável); **regressão** que quebra uma wave anterior; **divergência de acesso** (middleware × RLS) que vaza ou bloqueia indevidamente; **atalho de relatórios presente** contrariando a decisão de produto. → **bloqueia o GO**.
- **🟠 Alto** — número compartilhado **diverge** entre dashboard e relatório (reuso quebrado); migration/RLS do repo não aplica limpo; **sobra meio-construída** do C18 (import morto/rota órfã); suíte vermelha em ponto não-crítico. → **bloqueia o GO**.
- **🟡 Médio** — docs desatualizados quanto ao corte do C18; navegação com aspereza menor; animação sem `prefers-reduced-motion` numa borda. → **não bloqueia**, registrar.
- **⚪ Baixo** — cosmético, dívida menor.

---

## 5. Critério de Go/No-Go da Wave 5

- **✅ GO** — (a) C17 **GO** na auditoria dedicada (ou achados remediados); (b) **zero regressão** nas Waves 0–4 e reuso do C16 intacto; (c) **corte do C18 limpo**; (d) qualidade transversal verde. **Zero** Críticos e Altos.
- **⛔ NO-GO** — qualquer Crítico ou Alto. Encaminhar: se for do C17, à **remediação do C17**; se for de integração/corte, à correção correspondente; depois **re-auditar**.

---

## 6. Entregável — o relatório

Produza **`docs/audits/AUDITORIA-WAVE-5.md`** com:

1. **Sumário executivo** — **veredito (GO/NO-GO)** no topo + contagem por severidade + **referência ao veredito do `AUDITORIA-C17.md`** (incorporado, não repetido).
2. **Achados** — por severidade, com **evidência reproduzível**, impacto e recomendação.
3. **Matriz de cobertura** das áreas A–D (PASSA/FALHA + refs).
4. **Nota sobre o C18** — registro de que foi **cortado por decisão de produto** e a confirmação de que o corte está limpo.
5. **Apêndice** — testes de auditoria criados (em `audit/`).

---

## 7. Método (ordem sugerida)

1. Abra o `AUDITORIA-C17.md` e capture o veredito (Área A). Se NO-GO/ausente → pare, registre e instrua a fechar o C17 primeiro.
2. Rode a suíte inteira + lint/mypy/build (B2/D1); cole as saídas.
3. Verifique o **reuso do C16** (B1 — número compartilhado bate) e a **coerência de acesso** (B4).
4. Faça a varredura do **corte do C18** (Área C — grep + navegação).
5. Cheque docs/qualidade transversal (Área D).
6. Classifique (§4); decida **Go/No-Go** (§5).
7. Escreva **`docs/audits/AUDITORIA-WAVE-5.md`** (§6).

---

## 8. Encerramento da auditoria

1. **Não** commite mudanças de produção. Commite **apenas** o relatório (e `audit/` temporário) — `chore(w5-audit): auditoria de fechamento da Wave 5`.
2. **`SESSION_LOG.md`** — registre: **auditoria de fechamento da Wave 5** (read-only), o **veredito**, a contagem por severidade, a confirmação do **corte do C18**, e o **próximo passo** (se GO → **W6-C19 · Camada Transversal de Animações**; se NO-GO → a correção/remediação indicada).
3. **Não** altere `CHANGELOG`/`DECISIONS` com correções. *(Exceção sugerida: se o `DECISIONS.md` ainda não registra o corte do C18, recomende — mas não implemente — esse ADR.)*
4. Ao final, **apresente um resumo** com: o **veredito da Wave 5**, como o veredito do C17 foi **incorporado**, os achados de **integração/regressão/corte** (com evidência), e a **recomendação de próximo passo**.

---

### Lembrete final
Esta auditoria fecha uma wave que, na prática, é **um componente (C17) mais uma decisão de cortar outro (C18)**. Seu valor **não** é reconferir os números do C17 — isso já foi feito a fundo; é responder três coisas que só aparecem no **nível de sistema**: o C17 **conviveu bem** com o que já existia (reuso do C16 intacto, **nada quebrou** nas waves anteriores)? O acesso a Relatórios é **coerente** entre middleware e RLS? E o **corte do C18 ficou limpo** — sem atalho de relatórios, sem sobra órfã, com os docs contando a verdade? Um GO de wave significa que o sistema **inteiro** seguiu são, não só a tela nova. **Não corrija; verifique, prove e reporte.**
