# Prompt de Auditoria — Wave 2 (Núcleo do Domínio de Provas)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz e a **Wave 2 concluída e mergeada** (C06 · Criar Prova + Etiqueta · C07 · Listagem/Filtros · C08 · Detalhe · C09 · Configurações). Esta é uma **AUDITORIA**, não uma sessão de construção. Objetivo: emitir um **parecer de prontidão (go/no-go)** para iniciar a Wave 3 (fluxo de movimentação).

---

## 0. Papel e contexto

Você é um **auditor de software sênior independente** — atue como quem **não escreveu** este código e precisa encontrar problemas antes da produção. A Wave 2 é o **núcleo do domínio**: a prova nasce aqui, ganha **código/QR/etiqueta**, **rota imutável** e a **RLS por perfil**. Falhas aqui comprometem todo o fluxo de movimentação (Wave 3) e a integridade do rastreamento.

**Leia, antes de qualquer verificação:** `CLAUDE.md` (pilares §3, arquitetura §5, DoD §8, regras §11), `DECISIONS.md` (ADRs de C06–C09 — incluindo as **reconciliações de design** registradas), `SESSION_LOG.md` (pendências/fronteiras declaradas), e o **Documento de Requisitos v1.0** (§4–§7), o **Backlog v1.0** (critérios de C06–C09 + DoD global §2) e o **DAT v1.0** (§2 schema/RLS, §7 RBAC).

---

## 0.1 Regras da auditoria (INVIOLÁVEIS)

1. **READ-ONLY / NÃO-DESTRUTIVA.** Você **NÃO** corrige, refatora ou altera **nenhum** arquivo de código, migration, RLS, config ou documento. A **única escrita permitida** é o **relatório** (§4), em `docs/audits/`. Rodar testes, linters, type-checkers, build, migrations em **banco de teste**, e **gerar uma etiqueta de exemplo para inspeção** é permitido (leituras) — **não** commite artefatos nem altere código para “fazer passar”.
2. **EXECUTAR, NÃO CONFIAR.** Rode de fato `ruff`, `mypy --strict`, lint/build, `pytest` com cobertura, os testes negativos de RLS por perfil, e **gere uma etiqueta** para inspecionar seu conteúdo. Reporte a **saída real**.
3. **BASEADO EM EVIDÊNCIA.** Todo achado cita **arquivo:linha** ou **comando/saída**, e aponta o **requisito/ADR/pilar** violado.
4. **PARE E PERGUNTE.** Se um achado for ambíguo (intencional vs. defeito), **pergunte** antes de classificar.
5. **HONESTIDADE SOBRE O VERIFICÁVEL.** Distinga o que dá para verificar **offline** (código, migrations, RLS, testes contra Postgres local com JWTs mintados, etiqueta gerada localmente) do que **exige ambiente real** (R2 real e pré-assinatura, config do template aplicada em produção, integração real com o dashboard). Marque o segundo como **“requer verificação em ambiente”**.
6. **REMEDIAÇÃO É DECISÃO SEPARADA.** Ao final, pergunte ao dono se deve gerar um **prompt de remediação**.

---

## 0.2 Antes de começar — confirme com o dono (3 itens)
1. **Escopo:** confirmo que a Wave 2 a auditar é **C06 + C07 + C08 + C09** (Waves 0–1 já auditadas/GO; Wave 3+ não construída).
2. **Ambiente:** há **staging/Supabase + R2** disponível para verificações de integração (RLS contra o banco real, pré-assinatura de arte real), ou rodo tudo contra **Postgres local** + **R2 mockado** + **JWTs de teste** por perfil?
3. **Política de veredito:** confirmo a régua da §4 (qualquer **Crítico** bloqueia a Wave 3). Deseja ajustar o limiar?

---

## 1. Escopo da auditoria

**Em escopo:** C06 (criação + código/QR/etiqueta + rota imutável + RLS de provas), C07 (listagem/pesquisa/filtros), C08 (detalhe), C09 (configurações + `system_settings`).

**Fora de escopo:** Waves 0–1 (já auditadas) e Wave 3+ (não construída). Porém **verifique as fronteiras**: C08↔C11↔C13 (movimentações/timeline corretamente adiadas — empty state, sem `movimentacoes` meio-feita), C09↔C16 (tempo de atraso só **armazenado**, cálculo é do C16), C06↔C09 (config do template **realmente** consumida pela geração).

---

## 2. Dimensões da auditoria (o que verificar)

