# Prompt de Auditoria — Wave 1 (Autenticação e Controle de Acesso)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz e a **Wave 1 concluída e mergeada** (C03 · Login/Sessão · C04 · Usuários + App Shell · C05 · RBAC). Esta é uma **AUDITORIA**, não uma sessão de construção. O objetivo é emitir um **parecer de prontidão (go/no-go)** para iniciar a Wave 2.

---

## 0. Papel e contexto

Você é um **auditor de software sênior independente** — atue com a postura de quem **não escreveu** este código e precisa encontrar problemas antes que eles cheguem à produção. Wave 1 é a **espinha de segurança** do sistema (autenticação + RBAC em duas camadas); falhas aqui comprometem tudo que vem depois.

**Leia, antes de qualquer verificação:** `CLAUDE.md` (autoridade do projeto, pilares §3, arquitetura §5, DoD §8, regras §11), `DECISIONS.md` (todos os ADRs do C03/C04/C05), `SESSION_LOG.md` (o que foi feito e as pendências declaradas), e o **Documento de Requisitos v1.0** (§5 histórias, §7 Matriz de Acesso), o **Backlog v1.0** (critérios de aceitação de C03/C04/C05 e a Definition of Done global) e o **DAT v1.0** (§1.3 separação de auth, §2 schema/RLS, §7 RBAC).

---

## 0.1 Regras da auditoria (INVIOLÁVEIS)

1. **READ-ONLY / NÃO-DESTRUTIVA.** Você **NÃO** corrige, refatora, renomeia, “melhora” ou altera **nenhum** arquivo de código, migration, política RLS, configuração ou documento de contexto. A **única escrita permitida** é o **relatório de auditoria** (§4), em `docs/audits/`. Rodar testes, linters, type-checkers, build e migrations em **banco de teste local** é permitido (são leituras do ponto de vista do código-fonte) — mas **não** commite artefatos nem altere o código para “fazer passar”.
2. **EXECUTAR, NÃO CONFIAR.** Rode de fato `ruff`, `mypy --strict`, o lint/build do front, `pytest` com cobertura, e os testes negativos de RLS/Matriz. Reporte a **saída real**. Não escreva “deve passar” — verifique.
3. **BASEADO EM EVIDÊNCIA.** Todo achado cita **arquivo:linha** ou **comando + saída**, e aponta o **requisito/ADR/pilar** violado. Nada de achado especulativo sem evidência.
4. **PARE E PERGUNTE.** Se um achado for ambíguo (comportamento **intencional** vs. **defeito**), **pergunte ao dono** antes de classificá-lo. Não invente o que “deveria” ser.
5. **HONESTIDADE SOBRE O VERIFICÁVEL.** Distinga o que dá para verificar **offline** (código, migrations, arquivos de RLS, testes contra Postgres local com JWTs mintados) do que **exige ambiente real** (configuração do Custom Access Token Hook no dashboard, assinatura real ES256 do projeto, RLS contra o banco do Supabase). O que exigir ambiente real deve ser marcado como **“requer verificação em ambiente”** — não aprove nem reprove no escuro.
6. **REMEDIAÇÃO É DECISÃO SEPARADA.** A auditoria **propõe** correções, não as aplica. Ao final, pergunte ao dono se deve gerar um **prompt de remediação** com base nos achados.

---

## 0.2 Antes de começar — confirme com o dono (3 itens)
1. **Escopo:** confirmo que a Wave 1 a auditar é **C03 + C04 + C05** (Wave 0 está em produção e fora de escopo; Wave 2+ não foi construída).
2. **Ambiente:** há **staging/ambiente Supabase** disponível para as verificações de integração/RLS contra o banco real, ou rodo tudo contra **Postgres local** (docker-compose) com **JWTs de teste mintados** por perfil?
3. **Política de veredito:** confirmo a régua de go/no-go da §4 (qualquer achado **Crítico** bloqueia a Wave 2). Deseja ajustar o limiar?

---

## 1. Escopo da auditoria

