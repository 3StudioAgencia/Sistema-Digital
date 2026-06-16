# Prompt de Execução — W3-C11 · Máquina de Estados (14 Estados, 4 Rotas)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–2 auditadas (GO)** e o **C10 mergeado**. Este é o **componente mais crítico do sistema** — o coração do domínio. Trabalhe a sessão inteira nele, sem pressa, com a régua de cuidado no máximo.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (**robustez/atomicidade/idempotência**, escalabilidade, mínimo de requisições, observabilidade), arquitetura §5 (Ports & Adapters — o domínio é o núcleo), gestão de schema/RLS (DAT §2), §9 (comandos), §11 (o que NÃO fazer).

**A especificação canônica é a Matriz de Transições (Requisitos v1.0, §6)** — reproduzida na íntegra na §1.2 deste prompt para referência. **Em qualquer divergência, a §6 dos Requisitos prevalece.**

**Estado atual do repositório (Waves 0–2 entregues):**
- C05: `access-matrix.ts` + middleware + `useAuthorization` + **helpers de RLS** (`is_3studio()`, `current_app_user_id()`, leitura de `setor`) + propagação de claims (ADR-008). **Reuse os helpers na RLS de `movimentacoes`.**
- C06: tabela **`provas`** com `rota` (`rota_enum`, **imutável** por trigger), `status` (`status_prova_enum`, default `'criada'`), e — se já criados — `finalizada_em`/`ciclo_atual`. **A rota é lida sempre de `prova.rota`.**
- C10: **identificação** (`POST /api/provas/identificar` / `resolver_prova()`) — a **porta de entrada** das transições. O C11 é invocado **após** a identificação.
- C07/C08/C09: listagem, detalhe (a seção "Histórico de movimentações" foi deixada em **empty state** esperando o C11/C13), configurações. **Reuse — não recrie.**

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (régua máxima)

Este é o componente onde um erro **corrompe o estado de uma prova**. Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — regra de transição, idempotência, assinatura, efeito de reprovação/cancelamento/reinício, RLS — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, **confronte a §6 reproduzida (§1.2) com a §6 do documento de Requisitos** (reporte qualquer diferença), confirme o estado das Waves 0–2 + C10 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas.
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte. **Nunca invente** uma transição, um perfil autorizado, um estado destino ou um efeito colateral.

---

## 1. Objetivo do componente

Entregar o **motor de estados autoritativo** do sistema: as **regras de transição** (a §6 inteira, como estrutura imutável em código), um **serviço de transição** que valida cada movimentação (rota + estado + perfil) antes de persistir — **atômico, idempotente** — e a **tabela `movimentacoes` imutável** (o log de auditoria das movimentações), com **RLS** por perfil. As telas que **dirigem** o motor (assinatura, cancelar, reiniciar) vêm depois (C12/C14/C15).