### 2.1 Segurança e integridade do domínio (peso máximo — furos aqui são Críticos)
- **RLS de `provas` à prova de vazamento de escopo:** com JWTs por perfil, **query direta** retorna **exatamente** o escopo correto — **Vendedor só `vendedor_id` próprio**, **Motorista só estados "Com Motorista (*)"**, **3Studio/Clicheria todas**, e **perfil fora do escopo → 0 registros**. Verifique também (como na Wave 1) que o **role de conexão do backend está sujeito à RLS** (não é owner/`BYPASSRLS`; RLS habilitada; avalie `FORCE`) — senão a RLS é decorativa **mesmo com claims propagados (ADR-008)**.
- **Propagação de claims (ADR-008) ativa nas consultas de provas:** nenhum caminho serve provas **sem** a RLS (ex.: listagem/detalhe que ignorem a propagação).
- **Anti-vazamento de existência (C08):** prova **inexistente** e prova **fora do escopo** produzem o **mesmo** comportamento observável (redirect + toast), sem diferença que permita inferir existência.
- **Arte do R2 (privado):** exibida via **URL pré-assinada de curta duração** ou **proxy** — **nunca** URL pública; **a chave do R2 não aparece no cliente** (grep do bundle/env). Verifique também o **upload**: validação de **tipo e tamanho no servidor** (não só extensão; magic bytes/content-type), e **criação atômica** (sem prova/arte **órfã** em falha parcial).
- **Imutabilidade da rota no banco (C06):** **tente um `UPDATE` direto** em `rota` — deve ser **rejeitado pelo trigger** (não basta o 422 da API). Confirme também `rota_enum` **NOT NULL**.
- **Unicidade e não-reuso do código:** `codigo` tem **constraint UNIQUE** (não só dedupe na aplicação); a geração trata **colisão** (retry); o charset é **não ambíguo** (digitação manual no C10); o **QR codifica o identificador** correto.
- **Chave secreta server-only:** re-`grep` do `apps/web`/`NEXT_PUBLIC_*` por `sb_secret`/`service_role` (a Wave 1 trouxe o provisionamento; garanta que nada vazou nesta wave).
- **Configurações 3Studio em duas camadas (C09):** acesso negado a não-3Studio no **middleware** **e** na **RLS** de `system_settings` (escrita); query direta de escrita por não-3Studio **bloqueada**.

### 2.2 Conformidade com os critérios de aceitação
Verifique, item a item, os critérios do **Backlog** para **C06, C07, C08 e C09** e as histórias (**Requisitos §5**), com evidência. Em especial: criação sem rota → erro (C06); PATCH rota → 422 (C06); filtros combináveis + escopo + debounce + ≤3s (C07); detalhe ≤3s + redirect fora do escopo (C08); tempo de atraso aplicado imediatamente + acesso negado a não-3Studio (C09).

### 2.3 Etiqueta (verificação crítica — gere e inspecione)
- **Gere uma etiqueta** e **inspecione o conteúdo**: deve conter **nome, requerimento, vendedor, rota, QR Code E o código alfanumérico em destaque** (RF-003). **A ausência do código alfanumérico na etiqueta é Crítico** — quebra o fallback manual do C10. Confirme que a **rota** também aparece.
- **Tamanho físico** correto (95 × 55 mm, ou o confirmado), QR legível.
- **A configuração do template (C09)** é **de fato** respeitada pela geração (padrão vs. personalizado) — fronteira C06↔C09.

### 2.4 Domínio, migrations e enums
- Tabelas `provas` e `system_settings` criadas; colunas aditivas `finalizada_em` (C07) e `ciclo_atual` (C08) presentes e coerentes (nullable/default conforme decidido); **enums** `rota_enum`/`status_prova_enum` **sincronizados** Python↔PostgreSQL (DAT §4.5).
- **Migrations `upgrade`/`downgrade`** em banco limpo; o **trigger de imutabilidade** e as **RLS** sobrevivem/são **reaplicáveis** após recriação; **RLS versionada** em `/migrations/rls/`.
- Índices em `status`/`rota`/`vendedor_id`/`created_at` presentes (RNF-019).

### 2.5 Listagem e performance (C07)
- **Paginação server-side** com limite por página; **uso real dos índices**; **sem N+1** (conte as queries); **debounce ≥ 300 ms** (não dispara a cada tecla); **filtros combináveis**; carrega **≤ 3 s** (RNF-001); estado de filtros (URL/conforme decidido); escopo pela **RLS**, não pela UI.
- **Reuso da tabela do C04:** a tabela é o **mesmo componente** (idêntica). Se houve **extração de `<DataTable>`**, os **testes do C04 seguem verdes** (sem regressão na Wave 1 auditada).

