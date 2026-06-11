# Prompt de Execução — W1-C04 · Cadastro e Gestão de Usuários (+ App Shell da Plataforma)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz do repositório, a **Wave 0 e o C03 concluídos e mergeados**, e as **duas imagens do design anexadas** (a tela "Gerenciador de usuários" e o modal "Novo usuário"). Este é o **segundo componente da Wave 1** e **estabelece o shell de layout de toda a plataforma autenticada**. Trabalhe a sessão inteira neste único componente, do começo ao fim.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize em especial:
- **§2 / §2.1** — hierarquia de fontes da verdade e **divergências**. *Atenção: este componente expõe uma divergência entre o design e os Requisitos (perfil/setor) que precisa ser reconciliada — ver DP-1.*
- **§3** — pilares: **robustez, escalabilidade, mínimo de requisições ao Supabase, observabilidade** e **animações leves e suaves**. Renan reforçou: o mais importante aqui é **robustez, escalabilidade e código limpo, sem bugs**.
- **§4** (stack) e **§5** (Ports & Adapters + layout do monorepo).
- Separação de autenticação (DAT **§1.3**): Supabase Auth emite/gerencia; o backend **nunca emite**. Gestão de schema (DAT **§2**): tabelas de **domínio** via **Alembic**; enums via `CREATE TYPE`; políticas RLS versionadas em `/migrations/rls/`. Sincronização de enums Python↔PostgreSQL (DAT **§4.5**).

**Estado atual do repositório (Waves 0 + C03 entregues):**
- Backend FastAPI stateless (Settings, logging estruturado, DB async, storage R2, health checks, Alembic baseline **sem tabelas de domínio**). **C04 cria a primeira migration de domínio.**
- C03 entregou: login Supabase via **`@supabase/ssr`** (clients de browser e de servidor + `middleware.ts` de refresh de sessão), **verificação de JWT no backend** (ES256/JWKS + HS256, com `/auth/me`), encerramento por inatividade de 30 min, **fundação mínima de animações** (`lib/motion/tokens.ts` + `useReducedMotion`). **Reaproveite tudo isso — não recrie.**
- Wave 0 fechada (infra + keep-alive).

**Decisões/insumos confirmados que regem esta sessão:**
- Hospedagem: **Vercel** (web) + **Railway** (API); futuro on-prem. Repositório **privado**.
- Design do **Gerenciador de usuários** e do **modal Novo usuário** definidos no Figma e anexados. **Layout exatamente igual ao design.**
- **O shell (sidebar preta + área de conteúdo "shell branco") é o layout de TODA a plataforma autenticada** — só o conteúdo dentro do shell muda conforme o item de menu. Este componente o constrói como **layout reutilizável**.

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — modelo de domínio, arquitetura de auth, nomenclatura, credencial, escopo, responsividade, token de design — você **para, expõe o ponto com 2–3 opções e a sua recomendação, e aguarda a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, confirme o estado das Waves 0 + C03 no repositório e **apresente, de uma só vez e em bloco, todos os Pontos de Decisão da §4.** Aguarde as respostas. *(DP-1 é bloqueante: o schema não pode ser escrito sem ela.)*
2. Só depois das respostas, comece a implementar na ordem da §8.
3. Surgindo nova ambiguidade no meio da execução, **pare imediatamente** e pergunte.
4. **Nunca invente** nomes de variáveis/secrets, rotas, nomes de assets, ícones ou valores de design (hex, fontes, tamanhos, raios). Em dúvida, **pergunte**.

---

## 0.2 Fidelidade ao design e o App Shell

A **imagem do Figma anexada é a fonte da verdade visual.** Há duas telas:

