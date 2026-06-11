# Prompt de Execução — W1-C03 · Tela de Login e Sessão

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz do repositório, a **Wave 0 concluída** (C01 + C02 mergeados) e a **imagem do design da tela de login anexada** (a mesma que será colocada em `apps/web/public/`). Este é o **primeiro componente da Wave 1**. Trabalhe a sessão inteira neste único componente, do começo ao fim.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize em especial:
- **§3** — pilares: **robustez/à prova de erros, escalabilidade, mínimo de requisições ao Supabase, observabilidade** e **animações leves e suaves** (este componente toca os pilares de robustez, mínimo de requisições e animações).
- **§4** (stack) e **§5** (Ports & Adapters + layout do monorepo).
- **§9** (comandos) e **§11** (o que NÃO fazer).
- Separação de responsabilidades de autenticação (DAT **§1.3** e **§7**): **o Supabase Auth emite e gerencia o JWT/sessão; o backend NUNCA emite — apenas verifica a assinatura** com PyJWT.

**Estado atual do repositório (Wave 0 entregue):**
- Monorepo `apps/api` + `apps/web`. Backend FastAPI stateless com `infrastructure/config.py` (Settings), `infrastructure/logging.py` (log estruturado JSON + `request_id`), `infrastructure/database.py` (engine async, sessão), porta de storage + adapter R2, health checks, Alembic assíncrono com baseline.
- Frontend Next.js (App Router + TypeScript strict + **CSS Modules**, sem framework CSS externo) com **client Supabase mínimo** já existente em `apps/web/src/lib/supabase/` (somente configuração, sem login). **Reaproveite e estenda — não recrie do zero.**
- Keep-alive (C02) operacional. Wave 0 fechada.

**Decisões/insumos confirmados pelo dono do produto que regem esta sessão:**
- Hospedagem atual: **Vercel** (web) + **Railway** (API). Futuro: on-prem (rede interna). *(Relevante aqui pelo cuidado de cache de CDN — ver §3.)*
- Repositório **privado**.
- Design da tela de login **definido no Figma** e anexado a esta sessão. **O layout deve ficar exatamente igual ao design.**

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Onde houver qualquer ambiguidade — arquitetura, fluxo de auth, nomenclatura, credencial, escopo, token de design — você **para, expõe o ponto com 2–3 opções e a sua recomendação, e aguarda a resposta do dono do produto antes de implementar.**

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, confirme o estado das Waves 0 no repositório e **apresente, de uma só vez e em bloco, todos os Pontos de Decisão da §4.** Aguarde as respostas.
2. Só depois das respostas, comece a implementar na ordem da §8.
3. Surgindo nova ambiguidade no meio da execução, **pare imediatamente** e pergunte.
4. **Nunca invente** nomes de variáveis de ambiente, nomes de *secrets*, rotas, nomes de arquivos de asset ou valores de design (hex, fontes, tamanhos, raios). Se não estiverem definidos no C01/C02 ou aqui, **pergunte**.

---

## 0.2 Fidelidade ao design (obrigatória)

A **imagem do Figma anexada é a fonte da verdade visual.** Reproduza o layout **exatamente** — proporções, hierarquia, espaçamentos, cantos arredondados, cores, tipografia e posicionamento. Há **três telas** no design:

1. **Desktop — login (split):** imagem do diorama 3D à esquerda (painel com canto arredondado no encontro com o fundo preto); à direita, sobre fundo preto, o bloco do formulário: wordmark **3STUDIO** no topo, título grande **"Fazer login"**, subtítulo apagado, rótulo **"E-mail:"** + campo arredondado escuro, rótulo **"Senha:"** + campo arredondado escuro, link pequeno **"Esqueci minha senha"**, botão **"Entrar"** amarelo (pílula, texto escuro) ocupando a largura do bloco, rodapé centralizado **"©3Studio 2026"**.
2. **Mobile — boas-vindas:** metade superior com a imagem do diorama (full-bleed, com transição/gradiente suave da imagem para o preto); metade inferior preta com wordmark **3STUDIO**, título **"Seja bem vindo!"** (duas linhas, bold), subtítulo apagado e botão **"Entrar"** amarelo (pílula) na zona inferior.
3. **Mobile — login:** fundo totalmente preto, coluna centralizada: wordmark **3STUDIO**, **"Fazer login"**, subtítulo, **"E-mail:"** + campo, **"Senha:"** + campo, **"Esqueci minha senha"** (centralizado, apagado), botão **"Entrar"** amarelo e rodapé **"©3Studio 2026"**.

