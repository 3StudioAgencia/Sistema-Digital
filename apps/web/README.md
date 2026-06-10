# apps/web — Frontend Next.js

Frontend do Sistema de Rastreio de Provas Digitais. **Next.js 16 (App Router)** ·
**TypeScript strict** · **CSS Modules** (sem framework CSS externo) · gerenciado
por **pnpm** (ADR-010).

## Comandos

```bash
pnpm install          # dependências (lockfile pinado)
pnpm dev              # dev server → http://localhost:3000
pnpm build            # build de produção
pnpm lint             # ESLint (flat config + next/core-web-vitals + ts)
pnpm format:check     # Prettier
```

## O que existe nesta wave (W0-C01)

- **Página de status** (`src/app/page.tsx`): confirma o build e consulta o
  readiness da API (`/health/ready`) **uma única vez, sem polling** (RNF-020/021),
  com fallback amigável quando a API não está configurada/acessível.
- **Client Supabase mínimo** (`src/lib/supabase/client.ts`): somente
  configuração, lazy e singleton. **Sem lógica de auth** — login/sessão chegam
  na Wave 1/C03 (com `@supabase/ssr` para o lado servidor).
- Variáveis de ambiente documentadas em `.env.example` (`NEXT_PUBLIC_*` são
  públicas por design; a proteção dos dados é a RLS).

## Reservado para waves futuras (NÃO criar antes — CLAUDE.md §5)

| Caminho                    | Wave  | Conteúdo                                           |
| -------------------------- | ----- | -------------------------------------------------- |
| `src/middleware.ts`        | 1/C05 | Middleware RBAC (camada superior)                  |
| `src/lib/access-matrix.ts` | 1/C05 | Matriz determinística `{ rota: [perfis, escopo] }` |
| `src/lib/motion/tokens.ts` | 6/C19 | Tokens de animação (`DURATION`, `EASING`)          |