**(1) Gerenciador de usuários** — estrutura em duas zonas, que é o **shell da plataforma**:
- **Sidebar** (fundo preto, fixa à esquerda): wordmark **3STUDIO** no topo; saudação **"Olá Mônica!"**; campo **"Buscar..."**; itens de navegação com ícone — **Dashboard, Provas, Nova prova, Escanear, Relatórios, Usuários** (item ativo, em destaque amarelo com barra à esquerda), depois **Configurações, Informações**; no rodapé, avatar + **"Mônica / 3Studio"** + link **"Sair"**.
- **Área de conteúdo (shell branco arredondado)** sobre o fundo preto: título **"Gerenciador de usuários"**; botão **"Novo usuário"** (amarelo, à direita); barra de busca **"Buscar por nome ou email..."**; dois filtros dropdown (**"Todos os setores"**, **"Todos"**); e uma **tabela** com colunas **Nome · E-mail · Setor · Localização · Status · Perfil · Ações**, com botões por linha **Editar** (preto) e **Desativar** (vermelho). A tabela é rolável.

**(2) Modal "Novo usuário"** — sobre o conteúdo escurecido: título **"Novo usuário"**; campos **Nome**, **E-mail**, **"Senha (min. 8, com letra e numero):"**, **Setor** (campo de seleção); checkbox **"Administrador"**; botões **Cancelar** (escuro) e **Cadastrar** (amarelo).

**O shell deve ser implementado como layout reutilizável** (o grupo de rotas autenticadas), de modo que Dashboard, Provas, Relatórios etc. (componentes futuros) renderizem **dentro** dele sem reconstruí-lo. Itens de menu que apontam para páginas ainda inexistentes são tratados conforme **DP-6**.

**Para "exatamente igual", valores do PNG são aproximados.** Tokens precisos (cores do shell branco, da tabela, da sidebar, do amarelo, do vermelho "Desativar", do preto dos botões "Editar"; tipografia; raios; espaçamentos) e os **ícones da sidebar** e o **wordmark** devem ser confirmados — ver **DP-9**. **Não chute: pergunte.**

---

## 1. Objetivo do componente

Entregar, de forma robusta, escalável e com código limpo:
1. O **app shell reutilizável** (sidebar + área de conteúdo) que hospedará toda a plataforma autenticada.
2. O **CRUD de usuários** (RF-018, RF-020, US-015): listar (paginado/filtrável), criar (modal "Novo usuário"), editar e **desativar** (sem excluir histórico), com as regras **RN-009** (um setor por usuário; localização obrigatória só para Vendedor, informativa) e **RN-010** (admin não pode se autodesativar; só admin gerencia admin).
3. A **primeira tabela de domínio** (`usuarios`) e a **primeira migration Alembic de domínio**, com enums de domínio versionados.
4. O **provisionamento de usuários** integrando o **Supabase Auth Admin API** (senha definida pelo admin) com a tabela de domínio, de forma coordenada e à prova de falhas parciais.
5. **Responsividade** (sem mockup mobile — ver DP-7) e **animações imersivas e contidas** sobre a fundação de motion do C03 (incluindo o **modal animado**), respeitando **`prefers-reduced-motion`**.

Referências: Backlog **C04** · Requisitos **RF-018, RF-020, RN-009, RN-010, US-015, RNF-001, RNF-005, RNF-018, RNF-019, RNF-023** · DAT **§1.3, §2, §4.5, §5.2, §5.4** · **RN-012, RNF-010**.

---

## 1.1 Fatos técnicos atuais e divergência a reconciliar