Referências: Backlog **C11** · Requisitos **§6 (canônica), RF-006, RF-007, RF-008, RNF-015, RNF-017** · §7 (Matriz) · C10 (identificação) · C05 (RBAC/RLS).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **Regras em código, não no banco (Backlog C11):** `transition_rules` vive em `/domain/state_machine/rules.py` como **estrutura imutável**, indexada por **`(rota, estado_atual) → lista de (ação, perfil_autorizado, estado_destino)`**. Revisável por code review, versionada em git. **Não** é tabela de banco.
2. **Validação antes de persistir:** transição **não definida** na matriz → **422**; transição por **perfil não autorizado** (mesmo com rota+estado válidos) → **403**.
3. **Roteamento sempre de `prova.rota`** — **sem inferência** por localização. O **mesmo estado** pode ter transições diferentes conforme a rota (ex.: "Aprovada pelo Vendedor" → 3Studio na Matriz, mas → Clicheria na Filial; "Laminação Concluída" → Motorista na Lam. Matriz, mas → Vendedor na Lam. Filial).
4. **Três estados distintos de "Com Motorista"** (não um só com flag): **ida laminação** (03), **volta laminação** (05), **entrega final** (12).
5. **Mecanismo invariável (§6 / RF-007):** identificar → **assinar** → confirmar → transição. A transição ocorre **somente após a assinatura digital**. *(A assinatura é o C12 — ver DP-1.)*
6. **Aprovar/Reprovar (RF-008):** nos estados em que o vendedor toma posse ("Retirada pelo Vendedor" / "Encaminhada para o Vendedor"), há **duas ações** (Aprovar → "Aprovada pelo Vendedor"; **Reprovar → "Reprovada pelo Vendedor", com motivo obrigatório**).
7. **Reprovação/Cancelamento/Reinício (§6.6):** transversais. Reprovar e Cancelar exigem **motivo**. Reiniciar Ciclo (3Studio, a partir de "Reprovada pelo Vendedor") **preserva a rota e o histórico** e volta a "Criada (novo ciclo)". Cancelar (3Studio) está disponível em **qualquer estado ativo** (≠ Cancelada, ≠ Recebida pela Clicheria) → "Cancelada".
8. **Atomicidade (RNF-017) e idempotência (RNF-015):** cada transição é **uma transação atômica**; reenvio **não duplica** movimentação nem transiciona duas vezes.
9. **Cobertura mínima 95%** nos testes unitários da máquina de estados (DoD — exigência exclusiva deste componente).

## 1.2 Matriz de Transições (§6 dos Requisitos — reproduzida; a fonte oficial prevalece em divergência)

**Inventário (14 estados):** 01 Criada (inicial, todas) · 02 Encaminhada para Laminação (Lam.Matriz, Lam.Filial) · 03 Com Motorista (ida laminação) (Lam.Matriz, Lam.Filial) · 04 Laminação Concluída (Lam.Matriz, Lam.Filial) · 05 Com Motorista (volta laminação) (Lam.Matriz) · 06 De volta à 3Studio (pós-laminação) (Lam.Matriz) · 07 Retirada pelo Vendedor (Matriz, Lam.Matriz) · 08 Encaminhada para o Vendedor (Filial, Lam.Filial) · 09 Aprovada pelo Vendedor (todas) · 10 Reprovada pelo Vendedor (todas) · 11 De volta à 3Studio (Matriz, Lam.Matriz) · 12 Com Motorista (entrega final) (Matriz, Lam.Matriz) · 13 Recebida pela Clicheria (terminal, todas) · 14 Cancelada (transversal).

**Rota Matriz:** Criada →(Vendedor)→ Retirada pelo Vendedor →(Vendedor: Aprovar)→ Aprovada pelo Vendedor →(3Studio)→ De volta à 3Studio →(Motorista)→ Com Motorista (entrega final) →(Clicheria)→ Recebida pela Clicheria.

**Rota Lam. Matriz:** Criada →(3Studio)→ Encaminhada para Laminação →(Motorista)→ Com Motorista (ida laminação) →(Clicheria)→ Laminação Concluída →(Motorista)→ Com Motorista (volta laminação) →(3Studio)→ De volta à 3Studio (pós-laminação) →(Vendedor)→ Retirada pelo Vendedor →(Vendedor: Aprovar)→ Aprovada pelo Vendedor →(3Studio)→ De volta à 3Studio →(Motorista)→ Com Motorista (entrega final) →(Clicheria)→ Recebida pela Clicheria.

**Rota Filial:** Criada →(Vendedor)→ Encaminhada para o Vendedor →(Vendedor: Aprovar)→ Aprovada pelo Vendedor →(Clicheria)→ Recebida pela Clicheria.

**Rota Lam. Filial:** Criada →(3Studio)→ Encaminhada para Laminação →(Motorista)→ Com Motorista (ida laminação) →(Clicheria)→ Laminação Concluída →(Vendedor)→ Encaminhada para o Vendedor →(Vendedor: Aprovar)→ Aprovada pelo Vendedor →(Clicheria)→ Recebida pela Clicheria.