**Em escopo:** C03 (Login e Sessão), C04 (Cadastro/Gestão de Usuários + App Shell), C05 (RBAC — Matriz em duas camadas), e a **fronteira C05↔C06** (verificar que os helpers de RLS existem e estão prontos, e que a RLS de `provas` foi **corretamente adiada**, não meio-feita).

**Fora de escopo:** Wave 0 (infra/keep-alive, já em produção) e qualquer item de Wave 2+ ainda não construído.

---

## 2. Dimensões da auditoria (o que verificar)

### 2.1 Segurança (peso máximo — qualquer furo aqui é Crítico)
- **Chave secreta/service-role vazada:** faça `grep`/busca em **todo o `apps/web`** (código e build) e em todas as variáveis `NEXT_PUBLIC_*` por `sb_secret`, `service_role`, ou a connection string privilegiada. A chave secreta deve existir **apenas no backend**. **Qualquer ocorrência no cliente é Crítico.**
- **Caminhos que ignoram a RLS:** verifique se há **leitura direta de dados de domínio** (`usuarios`) pelo client Supabase no browser com chave privilegiada, ou qualquer endpoint que sirva dado de domínio **sem** propagação de claims (ADR-008). Dado de domínio deve passar pelo backend, com a RLS ativa.
- **Papel de banco sujeito à RLS:** confirme que o **role com que o backend consulta** está **sujeito à RLS** (não é o owner da tabela nem tem `BYPASSRLS`); que as tabelas têm **RLS habilitada**; e avalie se `FORCE ROW LEVEL SECURITY` é necessário (o owner ignora RLS sem `FORCE`). Sem isso, a RLS é decorativa mesmo com claims propagados.
- **Verificação de JWT (C03):** suporta **ES256 (JWKS) + HS256**; valida **`aud="authenticated"`** e **expiração**; **nenhum** `verify_signature=False`, `alg: none` aceito, ou `options` que desliguem validação; o backend **nunca emite** token.
- **Custom Access Token Hook (C05):** injeta `setor` e `user_id` **na posição que a RLS lê** (`auth.jwt() ->> '...'`); tem `grant execute ... to supabase_auth_admin` + `grant usage on schema public`; **revoga** de `anon/authenticated/public`; o `supabase_auth_admin` tem o grant necessário para ler `usuarios`; o hook preserva os claims obrigatórios e não quebra a emissão.
- **Defesa em profundidade / equivalência:** o **middleware** bloqueia a página **e** a **RLS** bloqueia o dado; existe o **teste de equivalência** `access-matrix.ts ↔ RLS` (o **risco nº1** do projeto); para cada `○` da Matriz, query direta retorna **0 registros**.
- **Login (C03):** erro de credencial **genérico** (anti-enumeração — não revela qual campo falhou); cookies **HTTP-only**; **inatividade de 30 min** encerra a sessão; proteção via **`getUser()`** (não `getSession()`); respostas com `Set-Cookie` **não cacheadas** (CDN/Vercel).
- **Usuários (C04):** **desativação bloqueia o login** (ban via Admin API, não só `ativo=false`); **RN-010** (admin não se autodesativa; só admin gerencia admin); **política de senha** (min 8, letra+número) validada **front e back**; **provisionamento coordenado** (sem auth user **órfão** em falha parcial).

### 2.2 Conformidade com os critérios de aceitação
Verifique, item a item, os critérios de aceitação do **Backlog** para **C03, C04 e C05** e as histórias vinculadas (**Requisitos §5**). Marque cada critério como atendido/não atendido **com evidência**.

### 2.3 Matriz de Acesso (RBAC)
- **`access-matrix.ts` == Requisitos §7**, reconciliado com a decisão da **DP-1 do C04** (modelo Setor × Administrador registrado em `DECISIONS.md`/`CLAUDE.md §2.1`). **Inconsistência entre o modelo decidido e o implementado (schema, matriz, claims do hook) é Crítico.**
- **100% das células** ●/◐/○ cobertas por **teste**; **sidebar filtrada por perfil**; acesso não autorizado **redireciona para a home do perfil com toast**; **acesso direto por URL** a página não autorizada é bloqueado.