1. **Criar usuário com senha definida pelo admin = `auth.admin.createUser` (server-only).** Exige a **chave secreta/service-role** (`sb_secret_…`, ou a legada `service_role`), que **só pode existir no backend FastAPI (Railway)** — **nunca** em `NEXT_PUBLIC_*`/bundle do cliente (a chave é bloqueada em origens de browser e dá acesso com BYPASSRLS). Use `admin.createUser` (não `signUp`), com `email_confirm: true`. O frontend chama um **endpoint do backend**, que detém a chave.
2. **Vínculo de identidades:** existem o usuário de **autenticação** (`auth.users`, gerenciado pelo Supabase) e o usuário de **domínio** (`usuarios`, gerenciado por Alembic, com setor/localização/perfil/ativo). Eles devem ser **vinculados 1:1** (ver DP-2).
3. **Claims para o C05:** o RBAC do C05 lê o setor/perfil via JWT (Custom Access Token Hook) e RLS. Para preparar o terreno, o C04 deve **gravar setor/perfil no `app_metadata`** do usuário ao criar (a configuração do hook e as políticas RLS por perfil ficam no C05 — ver DP-5).
4. **DIVERGÊNCIA design × Requisitos (bloqueante — DP-1):** os **Requisitos (§3, §7)** modelam **quatro setores** (3Studio, Clicheria, Vendedor, Motorista), sendo **"3Studio" o perfil administrador**. O **design** mostra um campo **Setor** *e* um checkbox **Administrador** separado, com a coluna **Perfil = Admin/Usuário** — sugerindo que "administrador" é um **flag ortogonal ao setor** (ex.: a tabela mostra "Setor: Vendedor" com "Perfil: Admin"). **São modelos diferentes.** Isso define o schema de `usuarios` **e** o RBAC do C05. **Tem que ser reconciliado antes do schema.**

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **App shell reutilizável** (frontend): layout do grupo de rotas autenticadas (ex.: `app/(app)/layout.tsx`) com a **sidebar** (nav + busca + saudação + rodapé de usuário/Sair) e a **área de conteúdo (shell branco)**. A página de **Usuários** é o **primeiro conteúdo** renderizado dentro do shell.
- **Backend — domínio `usuarios`:** tabela `usuarios` + enums de domínio (`setor`, e `localizacao` se aplicável) na **primeira migration Alembic de domínio**; **RLS habilitada com postura restritiva** (acesso direto negado; leitura/escrita via backend) — as políticas completas por perfil são do C05, mas a tabela **não** pode nascer exposta.
- **Backend — endpoints (Ports & Adapters), com guard mínimo de admin (DP-5):**
  - **Listagem** paginada **server-side** (RNF-019), com busca por nome/email (debounce no front, RNF-023) e filtros por setor e status (e o que o design exibir); índices nas colunas de filtro/ordenação.
  - **Criar** usuário: valida payload (incl. **senha min. 8 com letra e número**), chama o **Admin API** (`createUser`, service role) e insere a linha `usuarios` de forma **coordenada** (compensação/rollback lógico em falha parcial); grava setor/perfil no `app_metadata` (DP-5).
  - **Editar** usuário (campos editáveis; regras RN-009/RN-010).
  - **Desativar/Reativar:** **ban/disable do auth user** (Admin API) + `usuarios.ativo=false` (DP-3) — sem excluir histórico (US-015); bloquear autodesativação do admin (RN-010).
- **Frontend — Usuários:** tabela fiel ao design (colunas, botões Editar/Desativar), busca, filtros; **modal "Novo usuário"** (validação em tempo real, estados de carregamento/erro/sucesso); ações de editar/desativar com confirmação.
- **Animações** (DP-8): estender a fundação de motion do C03; **componente de modal animado reutilizável** (forward-compatible com o `<MotionModal>` do C19); indicador animado do item ativo na sidebar; transição de conteúdo ao trocar de menu; **toasts** de sucesso/erro; stagger sutil das linhas/cards. GPU-only + `prefers-reduced-motion`.
- **Configuração:** adicionar ao `.env.example` da **API** a chave secreta do Supabase (nome confirmado em DP-3), com comentário e **sem valor real**, deixando explícito que é server-only.
- **Documentação** (`docs/usuarios.md` e atualização de `docs/` do shell): modelo de domínio (pós-DP-1), o fluxo de provisionamento (Admin API), a postura de RLS provisória, a estrutura do shell e como novos itens de menu/páginas plugam nele.
- **Testes** (§7) e **Protocolo de Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Matriz de Acesso completa / `access-matrix.ts` / enforcement por perfil no middleware / Custom Access Token Hook / políticas RLS por perfil** (Componente **05**). Aqui apenas: **guard mínimo de admin** nos endpoints de usuários (DP-5), **RLS restritiva provisória** na `usuarios`, e gravação de setor/perfil no `app_metadata`.
- ❌ **Visibilidade dos itens de menu por perfil** (C05). O shell renderiza o menu conforme DP-6; o filtro por perfil vem depois.
- ❌ **Páginas dos demais itens de menu** (Dashboard=C16, Provas=C07, Nova prova=C06, Escanear=C10, Relatórios=C17, Configurações=C09). São **placeholders** agora (DP-6).
- ❌ **Conjunto completo da camada de animações do C19** (`<PageTransition>`, `<AnimatedCounter>`, `<AnimatedTimeline>`, toaster global definitivo). Aqui: fundação + modal reutilizável + animações locais do shell/usuários.
- ❌ Qualquer tabela/enum de **provas** (`rota_enum`, `status_prova_enum`), domínio de provas, máquina de estados — Wave 2+.

