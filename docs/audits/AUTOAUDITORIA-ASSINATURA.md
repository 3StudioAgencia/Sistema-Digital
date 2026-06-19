# Auto-auditoria — Redesign da tela de assinatura (frontend-only)

> **Sessão:** 26 — 2026-06-19 · **Tipo:** redesign de UX **fora do backlog** (re-skin do frontend da tela de assinatura do C12) · **ADR:** ADR-096
> **Regra dominante:** escopo travado ao **frontend da tela de assinatura**; comportamento do C12 **preservado integralmente**. Esta auditoria **prova** o escopo (via `git diff`) e a não-regressão (via suíte verde).

---

## 1. Escopo (prova por `git diff`)

`git diff --stat` (apenas arquivos versionados tocados nesta sessão):

```
apps/web/src/app/(app)/provas/[id]/confirmar/_components/assinatura-pad.tsx        |  27 +-
apps/web/src/app/(app)/provas/[id]/confirmar/_components/confirmar-view.test.tsx   |  12 +-
apps/web/src/app/(app)/provas/[id]/confirmar/_components/confirmar-view.tsx        | 184 +++++++----
apps/web/src/app/(app)/provas/[id]/confirmar/confirmar.module.css                  | 367 ++++++++++++-------
4 files changed
```

**Todos os 4 arquivos pertencem ao frontend da própria tela de assinatura** (`apps/web/src/app/(app)/provas/[id]/confirmar/`):

- `_components/confirmar-view.tsx` — componente da tela (marcação re-estruturada).
- `confirmar.module.css` — CSS Module **da tela** (re-skin).
- `_components/assinatura-pad.tsx` — wrapper **local** do `react-signature-canvas` (vive na pasta da própria tela — não é compartilhado).
- `_components/confirmar-view.test.tsx` — teste **da própria tela** (atualizado só pelo rótulo do botão).

✅ **Nenhum arquivo fora da tela de assinatura foi alterado.** Backend, migrations, RLS, componentes compartilhados (app shell, `MotionModal`, `ToastProvider`, tokens em `globals.css`/`motion/tokens.ts`), e demais telas: **intactos**. Os `PROMPTS/*.md` que aparecem em `git status` são **pré-existentes** (não rastreados antes desta sessão), não foram criados aqui.

> **Nota de escopo (E2E):** `apps/web/e2e/confirmar.spec.ts` **não foi tocado**. Ele localiza o botão por `getByRole("button", { name: "Confirmar" })`; o Playwright casa **substring case-insensitive**, então "Confirmar" continua casando "Confirmar assinatura" — o E2E permanece verde **sem edição** (e está `test.skip` sem `E2E_LIVE`). Só o teste unitário (RTL, casamento exato) exigiu o ajuste de rótulo.

---

## 2. Decisões (Pontos de Decisão §4 — respondidas pelo dono antes de codificar)

- **DP-1 (Reprovar):** Reprovar = **botão de perigo no rodapé**, ao lado de Confirmar. **Mesmo comportamento** — clicar revela o **campo de motivo obrigatório** e o passo "Confirmar reprovação".
- **DP-2 (metadados):** **sem nova busca** — os 6 campos (Cliente/Vendedor/Rota/Ciclo/Criada em/Status) **já vinham** no `ProvaDetalhe` que a tela carrega; nada novo no backend.
- **DP-3 (compartilhados):** tudo **local** à tela (estilos + afford); **nenhum** componente compartilhado tocado.
- **DP-4 (Cancelar):** "Cancelar" = **abandonar e voltar** (mesma navegação do "Voltar" do topo).
- **DP-5 (canvas/PNG):** **fiel ao design** — canvas **transparente** com guias (X + linha + legenda) ATRÁS; o PNG exportado passou de fundo **branco** → **transparente** (traço escuro idêntico; mudança cosmética no artefato, conteúdo intacto).

---

## 3. Comportamento preservado (§0.2) — verificado por teste

A suíte unitária da tela (`confirmar-view.test.tsx`, **8/8 verdes**) cobre o contrato e **continua passando**:

| Invariante do C12 | Cobertura |
| --- | --- |
| Captura do traço (`react-signature-canvas`) + validação "assinou" | `canvas vazio → bloqueia o envio` ✅ |
| Submissão invoca a transição do C11 (atômica/idempotente) | `assinatura + Confirmar → invoca a transição` ✅ |
| Variante Aprovar/Reprovar; **Reprovar exige motivo** | `Aprovar/Reprovar; Reprovar exige motivo` + `Aprovar envia aprovar` ✅ |
| Anti-enumeração (404 genérico; bloqueio sem revelar o ator) | `não é a vez do ator → bloqueio genérico` + `404 na carga → toast genérico` ✅ |
| Resiliência (RNF-016): preserva traço + retry com **a mesma** `idempotency_key` | `falha de rede preserva o traço e oferece retry com a MESMA chave` ✅ |
| "Limpar" (limpar o traço) | preservado como link discreto no cabeçalho do bloco de assinatura |
| ≤ 3 toques / mobile-first / `prefers-reduced-motion` | preservados (base mobile-first; animações só `transform`/`opacity` zeradas por `useReducedMotion`) |

Nada da **lógica** (submissão, transição, anti-enum, resiliência, idempotência) foi alterado — apenas marcação/estilo e o **rótulo** "Confirmar" → "Confirmar assinatura".

---

## 4. Não-regressão (suíte + gates)

| Verificação | Resultado |
| --- | --- |
| Vitest — tela de assinatura | **8/8 verdes** |
| Vitest — suíte web inteira | **27 arquivos · 179 testes verdes** |
| `pnpm lint` (eslint) | **exit 0** (sem achados) |
| `pnpm format:check` (prettier) | **All matched files use Prettier code style!** |
| `pnpm build` (next build + TypeScript) | **exit 0** — `/provas/[id]/confirmar` compila, TS limpo |

Backend (`ruff`/`mypy`/`pytest`) **não foi tocado** e portanto **não regrediu** (nenhum arquivo de api no diff).

---

## 5. Fidelidade ao design (§0.3 / §6.1)

- ✅ "← Voltar" (pill, topo).
- ✅ Título = nome da prova + **badge "Requerimento: {nº}"** (pílula cinza-clara).
- ✅ Divisor + linha de metadados em colunas: **Cliente · Vendedor · Rota · Ciclo · Criada em · Status** (rótulo em cima, valor embaixo).
- ✅ Rótulo **"Assinatura Digital"**.
- ✅ Caixa de assinatura cinza-clara com **"X" + linha** próxima à base e legenda **"Assine no espaço acima da linha"** (guias atrás do canvas transparente).
- ✅ Rodapé: ícone de info + **"Ao confirmar, você aprova as cores da prova digital"** (esquerda) · **Cancelar** (contorno) + **Confirmar assinatura** (escuro, com check) (direita).
- ✅ Variantes preservadas: Reprovar (perigo no rodapé) → motivo obrigatório → "Confirmar reprovação"; bloqueio genérico quando não é a vez do ator.

Verificação visual fina (pixels) sugerida pelo dono no app rodando — a fidelidade aqui foi conferida no nível de marcação/CSS contra a imagem do design.

---

## 6. Sem novas dependências / chamadas

- ✅ Nenhuma lib nova (os ícones info/check são **SVG inline locais**).
- ✅ Nenhuma nova chamada de API / busca de dados (metadados já presentes — DP-2).

---

## 7. Veredito

**APROVADO.** Escopo respeitado (diff contido em `confirmar/`), comportamento do C12 preservado (suíte verde), fidelidade ao design atingida, sem regressão e sem dependências/chamadas novas.