**Para "exatamente igual", valores aproximados do PNG não bastam.** Os tokens precisos (hex de cores, família/pesos de fonte, tamanhos, *line-height*, *border-radius*, espaçamentos) e os assets (a **imagem-herói** e o **wordmark 3STUDIO**, que provavelmente é um logo/SVG e não texto em fonte) devem ser confirmados — ver **DP-8**. **Não** chute esses valores: pergunte.

---

## 1. Objetivo do componente

Entregar a **autenticação por e-mail e senha** (RF-019) com **Supabase Auth**, a **sessão stateless** (estado no JWT, em cookie — RNF-018), o **encerramento automático por inatividade de 30 minutos** (RNF-004), e o **caminho de verificação de JWT no backend** com PyJWT — tudo materializado nas **três telas do design**, com **animações imersivas, porém contidas** (leves, suaves, sutis; nunca chamativas — DAT §2.4), respeitando **`prefers-reduced-motion`** (RN-012, RNF-010).

Referências: Backlog **C03** · Requisitos **RF-019, RNF-004, RNF-005, RNF-008, RNF-013, RNF-018** · DAT **§1.3, §5** · **RN-012, RNF-010**.

---

## 1.1 Fatos técnicos atuais (orientam a implementação — não use suposições antigas)

1. **Assinatura do JWT do Supabase mudou.** Projetos atuais assinam por padrão com **ES256 (assimétrico)**; verificar o token **somente** contra o segredo HS256 legado quebra (401) e quebra na rotação de chaves. A verificação assimétrica usa o **endpoint JWKS** do projeto (`/auth/v1/.well-known/jwks.json`), cacheado. **O backend deve verificar de forma robusta a ambos** (ler `alg`/`kid` do header; ES256 via cliente JWKS com cache; HS256 como *fallback* com o segredo), validando `audience="authenticated"` e a expiração. *(Isto difere do que o DAT/C01 assumiram com `SUPABASE_JWT_SECRET` — ver DP-2 e o Encerramento.)*
2. **Biblioteca de auth no Next.js App Router = `@supabase/ssr`** (o antigo `@supabase/auth-helpers-nextjs` está **deprecado**). Sessão em **cookies HTTP-only**, com um **`middleware.ts`** que faz o **refresh** do token. Dois clients: **browser** (`createBrowserClient`) e **server** (`createServerClient`, lendo cookies via `next/headers`).
3. **Para qualquer lógica de proteção, verifique no servidor com `supabase.auth.getUser()`** (que valida no servidor de auth), **não** `getSession()`.
4. **Cuidado de cache/CDN (Vercel):** respostas que escrevem `Set-Cookie` de refresh **não podem ser cacheadas** (ISR/CDN), sob risco de servir a sessão de um usuário a outro. Garanta `Cache-Control` adequado nas rotas afetadas.

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Frontend — as três telas do design** (§0.2) em **CSS Modules**, mobile-first, totalmente responsivas (≥ 360 px, *touch targets* ≥ 44×44 px / 48 dp — RNF-013).
- **Auth via `@supabase/ssr`:** estender `apps/web/src/lib/supabase/` com **client de browser** e **client de servidor**; login com `signInWithPassword`; **mensagem de erro genérica** em falha (sem revelar qual campo falhou); redirecionamento pós-login (DP-5).
- **`middleware.ts` — SOMENTE refresh de sessão** (o `updateSession` do padrão `@supabase/ssr`). **Sem RBAC** (isso é C05).
- **Encerramento por inatividade de 30 min** (DP-4): timer no app que, ao expirar, faz `signOut` + redireciona ao login com toast leve.
- **Backend — verificação de JWT:** dependência FastAPI que valida o Bearer JWT com **PyJWT robusto a ES256(JWKS)+HS256**, valida `aud`/`exp`, e extrai a identidade (sub, email, claims). **Endpoint mínimo de prova** (ex.: `GET /auth/me`) que exige JWT válido e devolve a identidade verificada — é a evidência demonstrável de que o caminho de verificação funciona.
- **Fundação mínima de animações** (DP-6): `apps/web/src/lib/motion/tokens.ts` (DURATION/EASING do DAT §5.1) + hook `useReducedMotion`. As animações do login são construídas **sobre esses tokens** (sem literais inline), de modo que o **C19 estenda** (PageTransition, MotionModal, etc.) sem reescrever.
- **Configuração:** adicionar ao `.env.example` da API/web as variáveis necessárias (ex.: `SUPABASE_JWKS_URL` e/ou `SUPABASE_JWT_SECRET`, chave publishable/anon — nomes confirmados em DP-2), com comentário e **sem valores reais**.
- **Documentação** (`docs/auth.md`): arquitetura de login/sessão, o caminho de verificação (ES256/JWKS + HS256), a regra dos 30 min, o cuidado de cache de CDN, e como validar localmente.
- **Testes** (§7) e **Protocolo de Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **RBAC / Matriz de Acesso / `access-matrix.ts` / enforcement por perfil** (Componente **05**). O `middleware.ts` aqui **só** faz refresh de sessão.
- ❌ **CRUD de usuários** e a tabela de aplicação `usuarios` (Componente **04**).
- ❌ **Qualquer tabela de domínio ou migration Alembic.** As tabelas de **auth** são gerenciadas pelo Supabase (DAT §2 — não tocar via Alembic). **C03 não cria migration.**
- ❌ **RLS** (não há tabela de domínio nesta sessão).
- ❌ **O conjunto completo da camada de animações do C19** (`<PageTransition>`, `<MotionModal>`, `<AnimatedCounter>`, `<AnimatedTimeline>`, toaster global). Aqui só a **fundação mínima** (tokens + `useReducedMotion`) e as animações **locais do login**.
- ❌ **Fluxo de redefinição de senha** (envio de e-mail + página de reset), salvo decisão explícita em **DP-7**. Por padrão, o link "Esqueci minha senha" é renderizado conforme o design, mas inerte/placeholder.
- ❌ Dashboard, relatórios, provas ou qualquer item de Wave 2+.