**Transversais (todas as rotas):**
- "Retirada pelo Vendedor" (Matriz, Lam.Matriz) —(Vendedor: **Reprovar** + motivo)→ "Reprovada pelo Vendedor".
- "Encaminhada para o Vendedor" (Filial, Lam.Filial) —(Vendedor: **Reprovar** + motivo)→ "Reprovada pelo Vendedor".
- "Reprovada pelo Vendedor" —(3Studio: **Reiniciar Ciclo**; rota e histórico preservados)→ "Criada (novo ciclo)".
- Qualquer estado ativo (≠ Cancelada, ≠ Recebida pela Clicheria) —(3Studio: **Cancelar** + motivo obrigatório)→ "Cancelada".

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão (predominantemente backend/domínio)
- **`status_prova_enum`** confirmado com os **14 estados** da §6.1 (criado no C06 — **verifique a paridade exata** e ajuste/registre se necessário, com cuidado de enum em PG).
- **`transition_rules`** em `/domain/state_machine/` (estrutura imutável): **toda** a §6.2–6.6 — fluxos por rota + **Aprovar/Reprovar** + **transversais** (reprovação, reinício, cancelamento) — como dados; ações que exigem **motivo** marcadas.
- **Serviço de transição** (motor genérico): valida `(rota, estado_atual, ação, perfil_do_ator)` contra `transition_rules` → **422** se indefinida, **403** se perfil não autorizado; executa de forma **atômica**; **idempotente** (DP-2); lê a rota de `prova.rota`; **popula `finalizada_em`** em estados terminais; exige **referência de assinatura** (DP-1) e grava **motivo** quando a ação exige.
- **Tabela `movimentacoes`** (append-only, **imutável**): migration + **RLS** (helpers do C05, espelhando o escopo de provas) versionada em `/migrations/rls/`.
- **Endpoint de transição** (Ports & Adapters) — `POST /api/provas/{id}/transicao` (ou conforme DP-1) — que o fluxo de confirmação (C12) invocará; **claims propagados** (RLS); validação Pydantic; logs estruturados.
- **Documentação** (`docs/maquina-estados.md`): as regras, o motor, `movimentacoes`, idempotência/atomicidade, RLS, e as fronteiras com C12/C13/C14/C15. **Testes exaustivos** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Tela/captura de assinatura digital** (Componente **12**) — o C11 **exige uma referência** de assinatura (stub nos testes); o C12 fornece a real (DP-1).
- ❌ **Timeline visual** (Componente **13**) — o C11 **gera os dados** (`movimentacoes`); a visualização rica é do C13.
- ❌ **UI/gatilho de Cancelar** (Componente **14**) e **UI/gatilho de Reiniciar Ciclo + incremento de `ciclo_atual`** (Componente **15**) — o C11 **modela e executa** essas transições no motor; as **telas/ações** e o **incremento de `ciclo_atual`** ficam com C14/C15 (DP-4/DP-5).
- ❌ **Nova UI de transição** no C11 (DP-6) — as telas que dirigem o motor são C12/C14/C15.
- ❌ Dashboard, relatórios (Waves 4–5).

> Vontade de adiantar assinatura, timeline, telas de cancelar/reiniciar ou UI de transição: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Regras imutáveis em código** (`/domain/state_machine/rules.py`) — a única fonte de transições válidas; o motor **lê** delas. Nenhuma transição hard-coded espalhada pelo código.
2. **Validação rigorosa:** indefinida → **422**; perfil errado → **403**; rota lida de `prova.rota`; estados terminais (Recebida pela Clicheria, Cancelada) **não** têm transição de saída.
3. **Atomicidade (RNF-017):** atualizar `status` + inserir `movimentacao` (+ referência de assinatura + motivo) em **uma transação**; falha → rollback completo (sem estado inconsistente).
4. **Idempotência (RNF-015):** reenvio da mesma transição **não duplica** movimentação nem transiciona duas vezes (DP-2). Validar o estado atual **sob concorrência** (lock/versão).
5. **`movimentacoes` imutável:** **sem UPDATE/DELETE** (garantido por trigger e/ou RLS); **RLS** por perfil (helpers do C05), espelhando o escopo de provas; versionada em `/migrations/rls/`.
6. **Motivo obrigatório** quando a ação é Reprovar ou Cancelar — validado no domínio (sem motivo → rejeitado).
7. **Observabilidade:** log estruturado de cada transição (de→para, ator, ação) com `request_id`; sem log de erro crítico em operação normal.
8. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada.