> Vontade de adiantar RBAC completo, páginas futuras ou a camada de animações do C19: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Chave secreta server-only:** a `sb_secret`/`service_role` vive **apenas** no backend (Railway), em variável de ambiente; **jamais** em `NEXT_PUBLIC_*` nem em qualquer bundle do cliente. Toda operação de Admin API (`createUser`, ban/disable) ocorre **no backend**.
2. **Provisionamento coordenado e idempotente:** criar usuário = auth user (Admin API) **+** linha `usuarios`, com tratamento de **falha parcial** (se a segunda etapa falhar, compensar/limpar a primeira ou marcar de forma consistente; nunca deixar identidade órfã). Em transação atômica onde aplicável (RNF-017).
3. **Regras de negócio enforce no backend:** RN-009 (exatamente um setor; localização obrigatória só p/ Vendedor; localização informativa, não roteia), RN-010 (admin não se autodesativa; só admin gerencia/promove admin). Validar com Pydantic v2.
4. **Senha:** política **min. 8 com letra e número** validada no front **e** no back; alinhar a política de senha do Supabase Auth no dashboard (config externa — DP-3).
5. **Escalabilidade/mínimo de requisições:** listagem **paginada server-side** com limite por página; **índices** nas colunas de filtro/ordenação (RNF-019); busca com **debounce ≥ 300 ms** (RNF-023); sem N+1 (RNF-022); carregar a tela em ≤ 3 s (RNF-001).
6. **RLS provisória:** `usuarios` nasce com RLS **habilitada** e postura restritiva (acesso direto negado a `anon`/`authenticated`; dados servidos via backend). Versionar em `/migrations/rls/`. Políticas por perfil = C05.
7. **Estilização:** **somente CSS Modules**. Mobile-first; *touch targets* ≥ 44×44 px / 48 dp (RNF-013); contraste adequado.
8. **Animações:** apenas `transform`/`opacity` (GPU — DAT §5.4); durações dos tokens; **`prefers-reduced-motion` obrigatório** (degrada para instantâneo — RN-012, RNF-010). Modal: scale 0.96→1.0 + fade na entrada, fade na saída (DAT §5.2). Imersivo, mas **contido** (DAT §2.4).
9. **Stateless** (RNF-018); **sem segredos versionados**; **custo R$ 0**.
10. **Acesso a `usuarios` via backend** (admin-guarded), não por leitura direta do client Supabase no browser (até o C05 ligar a RLS por perfil).

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a sua recomendação destacada. Não comece a §5 sem as respostas. **DP-1 é bloqueante.**

### Bloco A — Modelo de domínio e provisionamento

**DP-1 — Modelo Setor × Administrador (BLOQUEANTE).**
Reconciliar a divergência (§1.1.4). Opções:
- (a) **Ortogonal (como o design):** `usuarios.setor` ∈ {3studio, clicheria, vendedor, motorista} **e** `usuarios.administrador` (boolean). "Perfil" (Admin/Usuário) deriva do boolean. Implica revisar o RBAC do C05 (páginas de admin chaveiam por `administrador`; escopo operacional por `setor`).
- (b) **Admin === setor 3Studio (como os Requisitos):** sem flag separado; o setor 3Studio é o administrador.
Diga qual governa. **Será registrado como ADR e refletido em `CLAUDE.md §2.1`.** (Se for (a), aponte como a Matriz de Acesso da §7 dos Requisitos deve ser ajustada.)

**DP-2 — Schema de `usuarios` e vínculo com `auth.users`.**
**[Recomendado]** PK de `usuarios` = **UUID do `auth.users`** (1:1). Confirmar os campos: `id`, `nome`, `email`, `setor` (enum), `localizacao` (enum/nullable — obrigatório só p/ Vendedor), perfil/`administrador` (conforme DP-1), `ativo` (boolean), `created_at`/`updated_at`. Confirmar nomes dos **enums** (`setor_enum`, `localizacao_enum`?) — primeira migration de domínio (DAT §2/§4.5).