> Se sentir vontade de "adiantar" RBAC, usuários ou a camada de animações completa, **pare** e registre como pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **`@supabase/ssr`** (não o pacote deprecado). Sessão em **cookies HTTP-only**. Clients de browser e de servidor separados.
2. **Proteção sempre via `getUser()` no servidor** (não `getSession()`); o `middleware.ts` apenas **refaz/atualiza** a sessão.
3. **Backend:** PyJWT (≥ 2.8) **robusto a ES256(JWKS, com cache do JWKS) + HS256(fallback)**; validar `aud="authenticated"` e expiração; **nunca** emitir token. Reusar `Settings`/logging do C01. Erros de verificação retornam **401** com mensagem genérica e **sem vazar detalhe**.
4. **Mensagem de erro de login genérica** (acceptance do Backlog): falha não revela qual campo errou.
5. **Cache/CDN:** rotas que emitem `Set-Cookie` de refresh **não** podem ser cacheadas (Vercel/ISR) — defina `Cache-Control` corretamente.
6. **Estilização:** **somente CSS Modules** (sem Tailwind/framework CSS). Mobile-first; *touch targets* ≥ 44×44 px / 48 dp (RNF-013); contraste adequado.
7. **Animações:** **apenas `transform` e `opacity`** (aceleradas por GPU — DAT §5.4); **proibido** animar `width/height/top/left`. Durações vindas dos tokens (DURATION). **`prefers-reduced-motion` é obrigatório** — quando ativo, animações decorativas degradam para transição instantânea (RN-012, RNF-010). **Imersivo ≠ chamativo**: a imersão vem da coreografia de entrada e da imagem-herói, mantendo "leve, suave e sutil" (DAT §2.4).
8. **Stateless** (RNF-018): nenhum estado de sessão em memória de processo no backend.
9. **Segredos só em variáveis de ambiente**; nada sensível versionado. HTTPS/TLS é responsabilidade de Vercel/Railway/Supabase (RNF-005) — documente, não reimplemente.
10. **Custo R$ 0.**

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a sua recomendação destacada. Não comece a §5 sem as respostas.