### Bloco A — O motor e a persistência

**DP-1 — Fronteira da assinatura (C11↔C12) e o endpoint de transição.**
A transição só ocorre após assinatura (RF-007), mas o **C12 ainda não existe**. **[Recomendado]** o serviço de transição **requer uma referência de assinatura** (contrato), registrada em `movimentacoes`; os **testes do C11 usam um stub**; o **C12** fornece a assinatura real (sua tabela + captura) e a referência. **[Recomendado]** o **endpoint de transição vive no C11** (exigindo a ref de assinatura); o C12 captura a assinatura e o invoca. Confirmar: (a) a forma da referência em `movimentacoes` (coluna **nullable agora + FK ao `signatures` do C12 depois** vs. referência genérica); (b) o endpoint no C11 vs. no C12.

**DP-2 — Idempotência e concorrência (RNF-015).**
**[Recomendado]** validar o estado atual da prova **sob lock pessimista da linha** (`SELECT ... FOR UPDATE`) dentro da transação — se a prova já não está no estado esperado (já transicionou), a re-submissão é **no-op/rejeitada graciosamente** (a transição não é válida a partir do novo estado); opcionalmente uma **chave de idempotência** por requisição para duplo-submit antes do commit. Confirmar o mecanismo (lock pessimista vs. versão otimista vs. chave de idempotência) e a **resposta** ao reenvio (idempotente: mesmo resultado, sem erro? ou 409?).

**DP-3 — `movimentacoes` e o "log de auditoria imutável".**
**[Recomendado]** o C11 cria **`movimentacoes`** (append-only, imutável): `prova_id`, `estado_origem`, `estado_destino`, `ator` (user_id), `acao`, `motivo` (nullable), `assinatura_ref` (DP-1), `created_at`; **RLS** espelhando o escopo de provas (helpers do C05). Confirmar se o "log de auditoria imutável" do escopo do C11 **é** `movimentacoes` (recomendado) **ou** se há um **`audit_log` distinto** (o C05 o listou na RLS) — e, neste caso, quem o possui (C11 ou componente posterior).

### Bloco B — As regras e as fronteiras de efeito

**DP-4 — Abrangência das `transition_rules` (incluir as transversais?).**
**[Recomendado]** o C11 é a **máquina de estados completa e autoritativa**: `transition_rules` encoda **todas** as transições da §6.2–6.6 — fluxos por rota + reprovação + reinício + cancelamento — como dados; o motor genérico valida/executa todas. **C12 (assinatura), C14 (cancelar), C15 (reiniciar)** são **UIs/ações** que **invocam** o motor. Confirmar (vs. C14/C15 definirem transições próprias fora do motor).

**DP-5 — Efeitos especiais: quem executa (C11 vs C14/C15).**
**[Recomendado]** o C11 executa os efeitos **genéricos** (gravar `motivo` quando a ação exige; popular `finalizada_em` em estados terminais); os **gatilhos/UI** de Cancelar (C14) e Reiniciar (C15) e o **incremento de `ciclo_atual`** ficam com **C14/C15**, que **chamam o motor do C11**. Em especial: a transição "Reprovada pelo Vendedor → Criada (novo ciclo)" é **modelada** no C11 e **executada quando invocada pelo C15**, que cuida do **incremento de `ciclo_atual`** e da preservação do histórico do ciclo. Confirmar o split exato.

