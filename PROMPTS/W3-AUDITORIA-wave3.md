# Prompt de Auditoria — Wave 3 · Movimentação (C10–C15)

> **Como usar:** cole este prompt no Claude Code, no repositório com a **Wave 3 inteira mergeada** (C10 escaneamento, C11 máquina de estados, C12 assinatura, C13 timeline, C14 cancelamento, C15 reinício de ciclo) e os arquivos de contexto na raiz. Esta é uma sessão de **auditoria read-only** — você **não corrige nada** aqui, apenas verifica e reporta. Wave 3 é a wave que toca o **estado das provas**: audite com rigor proporcional.

---

## 0. Contexto e autoridade

Você é um **engenheiro de software sênior atuando como auditor adversarial independente**. Sua missão **não** é elogiar o que foi feito nem confirmar que está pronto — é **encontrar onde quebra**. Assuma que há defeitos até provar empiricamente o contrário.

**Leia `CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md` e `SESSION_LOG.md`** para entender o que foi *declarado*. Em seguida, **leia os requisitos** (`RequisitosProvasDigitais_v1_0.docx` §6 e §7, RF/RN/RNF citados) — a **fonte da verdade do comportamento esperado** é o requisito, não o que os docs do repo afirmam.

---

## 0.1 Princípio dominante — EXECUTAR, NÃO CONFIAR

**Documentação mente; código e dados, não.** Para cada item desta auditoria:
- **Não** aceite o `CHANGELOG`, o `SESSION_LOG`, comentários ou nomes de teste como prova. **Rode** o código, **execute** os testes, **consulte** o banco, **tente** os ataques.
- Se um critério diz "X é atômico", **provoque uma falha no meio** e verifique o rollback. Se diz "anti-enumeração", **mande os dois casos** e **compare as respostas**. Se diz "só 3Studio", **chame o endpoint como Vendedor** e veja o que acontece.
- Evidência válida = **comando + saída**, **teste + resultado**, ou **query + linhas**. Afirmação sem evidência reproduzível **não conta**.
- Onde o teste necessário não existe, **escreva um teste de auditoria descartável** (em uma pasta `audit/` separada, claramente temporária) para produzir a evidência — mas **não** altere o código de produção.

---

## 0.2 Postura

- **Adversarial:** seu trabalho é quebrar o sistema, não validá-lo. Procure o caminho que o desenvolvedor não testou.
- **Cético com os docs:** divergência entre o que o `DECISIONS.md` diz e o que o código faz é, por si só, um achado.
- **Específico:** todo achado aponta arquivo/linha/endpoint/migration e traz o passo para reproduzir.

---

## 1. Objetivo

Determinar, com evidência empírica, se a **Wave 3 está sólida o suficiente para seguir** — ou seja, se o **estado das provas é íntegro, consistente e inviolável** sob o comportamento especificado (§6, §7, RF/RN/RNF), e emitir um **veredito Go/No-Go** com um **relatório de achados classificados por severidade**.

---

## 2. O que NÃO fazer (limites da auditoria)

- ❌ **Não corrija, não refatore, não implemente** nada no código de produção. Achou um bug? **Registre-o** — a correção é da sessão de **remediação**.
- ❌ **Não altere** migrations, RLS, regras de transição, componentes.
- ❌ **Não faça** commit de mudanças de produção. (Pode commitar **apenas** o relatório de auditoria e, se quiser, a pasta `audit/` de testes descartáveis, claramente marcada.)
- ✅ **Pode** rodar tudo (testes, lint, build, servidor local), criar testes de auditoria temporários, consultar o banco, e escrever o relatório.

> Se durante a auditoria você sentir o impulso de "consertar rapidinho", **pare** — anote o achado e siga. Misturar auditoria com correção contamina o veredito.

---

## 3. Áreas de verificação (o núcleo)

Para cada área, **execute** as verificações e **registre** o resultado (PASSA / FALHA + evidência). As áreas A–C são as mais críticas desta wave.

### Área A — Integridade do motor de transição (C11)
- **A1.** As `transition_rules` implementam **exatamente** a §6? Para **cada uma das 4 rotas**, percorra o caminho canônico ponta a ponta (Criada → terminal) **executando** as transições; confirme que cada passo só avança com o **perfil correto** e produz o **estado correto**.
- **A2.** **Nenhuma transição inválida** é aceita: para amostras de (rota, estado), tente ações **não previstas** na §6 → devem ser **rejeitadas (422)**.
- **A3.** **Estados terminais** ("Recebida pela Clicheria", "Cancelada") **não têm saída**: tente transicionar a partir deles → rejeitado.
- **A4.** As regras vivem **em código imutável** (não no banco)? Confirme onde estão e que não há tabela de regras editável.
- **A5.** O motor distingue **403 (perfil errado)** de **422 (transição indefinida)** corretamente?