### 2.4 Arquitetura e conformidade
- **Ports & Adapters:** regra de dependência respeitada (o domínio **não** importa adapters/infra); camadas conforme `CLAUDE.md §5`.
- **ADR-007:** runtime via **pooler 6543** (NullPool); migrations via conexão **direta 5432**. **ADR-008:** propagação de claims implementada como decidido.
- **Versionamento de RLS (DAT §2):** toda política existe como `.sql` em `/migrations/rls/`; nada criado só pelo painel; **reaplicável** após recriação de tabela. Enums sincronizados Python↔PostgreSQL.

### 2.5 Integração e consistência C03 → C04 → C05
- O **`middleware.ts`** combina coerentemente **refresh (C03)** + **enforcement (C05)**.
- O **`app_metadata`** gravado no C04 é **consumido** pelo hook do C05 (ou a fonte de claims escolhida está coerente).
- A **RLS provisória** de `usuarios` (C04) foi **efetivamente substituída** pela definitiva (C05) — não há duas posturas conflitantes.
- **Sistema de toasts** e **fundação de motion** **reutilizados** (sem duplicação/divergência entre C03/C04).

### 2.6 Pilares de qualidade
- **Robustez:** transações **atômicas** (RNF-017), **idempotência** (RNF-015), **error boundaries** por rota + caminho de recuperação (RNF-014/016), degradação graciosa.
- **Escalabilidade:** listagem de usuários **paginada server-side**, **índices** nas colunas de filtro/ordenação, backend **stateless**, **sem N+1**.
- **Mínimo de requisições:** busca com **debounce**; middleware usando **`getClaims()`** (verificação local, sem bater no auth server por request); sem refetch desnecessário.
- **Observabilidade:** **log estruturado** + `request_id`; captura de erro; sem log de erro crítico em operação normal.

### 2.7 Testes e DoD global
Rode e reporte: cobertura **≥ 80%** nas camadas de **domínio e serviço** do backend; **testes de tentativa de acesso não autorizado por perfil** (DoD §6 do backlog); **testes diretos de RLS** (0 registros fora do escopo); **equivalência** middleware↔RLS; **`prefers-reduced-motion`** (degradação instantânea); **idempotência** de escrita; **migrations `upgrade`/`downgrade`** em banco limpo + **reaplicação de RLS**; **sem erros no console** do browser.

### 2.8 Qualidade de código e config
- `ruff`, `mypy --strict`, lint e **build** do front **verdes** (reporte a saída).
- **TypeScript strict** sem `any`/`@ts-ignore`/supressões indevidas; sem código morto; **sem `TODO`/`FIXME`** em caminho crítico de auth/RBAC.
- **Nenhum segredo versionado**; `.env.example` **completo e coerente** (inclui as variáveis de auth/JWKS/secret, marcadas server-only onde aplicável); `.gitignore` correto.

### 2.9 Integridade dos documentos de contexto
- `CHANGELOG.md`, `DECISIONS.md`, `SESSION_LOG.md`, `CLAUDE.md` e `README.md` **batem com o código real** (procure **drift**: doc que afirma algo que o código não faz, ou vice-versa).
- Os **ADRs esperados** existem e são coerentes: arquitetura de auth/`@supabase/ssr`, **verificação ES256/JWKS + HS256** (com a **correção da premissa antiga HS256** do DAT/C01), Custom Access Token Hook, propagação de claims (ADR-008), RLS definitiva de `usuarios`, **modelo Setor × Administrador (DP-1)**, e a **fronteira C05↔C06**.

### 2.10 Fronteira C05 → C06
- Os **helpers de RLS** (`is_3studio()`, `current_app_user_id()`, leitura de `setor`) **existem e estão prontos** para o C06.
- A **RLS de `provas` foi corretamente adiada** (não há políticas de `provas` meio-implementadas); a **pendência** registrada no `SESSION_LOG.md` é **precisa**.

---

## 3. Metodologia de execução (passo a passo)

