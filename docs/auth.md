# Autenticação e Sessão (W1-C03)

> Arquitetura de login/sessão do Rastreio de Provas Digitais. Fonte de verdade da
> autenticação: **Supabase Auth** (emite e renova o JWT). O backend FastAPI
> **apenas verifica** a assinatura (PyJWT — nunca emite). Ver ADR-018 e ADR-019.

---

## 1. Visão geral do fluxo

```
            (e-mail + senha)                      cookies HTTP-only
 Browser ───────────────────────► Supabase Auth ───────────────────► Browser
   │   signInWithPassword (@supabase/ssr)   (emite access+refresh JWT)
   │
   │  navega para /inicio
   ▼
 Next.js (proxy.ts)  ── a cada navegação ──► supabase.auth.getUser()  (refresh)
   │
   │  AuthProof envia o access token (Bearer)
   ▼
 FastAPI  GET /auth/me ──► verifica a assinatura do JWT (ES256/JWKS + HS256),
                            valida aud="authenticated" e exp → identidade.
```

- **Login**: direto **Frontend ↔ Supabase Auth** via `@supabase/ssr`
  (`signInWithPassword`). O backend **não** intermedia o login (DP-1).
- **Sessão**: **stateless**, no JWT, guardada em **cookies HTTP-only** geridos
  pelo trio de clients `@supabase/ssr` (browser + server + proxy). RNF-018.
- **Backend**: stateless; só **verifica** o Bearer JWT e devolve a identidade.

---

## 2. Frontend (`apps/web`)

### Clients `@supabase/ssr` (substituem o `@supabase/auth-helpers`, deprecado)

| Arquivo | Papel |
| --- | --- |
| `src/lib/supabase/env.ts` | Lê/valida `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_ANON_KEY`. |
| `src/lib/supabase/client.ts` | **Browser** (`createBrowserClient`) — singleton por aba. |
| `src/lib/supabase/server.ts` | **Server** (`createServerClient`) — lê cookies via `next/headers`. |
| `src/lib/supabase/middleware.ts` | `updateSession()` — refresh do token + reescrita dos cookies. |
| `src/proxy.ts` | Convenção do App Router (Next 16) — chama `updateSession`. **Só refresh.** |

### Regras críticas

- **Proteção sempre com `supabase.auth.getUser()`** (valida no servidor de auth),
  **nunca `getSession()`** (que só lê o cookie, sem revalidar) — prompt §3.2.
- O `proxy.ts` (sucessor do `middleware.ts` no Next 16) **só faz refresh** nesta
  wave. O **enforcement de RBAC** (camada superior, CLAUDE.md §5.4) entra no
  **W1-C05**, lendo `lib/access-matrix.ts`. Ver ADR-021.
- **Cache/CDN (Vercel):** respostas que escrevem `Set-Cookie` de refresh **não**
  podem ser cacheadas (ISR/CDN serviria a sessão de um usuário a outro). O
  `updateSession` aplica `Cache-Control: no-store`; o `matcher` do proxy exclui
  assets estáticos. Prompt §3.5.

### Telas (DP-7)

- `/bem-vindo` — **mobile**: boas-vindas (hero + "Seja bem vindo!" + Entrar). No
  **desktop** encaminha para `/login` (a tela é mobile-only).
- `/login` — **adaptativa**: desktop = split (imagem-herói + formulário);
  mobile = formulário em coluna. `signInWithPassword`, **erro genérico** (não
  revela qual campo falhou), estados de carregamento.
- `/inicio` — landing autenticada **placeholder** (DP-4). Protegida por `getUser()`;
  monta o guarda de inatividade e a prova `AuthProof` (chama `/auth/me`).
- `/` — autenticado → `/inicio`; senão → `/bem-vindo`.

### Encerramento por inatividade (30 min — RNF-004 / DP-3)

`src/app/_components/inactivity-guard.tsx`: um timer reinicia a cada interação
(mousemove/keydown/scroll/touch/click). Ao expirar (30 min), faz `signOut` e volta
ao `/login?expirado=1` — onde um aviso discreto é exibido (sem antecipar o Toaster
global do C19). **Complementar** ao TTL do access token no dashboard do Supabase
(ver §5). Montado nas páginas autenticadas (por ora `/inicio`; o C05 levará para um
layout autenticado compartilhado).

### Animações (DP-6)

Fundação mínima em `src/lib/motion/` (`tokens.ts` = DAT §5.1; `hooks.ts` =
`useReducedMotion`). As animações do login (entrada coreografada, hover/press)
usam **Framer Motion sobre os tokens**, **só `transform`/`opacity`** (GPU), e
degradam para instantâneas com `prefers-reduced-motion`. O C19 estende. Ver ADR-020.

---

## 3. Backend — verificação de JWT (`apps/api`)