**DP-3 — Provisionamento, senha e variável da chave secreta.**
**[Recomendado]** backend cria o auth user via Admin API (`createUser`, `email_confirm: true`) + linha `usuarios`, coordenado, com compensação em falha parcial. Confirmar: o **nome da variável** da chave secreta no backend (ex.: `SUPABASE_SECRET_KEY`); usar **`sb_secret`** (novo) ou a `service_role` legada; e **quem configura** a política de senha (min 8, letra+número) no dashboard do Supabase.

**DP-4 — Desativação.**
**[Recomendado]** "Desativar" = **ban/disable do auth user** (Admin API) **+** `usuarios.ativo=false`, bloqueando login sem excluir histórico (US-015, RN-010). Confirmar a abordagem e a regra de autodesativação/gestão de admin (RN-010).

**DP-5 — Guard mínimo agora vs. RBAC completo no C05.**
**[Recomendado]** endpoints de usuários verificam o JWT (C03) **e** exigem que o chamador seja admin (lendo a linha `usuarios` dele); **RLS restritiva provisória** na tabela; gravar setor/perfil no **`app_metadata`** para o C05 consumir. O Custom Access Token Hook + matriz + RLS por perfil ficam no **C05**. Confirmar essa fronteira.

### Bloco B — Shell, responsividade e animações

**DP-6 — Itens de menu e rotas placeholder.**
Confirmar: a **lista e a ordem** dos itens da sidebar (conforme o design) e suas **rotas-alvo**; que itens de páginas inexistentes (Dashboard, Provas, etc.) apontam para um **placeholder neutro** (ou ficam desabilitados) **agora**, com a **visibilidade por perfil** adiada para o C05; e a **fonte** da saudação "Olá Mônica!", do avatar e do "Sair" (a linha `usuarios` do usuário logado + sessão do C03).

**DP-7 — Responsividade (sem mockup mobile).**
Não há design mobile desta tela. **[Recomendado]** sidebar → **drawer/hambúrguer**; tabela → **lista de cards** (ou scroll horizontal) abaixo de um breakpoint; modal → **full-screen/bottom-sheet** no mobile. Confirmar a abordagem **ou fornecer mockup mobile**. Definir o **breakpoint** de corte.

**DP-8 — Animações e modal reutilizável (fronteira C04↔C19).**
**[Recomendado]** reutilizar a fundação de motion do C03 e criar **agora** um **modal animado reutilizável** (forward-compatible com `<MotionModal>` do C19), usado pelo "Novo usuário" e por futuros modais; toasts de feedback; indicador animado do item ativo; transição de conteúdo ao trocar de menu; stagger sutil de linhas/cards. Confirmar essa fronteira (o C19 generaliza/documenta depois, sem reescrever).

**DP-9 — Tokens e assets do design.**
Fornecer os **tokens do Figma** desta tela (cores do shell branco, tabela, sidebar, amarelo, vermelho "Desativar", preto "Editar"; tipografia; raios; espaçamentos) — ou o **link do Figma** (extrair via Dev Mode/MCP, se disponível). Confirmar a **biblioteca/origem dos ícones** da sidebar (ex.: `lucide-react`?) e o **wordmark 3STUDIO** (asset SVG?). **Sem esses valores, não chute — pergunte.**

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; use nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida sobre localização/nome, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- **Shell:** `app/(app)/layout.tsx` (ou equivalente) com `<Sidebar>` e a área de conteúdo (shell branco), em **CSS Modules**. A sidebar lê o usuário logado (nome/setor) da sessão (C03) + linha `usuarios`. Itens de menu conforme DP-6.
- **Página de usuários:** `app/(app)/usuarios/page.tsx` — tabela fiel ao design (colunas, Editar/Desativar), busca (debounce), filtros (setor, status), paginação; consome o **backend** (não o client Supabase direto).
- **Modal reutilizável:** `src/components/ui/Modal` (animado, forward-compatible com `<MotionModal>` do C19) + o formulário "Novo usuário" (validação em tempo real: senha min 8/letra+número; setor; campos obrigatórios; estados de loading/erro/sucesso).
- **Sistema de toasts** (feedback de sucesso/erro), reutilizável.
- **Placeholders** das rotas de menu inexistentes (DP-6).
- Extensão de `src/lib/motion/` se necessário (sem literais inline; tudo via tokens).
- Ícones e wordmark conforme DP-9.