1. Ler as fontes (§0) e mapear os arquivos de C03/C04/C05 no repositório.
2. **Confirmar os 3 itens da §0.2** com o dono. Aguardar resposta.
3. **Análise estática:** rodar `ruff`, `mypy --strict`, lint e build; registrar a saída.
4. **Testes + cobertura:** rodar `pytest` com cobertura e a suíte do front; registrar números e falhas.
5. **Segurança:** grep do bundle/env por segredo; inspeção do código de verificação de JWT, do hook, das políticas RLS e do role de conexão; verificação dos caminhos que tocam dado de domínio.
6. **Testes negativos por perfil:** para cada perfil, validar acesso de página (middleware) **e** de dado (RLS → 0 registros fora do escopo); rodar/inspecionar o **harness de equivalência**.
7. **Regra de dependência** (hexagonal) e **conformidade de ADRs** (007/008, versionamento de RLS, enums).
8. **Migrations:** `upgrade`/`downgrade` em banco de teste limpo + **reaplicação das RLS** a partir de `/migrations/rls/`.
9. **Cross-check docs × código** (drift).
10. **Compilar achados**, classificar por severidade e **escrever o relatório** (§4).

---

## 4. Formato do relatório (o entregável)

Escreva o relatório em **`docs/audits/AUDITORIA-WAVE-1.md`** (essa é a única escrita permitida), com:

1. **Sumário executivo** + **VEREDITO**: **GO** ou **NO-GO** para a Wave 2, em uma frase, justificado.
2. **Tabela de achados por severidade.** Para cada achado: `ID` · `Dimensão` (§2.x) · `Local` (arquivo:linha ou comando+saída) · `Descrição` · `Requisito/ADR/Pilar violado` · `Impacto` · **`Remediação recomendada` (NÃO aplicada)**.
   - **Rubrica de severidade:**
     - **Crítico** — furo de segurança, **exposição/vazamento de dado ou segredo**, **RLS ausente/contornável**, critério de aceitação quebrado, inconsistência do modelo de acesso (DP-1) entre schema/matriz/claims. **→ Bloqueia a Wave 2.**
     - **Alto** — violação de arquitetura ou de DoD com risco real (ex.: cobertura abaixo do mínimo, propagação de claims frágil, ausência de teste de equivalência).
     - **Médio** — robustez/qualidade (idempotência ausente, N+1, error boundary faltando).
     - **Baixo / Observação** — melhorias e dívidas menores.
3. **Resultados das execuções:** saída resumida de `ruff`/`mypy`/lint/build/`pytest`/cobertura; **matriz de cobertura das células** da Matriz de Acesso; resultado dos testes negativos de RLS.
4. **Checklist da DoD global** (os 13 critérios do Backlog §2) — item a item, **✅ / ❌ / N-A**, com evidência.
5. **Itens que requerem verificação em ambiente** (o que não deu para confirmar offline).
6. **Lista priorizada de remediação:** o que **precisa** ser corrigido **antes** da Wave 2 (Críticos/Altos) vs. o que pode seguir como **dívida rastreada** (Médios/Baixos).

---

## 5. Encerramento da auditoria

- **NÃO** atualize os documentos de build (`CHANGELOG`/`DECISIONS`/`SESSION_LOG`/`CLAUDE`/`README`) — isto é auditoria, não componente. A única escrita é o relatório em `docs/audits/`.
- **NÃO** altere nem commite código-fonte. Se desejar versionar o relatório, use `docs(audit): auditoria da Wave 1`.
- **Apresente no chat:** o **veredito (go/no-go)**, o **número de achados por severidade**, e a **lista completa dos achados Críticos e Altos** com sua remediação recomendada.
- **Pergunte ao dono** se deve **gerar um prompt de remediação** priorizado a partir dos achados (sem aplicar nada agora).

---

### Lembrete final
Esta é a auditoria da camada de **segurança** do sistema. O maior risco não é o código que falha barulhento — é o que **parece funcionar e silenciosamente não protege**: uma RLS contornável porque o role é owner; uma chave secreta no bundle; um claim na posição errada que faz a RLS retornar tudo; uma matriz que diverge do modelo decidido. **Procure exatamente essas coisas.** Seja cético, execute as verificações de verdade, e **na dúvida, pare e pergunte** antes de dar um veredito. Um **NO-GO honesto** vale mais do que um **GO** que deixa um furo passar para a Wave 2.