### Área B — Nenhum caminho de status fora do motor (a regra de ouro)
- **B1.** **Grep/inspeção** em todo o backend: existe **algum** `UPDATE` em `provas.status` (ou equivalente do ORM) **fora** do serviço de transição do C11? Liste cada ocorrência.
- **B2.** C12 (assinatura), C14 (cancelar), C15 (reiniciar) **invocam o motor**? Confirme no código que **nenhum** deles altera o status por um segundo caminho.
- **B3.** Existe **algum endpoint/rota** que mude o estado de uma prova sem passar pela validação do motor? Tente encontrá-lo e exercitá-lo.

### Área C — Atomicidade, idempotência e concorrência
- **C1. C12 (assinatura + movimentação):** injete uma **falha** entre gravar a assinatura e a movimentação → verifique **rollback total** (sem assinatura órfã, sem movimentação sem assinatura).
- **C2. C15 (transição + incremento de ciclo):** force falha no meio → `status` e `ciclo_atual` **não** mudam (rollback). No sucesso, **ambos** mudam juntos.
- **C3. Idempotência:** **reenvie** a mesma transição (mesma chave/sob lock) → **não** duplica movimentação nem incrementa ciclo duas vezes.
- **C4. Concorrência:** dispare **duas transições concorrentes** na mesma prova → o estado **não** corrompe (uma vence, a outra é rejeitada/ignorada coerentemente).

### Área D — Anti-enumeração (C10 escaneamento + C12 assinatura)
- **D1.** **Código inválido** vs. **código válido-mas-fora-de-escopo** → **a mesma resposta genérica** (status + corpo). Compare as duas respostas; qualquer diferença que revele existência é achado.
- **D2.** **Ator não autorizado** para a próxima transição → mensagem genérica, **sem revelar** quem é o próximo ator. Verifique o texto e o payload.
- **D3.** **Rate limit** no identificar (se especificado — C10 citou ~30/min): existe e funciona?
- **D4.** As respostas vazam por **timing** (latência mensuravelmente diferente entre existe/não-existe)? Registre se observável.

### Área E — Consistência de ciclo (C13 timeline + C15 reinício)
- **E1.** Cada `movimentacao` carrega o **`ciclo`** correto (carimbado no insert)? Verifique o schema **e** os dados.
- **E2.** Após um **reinício**: as movimentações do ciclo anterior ficam atribuídas ao **ciclo antigo** e as novas ao **novo**? (Crie uma prova, reprove, reinicie, mova; inspecione os ciclos.)
- **E3.** O **histórico do ciclo anterior é preservado** (não apagado) após o reinício? (RN-006)
- **E4.** A **timeline (C13)** agrupa por ciclo corretamente e **separa** os ciclos? O **caminho canônico deriva das regras do C11** (não é uma cópia da §6 que pode divergir)? Force uma divergência hipotética e veja se há teste que a pegaria.

### Área F — RLS e acesso (movimentacoes, assinaturas, ações administrativas)
- **F1.** **RLS em `movimentacoes` e `assinaturas`**: com JWTs por perfil, tente ler fora do escopo (Vendedor vê só as suas; Motorista só "Em Trânsito"; etc.) → **0 registros** fora do escopo.
- **F2. Risco nº1 do projeto:** o role conectado **não** tem `BYPASSRLS` e as tabelas têm **`FORCE ROW LEVEL SECURITY`** onde necessário (a RLS **não** é decorativa)? Verifique no banco.
- **F3. Cancelar/Reiniciar (3Studio-only em duas camadas):** chame os endpoints **diretamente como Vendedor/Motorista/Clicheria** → **403** (não basta esconder o botão no front).
- **F4.** Os claims (`setor`, `user_id`) chegam ao Postgres e a RLS os usa de fato? (Não confie no hook — verifique uma query real.)

### Área G — Ações administrativas e regras de assinatura
- **G1. Cancelar (C14):** motivo **obrigatório** (sem motivo → bloqueado); **sem** assinatura (§6.6); **irreversível** (Cancelada terminal — RN-005); disponível **só** em estados ativos (≠ Cancelada, ≠ Recebida).
- **G2. Reiniciar (C15):** **só** em "Reprovada pelo Vendedor"; **sem** motivo e **sem** assinatura (só confirmação); **rota preservada**; **mesma prova** (mesmo código).
- **G3. Reprovar (fluxo de assinatura):** **EXIGE** motivo **+ assinatura** (contraste deliberado com cancelar/reiniciar). Confirme que reprovar sem assinatura/motivo é bloqueado.

### Área H — Assinatura (C12) e resiliência
- **H1.** A assinatura desenhada é capturada e **armazenada** conforme o ADR (tabela/R2); se R2, **sem URL pública** (apenas pré-assinada). Verifique.
- **H2. Resiliência (RNF-016):** simule **falha de submissão** → o **traço** e a **ação** persistem localmente + **retry** funciona (a assinatura **não** se perde).
- **H3.** Fluxo **identificar → assinar → confirmar em ≤ 3 toques** (RNF-009)? Conte os toques no caminho feliz.

