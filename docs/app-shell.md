# App Shell — layout da plataforma autenticada (W1-C04 / ADR-026)

> A sidebar preta + área de conteúdo ("shell" `#eaeaea`, raio 40px) do design
> são o layout de **toda** a plataforma autenticada. Páginas novas renderizam
> **dentro** dele sem reconstruir nada.

## 1. Estrutura

```
apps/web/src/
├── app/(app)/                       # grupo de rotas AUTENTICADAS
│   ├── layout.tsx                   # proteção (getUser) + /usuarios/me + <AppShell>
│   ├── usuarios/                    # primeira página real (W1-C04)
│   ├── dashboard/ provas/ provas/nova/ escanear/ relatorios/
│   ├── configuracoes/ informacoes/  # placeholders (DP-6) até os componentes chegarem
├── components/shell/
│   ├── AppShell.tsx                 # zonas, drawer mobile, transição de conteúdo
│   ├── Sidebar.tsx                  # nav + saudação + busca (inerte) + rodapé/Sair
│   ├── nav-items.ts                 # ITENS CANÔNICOS do menu (+ hrefAtivo)
│   └── Placeholder.tsx              # página neutra "em construção"
└── components/ui/
    ├── modal/MotionModal.tsx        # modal animado reutilizável (DAT §5.2)
    └── toast/ToastProvider.tsx      # toasts (useToast) — sucesso/erro
```

- `(app)/layout.tsx` protege no servidor com `getUser()` (nunca `getSession`),
  monta o `InactivityGuard` (30 min — C03) e o `ToastProvider`, e busca
  `GET /usuarios/me` para a saudação/rodapé. **Degrada com fallback de e-mail**
  se a API estiver fora ou o usuário não estiver provisionado — o shell nunca
  derruba a página.
- A **visibilidade por perfil** dos itens de menu e o enforcement de rota foram
  entregues no **C05**: a sidebar filtra os itens via `lib/access-matrix.ts`
  (`can`/`podeAcessarRota`) e o `proxy.ts` enforça as rotas após o refresh
  (`getClaims`), com a RLS como camada inferior; o guard do backend permanece
  como defesa em profundidade. Ver `docs/rbac.md`.

## 2. Como plugar uma página nova

1. Crie `app/(app)/minha-rota/page.tsx` — o shell envolve automaticamente.
2. Se entra no menu: adicione o item em `components/shell/nav-items.ts`
   (ícone `lucide-react`, rótulo, `href`) na posição do design.
3. Consuma `useToast()` para feedback e `MotionModal` para diálogos — não crie
   variantes próprias.
4. Tokens visuais: use as custom properties `--app-*` de `globals.css`
   (cores extraídas 1:1 do Figma) e os tokens de motion de `lib/motion/tokens.ts`.

## 3. Animações (DP-8 → ADR-028; fronteira com o C19)

Tudo via tokens (`DURATION`/`EASING`/`SPRING`), GPU-only
(transform/opacity) e **zerado** com `prefers-reduced-motion`
(`useReducedMotion`):

- Indicador do item ativo da sidebar: `layoutId` (a barra amarela desliza).
- Transição de conteúdo ao trocar de menu: fade + translateY 8px na entrada.
- `MotionModal`: entrada scale 0.96→1 + fade, saída fade (`DURATION.medium`) —
  já no contrato do `<MotionModal>` do C19, que só generaliza/documenta.
- Toasts: slide-in à direita + fade-out automático (canto inferior direito).
- Linhas da tabela: fade com stagger sutil.

## 4. Responsividade (DP-7 — breakpoint 768px)

- Sidebar → **drawer** com hambúrguer (overlay; `transform` only; fecha por
  ESC/navegação/clique fora). Topbar preta com wordmark no mobile.
- Tabela de usuários → **cards** empilhados com as mesmas ações.
- `MotionModal` → folha em tela cheia.
- Touch targets ≥ 44×44px (RNF-013).

## 5. Tokens do design (DP-9)

Extraídos por **amostragem de pixel dos exports PNG 1:1 do Figma** (o MCP do
Figma estava no limite do plano; PNG é lossless → cores exatas). Centralizados
em `globals.css`:

| Token | Valor | Uso |
| --- | --- | --- |
| `--app-shell-bg` / `--app-shell-radius` | `#eaeaea` / `40px` | área de conteúdo |
| `--app-accent` | `#ffcb5c` | ação primária (mesmo amarelo do login) |
| `--app-danger` | `#ff5959` | Desativar |
| `--app-text-gray` | `#575757` | textos de tabela/controles claros |
| `--app-field` | `#d7d7d7` | busca/filtros do conteúdo |
| `--app-divider` | `#979797` | bordas da tabela |
| `--app-overlay` | `rgba(0,0,0,.76)` | scrim do modal (medido) |
| `--app-sidebar-field` / `--app-sidebar-muted` | `#181818` / `#868686` | busca/textos da sidebar |
| `--app-control-h` / `--app-control-h-sm` | `56px` / `29px` | pills grandes / botões de linha |

Fidelidade verificada por screenshot 1920×1080 comparado pixel a pixel com o
export do Figma (cores idênticas; scrim `#343434` vs `#333333` por
antialiasing/compositing — dentro da tolerância).

## 6. Notas

- A **busca da sidebar é inerte** (campo fiel ao design, `disabled`): o alvo
  (busca global de provas) só existe a partir da Wave 2.
- `/` e `/inicio` redirecionam para `HOME_PADRAO` (`/dashboard`) — a home do
  perfil definida no C05 (● a todos na Matriz §7; ADR-030/W1-A-003).
- A wordmark reutiliza `src/assets/logo-3studio.svg` (C03) — **importada e renderizada via `next/image`** (`<Image>`); movida de `public/` para `src/assets/` (ADR-106); ícones: `lucide-react`.