### Bloco A — Autenticação e sessão

**DP-1 — Padrão de login e sessão.**
**[Recomendado]** login **direto frontend ↔ Supabase Auth** via `@supabase/ssr` (`signInWithPassword`), **cookies HTTP-only**, **`middleware.ts` só de refresh**; o backend apenas verifica o JWT. Confirmar (alternativa — proxy via FastAPI — não recomendada, fere a separação "backend só verifica").

**DP-2 — Esquema de assinatura do JWT e variáveis.**
Confirmar qual esquema o projeto Supabase usa: **ES256 assimétrico (default atual, via JWKS)** ou **HS256 legado (segredo)**. **[Recomendado]** implementar verificação **robusta a ambos** (lê `alg`/`kid`; ES256 via cliente JWKS com cache no `SUPABASE_JWKS_URL`; HS256 *fallback* via `SUPABASE_JWT_SECRET`). Confirmar os **nomes exatos** das variáveis a usar/adicionar e a chave pública do client (`anon` legada vs. `publishable` nova).

**DP-3 — Encerramento por inatividade (30 min, RNF-004).**
**[Recomendado]** timer de inatividade no app (reseta a cada interação; 30 min ocioso → `signOut` + redirect ao login + toast) **somado** ao TTL do access token configurado no dashboard do Supabase. Confirmar o mecanismo e **quem ajusta o TTL** no dashboard (é configuração externa ao código).

**DP-4 — Destino pós-login.**
Como ainda **não existem páginas protegidas nem dashboard**, **[Recomendado]** redirecionar para uma **landing autenticada mínima** (placeholder, ex.: `/inicio`), a ser substituída por roteamento por perfil (C05) e dashboard (C16). Confirmar a rota e o conteúdo mínimo do placeholder.

**DP-5 — "Esqueci minha senha".**
**[Recomendado]** renderizar o link conforme o design, porém **inerte/placeholder** nesta sessão (o fluxo de reset — e-mail + página de redefinição — está fora do escopo documentado do C03). Confirmar, ou decidir implementar o reset completo agora.

### Bloco B — Design e animação

**DP-6 — Fronteira C03 ↔ C19 (fundação de motion).**
**[Recomendado]** criar **agora** a fatia mínima `lib/motion/tokens.ts` (DURATION/EASING) + `useReducedMotion`, e construir as animações do login **sobre esses tokens**, para o C19 **estender** sem reescrever (evita literais inline proibidos pelo DAT §5.1). Confirmar essa fronteira.

**DP-7 — Fluxo responsivo e tela de boas-vindas.**
Confirmar o entendimento: **mobile** = tela **"Seja bem vindo!"** → botão Entrar → **formulário de login**; **desktop** = **split** direto no formulário (sem tela de boas-vindas). Confirmar as **rotas/estrutura** (ex.: `/` boas-vindas no mobile e `/login` o formulário, ou tela única adaptativa) e o **breakpoint** de corte desktop/mobile.

**DP-8 — Tokens exatos e assets (para ficar "exatamente igual").**
Fornecer os **tokens do Figma** (hex de cores, família/pesos de fonte, tamanhos, *line-height*, *border-radius*, espaçamentos) — ou o **link do arquivo Figma** (se este Claude Code tiver acesso ao Figma via Dev Mode/MCP, extraia as variáveis de lá) — em vez de derivar do PNG. Confirmar também: o **nome exato do arquivo** da imagem-herói em `apps/web/public/`, e se o **wordmark "3STUDIO"** é um **asset SVG/logo** (provável) ou texto em uma fonte específica. **Sem esses valores, não chute — pergunte.**

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; use nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida sobre localização/nome, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- `src/lib/supabase/client.ts` — **browser client** (`createBrowserClient`) estendendo a configuração mínima do C01.
- `src/lib/supabase/server.ts` — **server client** (`createServerClient`) lendo cookies via `next/headers`.
- `src/lib/supabase/middleware.ts` — helper `updateSession()` (refresh do token, escrita correta de cookies).
- `middleware.ts` (raiz de `apps/web`) — chama `updateSession()`. **Somente refresh; sem RBAC.** Comentário marcando o ponto onde o C05 acrescentará o enforcement.
- `src/lib/motion/tokens.ts` — `DURATION` e `EASING` conforme DAT §5.1; `src/lib/motion/hooks.ts` (ou equivalente) — `useReducedMotion`.
- Rotas/telas (estrutura conforme DP-7), em **CSS Modules**:
  - Tela de **login** (desktop split + mobile login) — formulário controlado, `signInWithPassword`, erro genérico, estados de carregamento, *touch targets* adequados.
  - Tela de **boas-vindas mobile** ("Seja bem vindo!") com botão Entrar.
  - **Landing autenticada placeholder** (DP-4).