### Área I — Qualidade transversal
- **I1.** `ruff`, `mypy --strict`, `pytest` (com **cobertura** — o C11 exigiu **≥ 95%** no motor), `pnpm lint`, `build` — **todos verdes**? Cole as saídas.
- **I2.** Migrations `upgrade`/`downgrade` **limpas**; RLS **reaplicável** sem erro.
- **I3.** Animações **GPU-only** + **`prefers-reduced-motion`** (timeline C13, modais C14/C15).
- **I4.** **Sem segredos versionados**; **stateless**; **sem** erro de console/log crítico em uso normal.
- **I5.** Os 5 docs de contexto **refletem a realidade** do código? (Divergência = achado — lembre: executar, não confiar.)

---

## 4. Classificação de severidade

Classifique **cada achado**:

- **🔴 Crítico** — corrompe ou pode corromper o **estado de uma prova**; permite **caminho de status fora do motor**; **vaza dados** (RLS furada, anti-enumeração quebrada, `BYPASSRLS`); perda de atomicidade que deixa **estado inconsistente**. → **bloqueia o GO**.
- **🟠 Alto** — viola um **Must** (RF/RN) de forma observável; **idempotência quebrada** (duplica movimentação/ciclo); ação administrativa **sem a segunda camada** de acesso; **assinatura perdida** em falha; transição inválida aceita. → **bloqueia o GO**.
- **🟡 Médio** — comportamento divergente que **não** corrompe estado nem vaza dados (rótulo/estado mal mapeado em caso raro, timeline com ciclo mal agrupado em borda, animação sem `prefers-reduced-motion`). → **não bloqueia**, registrar.
- **⚪ Baixo** — cosmético, dívida técnica menor, teste ausente não-crítico.

---

## 5. Critério de Go/No-Go

- **✅ GO** — **zero** achados Críticos **e** zero Altos. (Médios/Baixos registrados como dívida.)
- **⛔ NO-GO** — **qualquer** achado Crítico **ou** Alto. Encaminhar para a sessão de **remediação da Wave 3** (que será dirigida por este relatório), e **re-auditar** depois.

Seja honesto: um **NO-GO bem fundamentado é mais valioso** que um GO complacente. Esta wave guarda o estado das provas — não deixe passar.

---

## 6. Entregável — o relatório

Produza **`docs/audits/AUDITORIA-WAVE-3.md`** com:

1. **Sumário executivo** — o **veredito (GO/NO-GO)** logo no topo, com a contagem de achados por severidade.
2. **Achados** — agrupados por severidade (Críticos primeiro). Cada achado: **ID**, **área** (A–I), **título**, **descrição**, **evidência reproduzível** (comando/teste/query + saída), **impacto**, **recomendação de correção** (para a remediação).
3. **Matriz de cobertura** — tabela das áreas A–I com PASSA/FALHA e referência aos achados.
4. **Apêndice** — lista dos **testes de auditoria descartáveis** criados (caminho em `audit/`) e como rodá-los.

O relatório é para um **leitor técnico** que vai decidir o próximo passo — direto, com evidência, sem floreio.

---

## 7. Método (ordem sugerida)

1. Leia os docs do repo (o *declarado*) e os requisitos (§6, §7 — o *esperado*).
2. Rode a suíte e o lint/build (I1) para a linha de base; cole as saídas.
3. Ataque as áreas na ordem **A → B → C** (as mais críticas), depois **D → E → F → G → H → I**.
4. Para cada verificação, produza **evidência** (executar, não confiar); onde faltar teste, escreva o teste de auditoria descartável em `audit/`.
5. Classifique cada achado (§4).
6. Decida **Go/No-Go** (§5).
7. Escreva **`docs/audits/AUDITORIA-WAVE-3.md`** (§6).

---

## 8. Encerramento da auditoria

1. **Não** commite mudanças de produção. Commite **apenas** o relatório (e, opcionalmente, `audit/` marcado como temporário) — `chore(w3-audit): relatório de auditoria da Wave 3`.
2. **`SESSION_LOG.md`** — registre: que foi uma **sessão de auditoria** (read-only), o **veredito (GO/NO-GO)**, a contagem de achados por severidade, e o **próximo passo** (se NO-GO → **remediação da Wave 3**; se GO → **W5-C17**).
3. **Não** altere `CHANGELOG.md`/`DECISIONS.md` com correções (não houve correção).
4. Ao final, **apresente um resumo** com: o **veredito**, os achados **Críticos e Altos** (se houver) com sua evidência, a matriz de cobertura, e a **recomendação de próximo passo**.

---

### Lembrete final
Você é a última linha antes do estado das provas virar dado de produção. O desenvolvedor desta wave fez o melhor que pôde — seu trabalho é **diferente**: encontrar o que ele não viu. Duas perguntas guiam tudo: **"o estado de uma prova pode ser corrompido ou contornar o motor?"** e **"um usuário pode ver ou mover o que não deveria?"**. Se a resposta for "talvez", **prove** — executando, não confiando. Um relatório honesto, com evidência reproduzível e um veredito claro, é o entregável. **Não corrija; reporte.**