### 2.6 Detalhe (C08)
- Anti-vazamento (2.1); arte segura (2.1); **"Baixar"/"Visualizar etiqueta"** funcionam (reuso do endpoint do C06); seção **"Histórico de movimentações"** em **empty state** (sem consultar `movimentacoes` inexistente); **"Voltar"** preserva filtros; display de **rota** reconciliado (DP-7 do C08); rótulos de status do módulo do C07.

### 2.7 Configurações (C09)
- Acesso 3Studio nas duas camadas (2.1); **imediatismo**: salvar o tempo de atraso **invalida o cache**/aplica na hora (US-016 × RNF-020); **validação por chave** (tempo de atraso inteiro > 0); RLS de `system_settings` (escrita 3Studio; leitura conforme decidido, com features compartilhadas funcionando server-side).

### 2.8 Integração e fronteiras
- A **RLS de provas usa os helpers do C05**; o **harness de equivalência** foi **estendido às células de provas** (Vendedor/Motorista/3Studio/Clicheria), testável via fixtures.
- **Módulos de rótulos** (status do C07, rota do C08) são **fonte única** (sem conjuntos paralelos/divergentes); cobrem os 14 estados/4 rotas.
- **Fronteiras limpas:** C08↔C11↔C13 (nada de `movimentacoes`/timeline meio-feitos), C09↔C16 (sem cálculo de atraso aqui), C06↔C09 (template consumido).
- **Divergências de design resolvidas e registradas** em `DECISIONS.md`/`CLAUDE.md §2.1` **e** refletidas no código: etiqueta (código+rota), "Rota direta", botões Reiniciar/Cancelar, "template personalizado".

### 2.9 Pilares de qualidade
- **Robustez:** criação **atômica** (RNF-017); **idempotência** de escrita (RNF-015); **error boundaries** + estados **loading/vazio/erro** (RNF-014/016).
- **Escalabilidade:** paginação server-side, índices, **sem N+1**, stateless.
- **Mínimo de requisições:** debounce; configurações cacheadas com TTL **+ invalidação**; consultas únicas e eficientes; pré-assinatura sem refetch redundante (RNF-020 a RNF-023).
- **Observabilidade:** log estruturado + `request_id`; sem log de erro crítico em operação normal.

### 2.10 Testes e DoD global
Rode e reporte: cobertura **≥ 80%** em domínio/serviço; **testes negativos de RLS de provas por perfil** (0 registros fora do escopo); **equivalência** estendida às células de provas; **idempotência** (RNF-015); **sem N+1**; **`prefers-reduced-motion`**; **migrations `upgrade`/`downgrade`** + **reaplicação de RLS** + **trigger de rota**. Cubra os **13 critérios da DoD global** (Backlog §2), item a item.

### 2.11 Qualidade de código e config
- `ruff`, `mypy --strict`, lint e **build** verdes (saída real). TypeScript strict sem `any`/supressões indevidas; sem código morto; sem `TODO`/`FIXME` em caminho crítico (criação/RLS/etiqueta). **Nenhum segredo versionado**; `.env.example` **completo** (chave secreta server-only, libs de QR/PDF, etc.); `.gitignore` correto.

### 2.12 Integridade dos documentos de contexto
- `CHANGELOG`/`DECISIONS`/`SESSION_LOG`/`CLAUDE`/`README` **batem com o código real** (procure **drift**). Os **ADRs esperados** de C06–C09 existem e são coerentes (modelo de `provas`, formato/charset do código, `status_prova_enum`, RLS de provas, etiqueta reconciliada, `system_settings`, template personalizado, etc.).

---

## 3. Metodologia de execução (passo a passo)