**DP-6 — Escopo de UI do C11.**
**[Recomendado]** o C11 é **predominantemente backend/domínio** (enum, `transition_rules`, motor, `movimentacoes`, RLS, endpoint) — **sem nova UI** de usuário. Confirmar (não construir tela de transição aqui; isso é C12/C14/C15).

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Domínio / Backend — `apps/api/`
- **`/domain/state_machine/rules.py`** — `transition_rules` imutável (a §6 inteira); estados terminais; ações que exigem motivo; helpers de consulta (`proxima(s)_transicao(es)(rota, estado)`, `transicao_valida(rota, estado, acao, perfil)`).
- **Enum** `status_prova_enum` confirmado (14 estados, paridade Python↔PostgreSQL).
- **Serviço de transição** (`executar_transicao(...)`): validação (422/403), atomicidade (RNF-017), idempotência/lock (DP-2), `finalizada_em` em terminais, exige `assinatura_ref` (DP-1), grava `motivo` quando aplicável; lê `prova.rota`.
- **Migration `movimentacoes`** (append-only, imutável) + `downgrade`; **RLS** em `migrations/rls/movimentacoes_*.sql` (helpers do C05).
- **Endpoint** `POST /api/provas/{id}/transicao` (DP-1): claims propagados, validação Pydantic, erros padronizados (422/403/409 conforme DP-2), logs estruturados.

### 5.2 Documentação — `docs/`
- `docs/maquina-estados.md`: as `transition_rules` (com a matriz), o motor (validação/atomicidade/idempotência), `movimentacoes` + RLS, e as **fronteiras** com C12 (assinatura), C13 (timeline), C14 (cancelar), C15 (reiniciar/ciclo). Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Toda transição da Matriz (§6.2–6.6) é executável**; **toda transição não definida é rejeitada (422)**.
2. ✅ **Transição por perfil não autorizado → 403**, mesmo com rota e estado válidos.
3. ✅ **Lam. Matriz percorre corretamente suas transições; Lam. Filial as suas; Matriz e Filial idem** (travessia completa de cada rota, do início ao terminal).
4. ✅ **Reprovar** (com motivo) e **Cancelar** (com motivo) funcionam; **sem motivo → rejeitado**. **Reiniciar Ciclo** volta a "Criada" preservando rota e histórico (transição modelada no C11; efeito de ciclo no C15 — DP-5).
5. ✅ **Atomicidade:** falha no meio da transição **não** deixa estado inconsistente (rollback). **Idempotência:** reenvio **não duplica** movimentação nem transiciona duas vezes (DP-2).
6. ✅ **`movimentacoes` imutável** (sem UPDATE/DELETE) com **RLS** por perfil (query direta fora do escopo → 0 registros); `finalizada_em` populado em estados terminais.
7. ✅ **Roteamento lido de `prova.rota`**; **rota imutável** após criação (re-verificado); estados terminais sem transição de saída.
8. ✅ **Cobertura ≥ 95%** nos testes da máquina de estados; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**; migration `upgrade`/`downgrade` limpa; RLS reaplicável.

---

## 7. Testes desta camada (EXAUSTIVOS — cobertura mínima 95%)