### 5.2 Backend — `apps/api/`
- **Migration Alembic de domínio** (`versions/00xx_usuarios.py`): enums (`setor_enum`, etc.), tabela `usuarios` (campos de DP-2), índices (RNF-019), `downgrade` correspondente. **RLS restritiva** versionada em `migrations/rls/usuarios_*.sql` (postura provisória).
- **Domínio/aplicação/adapters** (regra hexagonal): modelo `Usuario`, schemas Pydantic (validação de RN-009/RN-010/senha), porta de provedor de identidade (Admin API) + adapter Supabase, casos de uso (criar/editar/desativar/listar).
- **Endpoints HTTP** (com **guard mínimo de admin** — DP-5): `GET /usuarios` (paginado/filtrável), `POST /usuarios` (provisionamento coordenado), `PATCH /usuarios/{id}` (editar), `POST /usuarios/{id}/desativar` e `/reativar` (ban/disable + `ativo`). Erros padronizados; logs estruturados; **sem vazar segredo**.
- `.env.example`: variável da chave secreta (DP-3), com comentário e marcação **server-only**, sem valor real.

### 5.3 Documentação — `docs/`
- `docs/usuarios.md`: modelo de domínio (pós-DP-1), fluxo de provisionamento (Admin API + compensação), postura de RLS provisória, regras RN-009/RN-010, política de senha.
- Documentar o **shell** (estrutura, como novas páginas/itens de menu plugam) — em `docs/` ou README do módulo. Incluir a **checklist** dos critérios de aceitação (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Shell reutilizável** funcionando: sidebar + área de conteúdo fiéis ao design; a página de Usuários renderiza dentro do shell; itens de menu conforme DP-6 (placeholders para páginas futuras).
2. ✅ **Cadastro** exige todos os campos obrigatórios; **localização obrigatória só para Vendedor** (RN-009); **senha min. 8 com letra e número** validada (front+back). Criar usuário provisiona o auth user (Admin API) **e** a linha `usuarios` de forma coordenada; falha parcial não deixa órfão.
3. ✅ **Desativação** bloqueia o login do usuário **sem excluir** seu histórico (US-015); **admin não consegue se autodesativar** e só admin gerencia admin (RN-010).
4. ✅ **Apenas o perfil administrador** acessa a gestão de usuários (guard mínimo no backend — DP-5); usuário não-admin recebe negação. *(Enforcement completo de página/RLS por perfil = C05.)*
5. ✅ **Listagem** paginada server-side, busca com debounce e filtros funcionando; carrega em ≤ 3 s (RNF-001); sem N+1; índices presentes (RNF-019).
6. ✅ **Fidelidade ao design** (tabela, modal, sidebar, cores, tipografia, raios, espaçamentos).
7. ✅ **Animações imersivas e fluidas** (modal scale+fade, toasts, item ativo, transição de conteúdo), **degradando para instantâneo** com `prefers-reduced-motion`; apenas `transform`/`opacity`.
8. ✅ **Responsivo** conforme DP-7 (sidebar→drawer, tabela→cards/scroll, modal→full-screen), *touch targets* ≥ 44×44 px / 48 dp.
9. ✅ `usuarios` com **RLS habilitada** (postura restritiva versionada); **chave secreta apenas no backend**, **sem segredos versionados**; **stateless**; **R$ 0**.
10. ✅ `ruff`, `mypy (strict)`, `pytest`, `pnpm lint`/`build` **verdes**; `alembic upgrade head`/`downgrade` aplicam em ambiente limpo; sem erros no console.

---

## 7. Testes desta camada

**Backend**
- Provisionamento: criação com Admin API **mockada** → cria auth user + linha `usuarios`; **falha parcial** (Admin API ok, insert falha, e vice-versa) → estado consistente (sem órfão).
- RN-009: localização obrigatória só p/ Vendedor; exatamente um setor. RN-010: bloqueio de autodesativação; só admin gerencia admin.
- Senha: rejeita < 8, sem letra ou sem número.
- Listagem: paginação server-side, filtros e busca; verificação de uso de índice; sem N+1.
- Guard: endpoint de usuários nega chamador não-admin (DP-5).
- Migration: `upgrade`/`downgrade` em ambiente limpo; RLS aplicada.
- Roda **offline** (Admin API e Supabase mockados; Postgres local).

**Frontend**
- Render fiel do shell e da tabela; modal abre/fecha; validações em tempo real; estados de loading/erro/sucesso; toasts.
- Desativar pede confirmação; reflete status na tabela.
- Responsividade (≥ 360 px; sidebar→drawer; tabela→cards/scroll; modal→full-screen) e `prefers-reduced-motion` (animações instantâneas).
- **E2E (Playwright):** criar usuário (caminho feliz), validações, desativar; navegação pelo shell. Sem credencial real (mocks/ambiente de teste).

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, confirme Waves 0 + C03 e a configuração existente.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas (DP-1 é bloqueante).**
3. Backend: migration de domínio `usuarios` + enums + índices + RLS restritiva; rode `alembic upgrade head`/`downgrade`.
4. Backend: domínio/serviços + porta do provedor de identidade + endpoints com guard mínimo (provisionamento coordenado, editar, desativar, listar); testes verdes.
5. Frontend: **shell** (layout + sidebar) reutilizável; placeholders dos itens de menu (DP-6).
6. Frontend: página de Usuários (tabela, busca, filtros, paginação) consumindo o backend.
7. Frontend: modal reutilizável + "Novo usuário"; toasts; animações sobre os tokens (GPU-only, reduced-motion); responsividade (DP-7).
8. `docs/` + `.env.example`.
9. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
10. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`, descreva o que o W1-C04 entregou (app shell reutilizável; CRUD de usuários; primeira tabela/migration de domínio `usuarios`; provisionamento via Admin API; desativação; modal/animações; responsividade).
2. **`DECISIONS.md`** — novos ADRs: (a) **modelo Setor × Administrador** (resultado da DP-1) e ajuste correspondente da Matriz de Acesso; (b) **vínculo `usuarios` ↔ `auth.users`** (1:1) e o schema; (c) **provisionamento via Admin API** + manuseio da chave secreta server-only + estratégia de compensação; (d) **arquitetura do app shell** (layout reutilizável); (e) **fronteira guard-mínimo-agora / RBAC-completo-no-C05** + RLS provisória + `app_metadata`; (f) **fronteira C04↔C19** (modal/animações). **Atualize `CLAUDE.md §2.1`** com a reconciliação da DP-1.
3. **`SESSION_LOG.md`** — nova entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes/cobertura, **pendências** e **próximo passo** = **W1-C05 · Controle de Acesso por Perfil — Matriz RBAC**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** (rodar migrations de domínio; rodar o fluxo de usuários localmente); registre o **padrão do app shell**, o **modelo de domínio** de `usuarios` e a regra da **chave secreta server-only**. Enxuto e verdadeiro.
5. **`README.md`** — atualize setup (chave secreta no backend; política de senha no dashboard) e o roadmap (C04 concluído; shell estabelecido).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. provisionamento e RN-009/RN-010), **migration versionada e documentada**, **RLS de `usuarios` versionada** em `/migrations/rls/`, sem erro de console/log crítico, docs do módulo, idempotência do provisionamento, error handling, animações validadas com `prefers-reduced-motion`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w1-c04): ...`, `chore(w1-c04): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. fidelidade ao design, provisionamento coordenado e regras RN-009/RN-010), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W1-C05**).

---

### Lembrete final
Este componente carrega o **layout de toda a plataforma** e a **primeira tabela de domínio** — se o shell ou o modelo de `usuarios` saírem frágeis, todo o resto se apoia em base ruim. O provisionamento toca a **chave mais sensível do projeto**: trate-a com rigor (server-only, sem vazamento, falha parcial sem órfão). Robustez, escalabilidade e código limpo aqui são o pedido explícito do dono do produto. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