1. Ler as fontes (§0) e mapear os arquivos de C06–C09.
2. **Confirmar os 3 itens da §0.2** com o dono. Aguardar resposta.
3. **Análise estática:** `ruff`, `mypy --strict`, lint, build — registrar saída.
4. **Testes + cobertura:** `pytest` + cobertura + suíte do front — registrar números/falhas.
5. **Segurança do domínio:** testes **negativos de RLS de provas por perfil** (0 registros fora do escopo); **`UPDATE` direto em `rota`** (deve falhar pelo trigger); **grep** do bundle/env por segredo e por exposição de URL/chave do R2; inspeção do role de conexão.
6. **Etiqueta:** **gerar uma etiqueta** e **inspecionar** que contém **código alfanumérico em destaque + rota + demais campos**; verificar que a **config do template (C09)** é respeitada.
7. **Anti-vazamento (C08):** comparar o comportamento de prova inexistente vs. fora do escopo.
8. **Performance (C07):** verificar **uso de índices**, **ausência de N+1**, debounce, tempo de carga.
9. **Migrations:** `upgrade`/`downgrade` em banco limpo + **reaplicação de RLS** + persistência do **trigger**.
10. **Fronteiras e divergências:** confirmar adiamentos limpos (C08↔C11↔C13, C09↔C16) e as **resoluções registradas** (etiqueta, rota display, botões, template).
11. **Cross-check docs × código** (drift).
12. **Compilar achados**, classificar por severidade e **escrever o relatório** (§4).

---

## 4. Formato do relatório (o entregável)

Escreva em **`docs/audits/AUDITORIA-WAVE-2.md`** (única escrita permitida), com:

1. **Sumário executivo** + **VEREDITO**: **GO** ou **NO-GO** para a Wave 3, justificado em uma frase.
2. **Tabela de achados por severidade.** Para cada: `ID` · `Dimensão` (§2.x) · `Local` (arquivo:linha ou comando/saída) · `Descrição` · `Requisito/ADR/Pilar violado` · `Impacto` · **`Remediação recomendada` (NÃO aplicada)**.
   - **Rubrica de severidade:**
     - **Crítico** — **RLS de provas contornável / escopo vazando**; **arte exposta publicamente**; **vazamento de existência**; **código alfanumérico ausente na etiqueta** (quebra o C10); **código não-único**; **rota mutável no banco**; **segredo vazado**; configurações graváveis por não-3Studio; critério de aceitação quebrado. **→ Bloqueia a Wave 3.**
     - **Alto** — violação de arquitetura/DoD com risco real (ex.: cobertura abaixo do mínimo, N+1 na listagem, claims não propagados, equivalência não estendida a provas, criação não atômica).
     - **Médio** — robustez/qualidade (idempotência ausente, error boundary faltando, cache sem invalidação).
     - **Baixo / Observação** — melhorias e dívidas menores.
3. **Resultados das execuções:** saída de `ruff`/`mypy`/lint/build/`pytest`/cobertura; **matriz de cobertura das células de provas**; resultado dos testes negativos de RLS; **inspeção da etiqueta gerada**; verificação do trigger de rota.
4. **Checklist da DoD global** (os 13 critérios) — **✅ / ❌ / N-A** com evidência.
5. **Itens que requerem verificação em ambiente** (o que não deu para confirmar offline — ex.: pré-assinatura do R2 real, config aplicada em produção).
6. **Lista priorizada de remediação:** **antes** da Wave 3 (Críticos/Altos) vs. **dívida rastreada** (Médios/Baixos).

---

## 5. Encerramento da auditoria

- **NÃO** atualize os documentos de build (`CHANGELOG`/`DECISIONS`/`SESSION_LOG`/`CLAUDE`/`README`) — é auditoria. A única escrita é o relatório em `docs/audits/`.
- **NÃO** altere nem commite código-fonte. Se desejar versionar o relatório: `docs(audit): auditoria da Wave 2`.
- **Apresente no chat:** o **veredito (go/no-go)**, o **nº de achados por severidade**, e a **lista completa dos Críticos e Altos** com a remediação recomendada.
- **Pergunte ao dono** se deve **gerar um prompt de remediação** priorizado (sem aplicar nada agora).

---

### Lembrete final
A Wave 2 é onde o **dado da prova** passa a existir — e onde os furos não dão erro de tela: uma **RLS de provas que vaza** o trabalho de outro vendedor; uma **arte servida por URL pública**; um **detalhe que revela** a existência de provas fora do escopo; uma **rota que pode ser alterada** por um `UPDATE` direto; e, o mais traiçoeiro, uma **etiqueta sem o código alfanumérico** — que **parece pronta** mas **quebra o rastreamento manual do C10**. **Gere a etiqueta, rode as queries diretas, tente alterar a rota** — não acredite no código sem executar. **Na dúvida, pare e pergunte.** Um **NO-GO honesto** vale mais que um **GO** que deixa um desses passar para a Wave 3.