A máquina de estados exige teste **célula a célula**. Cubra, no mínimo:
- **Caminho feliz completo de cada rota:** Matriz, Lam. Matriz, Lam. Filial, Filial — **toda** transição da §6, do início ao terminal, com o **perfil correto** e a **rota correta**.
- **Toda transição não definida → 422:** para cada estado, tentar ações/destinos fora da matriz (incl. cruzar rotas: uma transição válida na Matriz não pode valer numa rota onde o estado não existe).
- **Perfil errado → 403:** para cada transição válida, tentar com **cada** perfil não autorizado (rota+estado válidos, perfil errado).
- **Ambiguidade por rota:** "Aprovada pelo Vendedor" → 3Studio (Matriz/Lam.Matriz) **vs.** Clicheria (Filial/Lam.Filial); "Laminação Concluída" → Motorista (Lam.Matriz) **vs.** Vendedor (Lam.Filial) — provar que a rota decide.
- **Aprovar/Reprovar:** nos estados de posse do vendedor, ambas as ações; **Reprovar sem motivo → rejeitado**.
- **Transversais:** Reprovação (nos dois estados aplicáveis); **Cancelar** em vários estados ativos (e **bloqueado** em terminais); **Reiniciar Ciclo** a partir de "Reprovada pelo Vendedor" (transição modelada).
- **Atomicidade:** simular falha (ex.: erro ao inserir movimentação) → **status não muda** (rollback).
- **Idempotência/concorrência:** reenvio da mesma transição e **duplo-submit concorrente** → **uma** movimentação, **uma** transição (DP-2).
- **`movimentacoes`:** imutabilidade (UPDATE/DELETE bloqueados); **RLS** por perfil (0 registros fora do escopo, via fixtures por perfil); `finalizada_em` em terminais.
- Roda **offline** (Postgres local; **assinatura stub**; JWTs de teste por perfil; provas via fixture em cada rota/estado).

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`; **confronte a §6 reproduzida (§1.2) com a §6 dos Requisitos** e reporte diferenças; confirme Waves 0–2 + C10 (identificação) e os helpers de RLS do C05.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. `transition_rules` em `/domain/state_machine/` (a §6 inteira) + enum confirmado; testes unitários **puros** das regras (sem banco) — todas as transições válidas/inválidas/perfis.
4. Migration `movimentacoes` (imutável) + RLS (helpers do C05); testes de RLS/imutabilidade.
5. Serviço de transição (validação 422/403, atomicidade, idempotência/lock — DP-2, `finalizada_em`, motivo, `assinatura_ref` stub); testes de integração exaustivos (§7).
6. Endpoint de transição (DP-1); testes (claims propagados, 422/403/409).
7. `docs/maquina-estados.md`.
8. Verifique **todos** os critérios de aceitação (§6) **e a cobertura ≥ 95%** e a sub-checklist da DoD (§9).
9. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: máquina de estados (14 estados, 4 rotas); `transition_rules`; serviço de transição (atômico/idempotente); tabela `movimentacoes` imutável + RLS; endpoint de transição.
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **fronteira da assinatura** + endpoint (DP-1); (b) **idempotência/concorrência** (DP-2); (c) **`movimentacoes` vs. `audit_log`** (DP-3); (d) **abrangência das `transition_rules`** (DP-4); (e) **split de efeitos C11/C14/C15** (DP-5). Status *Aceita* onde aplicável.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, **cobertura da máquina de estados (≥ 95%)** e testes, **pendências** (assinatura real = C12; timeline = C13; UI cancelar/reiniciar + `ciclo_atual` = C14/C15) e **próximo passo** = **W3-C12 · Assinatura Digital no Fluxo de Escaneamento**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre o **modelo da máquina de estados** (onde vivem as regras), `movimentacoes`, o **contrato do endpoint de transição** e as **fronteiras**. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap (C11 concluído).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): **cobertura ≥ 95% na máquina de estados**, testes de **acesso não autorizado por perfil** (403) e de **RLS de `movimentacoes`**, **atomicidade** e **idempotência** (RNF-015/017), migration + RLS versionadas/documentadas, sem erro de console/log crítico, docs do módulo, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w3-c11): ...`, `chore(w3-c11): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. a travessia completa das quatro rotas, as rejeições 422/403, a atomicidade e a idempotência, e a **cobertura ≥ 95%**), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W3-C12**).

---

### Lembrete final
Este é o **coração do sistema** — onde um erro não dá tela vermelha, mas **corrompe silenciosamente o estado de uma prova**: uma transição que não deveria existir e existe; um perfil que transiciona o que não pode; um reenvio que move a prova duas vezes; uma falha no meio que deixa o status mentindo. Por isso: **regras em código (a §6, fonte única)**, **validação 422/403**, **transação atômica**, **idempotência sob lock**, **`movimentacoes` imutável**. E mantenha o **escopo enxuto**: o C11 é o **motor** — quem **assina** é o C12, quem desenha a **timeline** é o C13, quem **cancela/reinicia** (e mexe no `ciclo_atual`) são C14/C15; todos **chamam** este motor. Teste **célula a célula** até os **95%**. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível — aqui, mais do que em qualquer outro componente.