- Imagem-herói referenciada de `apps/web/public/<arquivo confirmado em DP-8>`; wordmark conforme DP-8.
- **Animações locais** (sobre os tokens, GPU-only, reduced-motion-aware): entrada coreografada do bloco do formulário (fade + slide leve, *stagger* sutil entre rótulos/campos/botão), microinterações de foco dos inputs e de *hover/press* do botão, e a transição **boas-vindas → login** no mobile. Nada chamativo (DAT §2.4).

### 5.2 Backend — `apps/api/`
- Dependência de verificação de JWT (ex.: `adapters/inbound/http/auth.py` ou local idiomático): valida Bearer com **PyJWT robusto a ES256(JWKS, cache)+HS256**, valida `aud="authenticated"` e `exp`, retorna identidade (`sub`, `email`, claims). Erros → **401** genérico, log apropriado, **sem vazar detalhe**.
- Endpoint de prova `GET /auth/me` (ou equivalente): exige JWT válido e devolve a identidade verificada. **Não** faz lookup em banco nem checagem de perfil (isso é C04/C05).
- `.env.example`: variáveis de DP-2 (com comentário, sem valores reais).

### 5.3 Documentação — `docs/`
- `docs/auth.md`: arquitetura de login/sessão (`@supabase/ssr`, cookies, middleware de refresh, `getUser()` vs `getSession()`), o caminho de verificação no backend (ES256/JWKS + HS256), a regra de inatividade de 30 min, o cuidado de cache de CDN, e o **passo-a-passo de validação local**. Incluir a **checklist** dos critérios de aceitação (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Login válido concede acesso** e redireciona ao destino (DP-4). **Login inválido exibe mensagem clara e genérica**, **sem revelar qual campo falhou** (Backlog C03).
2. ✅ **Sessão inativa por mais de 30 minutos é encerrada automaticamente** (RNF-004), com retorno ao login.
3. ✅ **HTTPS/TLS** (RNF-005) — documentado (responsabilidade de Vercel/Railway/Supabase); cookies de sessão configurados de forma segura.
4. ✅ **Verificação de JWT no backend funciona** — `GET /auth/me` retorna a identidade para token válido (**ES256 via JWKS e HS256**) e **401** para token inválido/expirado/aud incorreta.
5. ✅ **Fidelidade ao design** — as três telas batem com o Figma (proporções, cores, tipografia, raios, espaçamentos, posicionamento).
6. ✅ **Animações imersivas e fluidas** na entrada e nas microinterações, **degradando para transição instantânea** com `prefers-reduced-motion` ativo (RN-012, RNF-010); apenas `transform`/`opacity`.
7. ✅ **Responsivo** ≥ 360 px, portrait e landscape, *touch targets* ≥ 44×44 px / 48 dp (RNF-013, RNF-008).
8. ✅ **Stateless** (RNF-018); **sem segredos versionados**; **custo R$ 0**.
9. ✅ `ruff`, `mypy (strict)`, `pytest`, `pnpm lint` e `pnpm build` **verdes** localmente e no CI; sem erros no console do browser.

---

## 7. Testes desta camada

**Backend**
- Verificação de JWT: token **ES256** válido (JWKS mockado) → passa; token **HS256** válido (segredo de teste) → passa; **expirado** → 401; **`aud` incorreta** → 401; **assinatura inválida** → 401; Bearer ausente/malformado → 401.
- `GET /auth/me`: identidade correta para token válido; 401 caso contrário.
- Roda **offline** (mintar tokens de teste com chave de teste / mock do cliente JWKS).

**Frontend**
- Render das três telas conforme o design (testes de componente).
- Login com sucesso (Supabase mockado) → redireciona ao destino (DP-4).
- Login com falha → **mensagem genérica** (sem distinguir e-mail vs senha).
- Inatividade: com *fake timers*, 30 min ociosos → `signOut` + redirect.
- `prefers-reduced-motion`: animações degradam para instantâneas.
- **E2E (Playwright):** caminho feliz de login, credenciais inválidas, e responsividade (≥ 360 px; *touch targets*). Sem dependência de credencial real (Supabase mockado/ambiente de teste).

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, confirme o estado das Waves 0 e a configuração Supabase existente do C01.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.** *(Não prossiga sem isso.)*
3. Backend: dependência de verificação de JWT (ES256/JWKS + HS256) + `GET /auth/me`; testes verdes.
4. Frontend: clients `@supabase/ssr` (browser/server) + `middleware.ts` de refresh; depois a fundação de motion (tokens + `useReducedMotion`).
5. Telas em CSS Modules com fidelidade ao design (DP-7/DP-8); login funcional (`signInWithPassword`, erro genérico, redirect DP-4); inatividade de 30 min (DP-3).
6. Animações locais sobre os tokens (GPU-only, reduced-motion); valide a degradação.
7. `docs/auth.md` + `.env.example`.
8. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
9. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`, descreva o que o W1-C03 entregou (login Supabase via `@supabase/ssr`, sessão em cookie + middleware de refresh, inatividade de 30 min, verificação de JWT no backend ES256/JWKS+HS256 com `/auth/me`, três telas do design, fundação mínima de motion).
2. **`DECISIONS.md`** — registre **novos ADRs** (próximos números disponíveis): (a) **arquitetura de auth/sessão** — `@supabase/ssr`, cookies HTTP-only, middleware só de refresh, proteção via `getUser()`; (b) **verificação de JWT robusta a ES256(JWKS)+HS256** — e **corrija/atualize a premissa antiga** do DAT/C01 baseada em `SUPABASE_JWT_SECRET` (HS256), registrando que o default atual do Supabase é ES256; (c) **fronteira C03↔C19 da camada de animações** (fundação mínima trazida para o C03). Ajuste status de *Proposta* → *Aceita* onde aplicável; relacione com o esquema confirmado em DP-2.
3. **`SESSION_LOG.md`** — nova entrada: objetivo, feito, **decisões tomadas (respostas dos Pontos de Decisão)**, testes/cobertura, **pendências** (ex.: reset de senha, se adiado) e **próximo passo** = **W1-C04 · Cadastro e Gestão de Usuários**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** com os comandos reais novos (rodar o frontend com auth localmente; validar `/auth/me`); registre as variáveis de auth e o padrão `@supabase/ssr`/`getUser()` onde fizer sentido. Enxuto e verdadeiro.
5. **`README.md`** — atualize setup (variáveis de auth, configuração do projeto Supabase, TTL/inatividade) e **marque o início da Wave 1** e o status do C03 no roadmap.
6. Verifique a **Definition of Done** aplicável (subconjunto do `CLAUDE.md §8`): testes, sem erro de console/log crítico, docs do módulo, error handling, animações validadas com `prefers-reduced-motion`, **sem segredos versionados**. *(RLS e migrations não se aplicam ao C03.)*
7. **Commits semânticos** (`feat(w1-c03): ...`, `chore(w1-c03): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incluindo prints/registro da fidelidade ao design e da verificação de JWT), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W1-C04**).

---

### Lembrete final
Esta é a porta de entrada de todo o sistema: precisa ser **segura, fiel ao design e fluida**, e a sessão precisa ser sólida o bastante para o **C05 (RBAC em duas camadas)** se apoiar nela sem retrabalho. A verificação de JWT tem que estar **certa para o esquema real do projeto** (ES256/JWKS hoje), senão toda a Wave 1 trava depois. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