`src/adapters/inbound/http/auth.py`:

- **`JwtVerifier`** verifica de forma robusta ao esquema real do projeto:
  - **ES256/RS256 via JWKS** (assimétrico) com cache (`PyJWKClient`) — **o default
    atual do Supabase é ES256** (confirmado no projeto real `wmpxxrzbzqgsorjwczvz`);
  - **HS256** (segredo legado) como **fallback** opcional.
  - O algoritmo é escolhido pelo header e validado contra lista explícita — nunca
    `none`, sem confusão de algoritmo (chave pública só para assimétrico; segredo
    só para HS256).
  - Valida **assinatura**, **`aud="authenticated"`** e **`exp`**.
- Qualquer falha → **401 genérico** (`WWW-Authenticate: Bearer`), sem revelar a
  causa; o motivo fica no log estruturado (só o **tipo** da exceção, nunca o token).
- **`GET /auth/me`** — exige Bearer válido e devolve `{ sub, email, role }`. É a
  **prova demonstrável** do caminho de verificação. **Não** consulta o banco nem
  checa perfil (isso é C04/C05).

A verificação é síncrona (CPU + JWKS via urllib, cacheado) e roda em threadpool
para não bloquear o event loop. Ver ADR-019.

### Variáveis (`apps/api/.env.example`)

| Variável | Papel |
| --- | --- |
| `SUPABASE_URL` | URL do projeto; deriva o JWKS quando `SUPABASE_JWKS_URL` está vazio. |
| `SUPABASE_JWKS_URL` | JWKS do projeto (ES256). Opcional — default: `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`. |
| `SUPABASE_JWT_SECRET` | Segredo HS256 legado — **fallback** opcional (projetos ES256 não precisam). |

---

## 4. HTTPS/TLS (RNF-005)

Responsabilidade do edge (Vercel / Railway / Supabase) — não reimplementado na
app. Cookies de sessão do `@supabase/ssr` são `HttpOnly`/`SameSite`/`Secure`
(em produção, via HTTPS).

---

## 5. Ação externa do responsável — TTL do access token (DP-3)

O tempo de vida do access token é configuração **do dashboard** do Supabase
(Authentication → Sessions / JWT expiry), não do código. Recomendado alinhar a um
valor curto (ex.: 30–60 min) coerente com a regra de inatividade. **Responsável:
Mario.** O timer de inatividade do app é a camada de UX; o TTL é a camada de token.

---

## 6. Validação local

```bash
# Backend — verificação de JWT (offline; mintando tokens de teste)
cd apps/api
uv run pytest tests/unit/test_auth.py tests/integration/test_auth_me.py -v
uv run ruff check . && uv run mypy

# Subir a API e provar /auth/me com um token real do Supabase:
uv run uvicorn src.main:app --reload          # http://localhost:8000/docs
#  curl -H "Authorization: Bearer <ACCESS_TOKEN>" http://localhost:8000/auth/me
#  → 200 { "sub": "...", "email": "...", "role": "authenticated" } com token válido
#  → 401 genérico com token inválido/expirado/aud incorreta

# Frontend — telas + fluxo
cd ../web
pnpm dev                                       # http://localhost:3000
pnpm test                                      # vitest (componentes/lógica)
pnpm test:e2e                                  # Playwright (telas, responsivo, erro genérico)
```

> **Caminho feliz E2E autenticado**: requer sessão **real** (a checagem `getUser`
> do servidor não é interceptável por route mock), API rodando e um usuário
> semeado. Fica atrás de `E2E_LIVE=1` (+ `E2E_EMAIL`/`E2E_PASSWORD`); a lógica de
> sucesso já é coberta pelo teste de componente de `LoginPanel`.

---

## 7. Checklist dos critérios de aceitação (§6 do prompt)

- [x] Login válido entra e redireciona ao destino (`/inicio`); login inválido →
      **mensagem clara e genérica**, sem revelar o campo.
- [x] Sessão inativa > 30 min é encerrada automaticamente (volta ao login).
- [x] HTTPS/TLS documentado (responsabilidade do edge); cookies seguros.
- [x] Verificação de JWT no backend funciona — `/auth/me` 200 para token válido
      (**ES256 via JWKS** e **HS256**) e **401** para inválido/expirado/aud errada.
- [x] Fidelidade ao design (3 telas; tokens extraídos do Figma) — evidência em
      screenshots do Playwright.
- [x] Animações imersivas e fluidas, degradando para instantâneas com
      `prefers-reduced-motion`; só `transform`/`opacity`.
- [x] Responsivo ≥ 360 px; *touch targets* ≥ 44 px (teste E2E).
- [x] Stateless; sem segredos versionados; custo R$ 0.
- [x] `ruff`/`mypy`/`pytest`/`pnpm lint`/`pnpm build`/`vitest`/Playwright verdes.
