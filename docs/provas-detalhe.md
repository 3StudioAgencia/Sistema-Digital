# Detalhe da Prova (W2-C08)

> Tela onde a prova **se abre**: arte, metadados completos, rota e status atuais,
> ações de etiqueta (visualizar/baixar) e a seção **"Histórico de movimentações"**
> (por ora em **empty state** — a timeline rica é do C13, alimentada pelo C11).
> Página **universal** (Matriz §7), com **escopo de dado pela RLS** e
> **redirecionamento sem vazar a existência** de provas fora do escopo.
> Componentes: Backlog **C08**; RNF-001/014/016; §7; reusa C04/C06/C07.

---

## 1. Visão geral

- Rota **`/provas/[id]`** dentro do shell autenticado (C04). Cai no recurso
  **universal `provas`** da Matriz §7 (qualquer perfil ativo acessa a *página*);
  o que muda por perfil é o **escopo do dado**, garantido pela **RLS de `provas`**
  (C06, claims propagados — ADR-008). Fora do escopo / inexistente → **mesmo 404**.
- **Client component** (`ProvaDetalheView`), mesmo padrão do C07: busca via
  `apiFetch` (Bearer da sessão). O `page.tsx` (server) extrai o `id` e remonta o
  view por `key={id}` (estado fresco ao navegar entre provas).
- Reaproveita, **sem reimplementar**: etiqueta (C06), rótulos de status (C07),
  `MotionModal`/`ToastProvider`/tokens de motion (C04), `apiFetchBlob`/
  `salvarArquivo` (C06).

## 2. Endpoints (backend)

Prefixo real **`/provas`** (não `/api/provas`). Os três endpoints de leitura do
detalhe usam **`get_provas_consulta_service`** — gate **universal** `Recurso.PROVAS`
(qualquer ativo provisionado; 403 genérico anti-enumeração para sem-linha/inativo)
+ **sessão RLS fail-closed por requisição** (ADR-008/ADR-034). O escopo é da RLS:
fora do escopo a query simplesmente **não retorna** a prova.

### 2.1 `GET /provas/{id}` — detalhe

Retorna `ProvaDetalheOut`:

| campo | tipo | origem |
| --- | --- | --- |
| `id`, `codigo`, `nome`, `requerimento`, `cliente`, `vendedor_id` | str | `provas` |
| `vendedor_nome` | str \| null | `private.nomes_de_vendedores` (DP-7) |
| `rota` | enum | `provas` |
| `status` | enum (14) | `provas` |
| `ciclo_atual` | int | `provas` (DP-1 — nasce 1, incrementado pelo C15) |
| `created_at`, `finalizada_em` | datetime \| null | `provas` (`finalizada_em` populada só pelo C11) |

Prova inexistente **e** prova fora do escopo → **404 `prova_nao_encontrada`** com a
**mesma mensagem** ("Prova não encontrada.") — anti-enumeração (§11). A **arte não
vem no JSON** (ver 2.2).

### 2.2 `GET /provas/{id}/arte` — proxy da arte (DP-5)

O backend **lê o objeto do R2 privado** (`StoragePort.download`) e **streama os
bytes** com o `Content-Type` real (`image/jpeg`/`image/png`) e `Cache-Control:
private, max-age=300`. **Nunca** há URL pública nem a key do R2 chega ao cliente.
A prova é resolvida (e escopada pela RLS) **antes** de tocar o storage: fora do
escopo / inexistente → **mesmo 404**. (Alternativa considerada e rejeitada: URL
pré-assinada — exigiria novo método na `StoragePort`/boto3, é *bearer-in-URL* e
**não** serviria a etiqueta, que é gerada e não está no R2; ADR-046.)

### 2.3 `GET /provas/{id}/etiqueta.pdf` — agora universal-em-escopo (DP-8)

A etiqueta (C06) **deixou de ser admin-only**: passou do serviço de criação
(`get_provas_service`, gate admin) para o serviço universal RLS-escopado. Qualquer
perfil que **enxerga** a prova (RLS) pode visualizar/baixar a etiqueta dela —
operacionalmente correto (são os atores do fluxo físico). A **geração** (segno +
fpdf2, `EtiquetaPort`) é a mesma do C06; só mudou o *wiring/gate*. O nome do
vendedor é resolvido por `private.nomes_de_vendedores` (funciona para qualquer
perfil em escopo; fallback ASCII `-`). Não altera a Matriz §7 (etiqueta não é
recurso da Matriz — herda o escopo de linha de `provas`, como o detalhe e a arte).

## 3. Frontend

- `app/(app)/provas/[id]/page.tsx` — server fino; `await params`; `key={id}`.
- `app/(app)/provas/[id]/_components/prova-detalhe-view.tsx` — client:
  - busca `obterProva`; **404 → toast genérico + `router.replace('/provas')`**
    (DP-6, anti-enumeração); outros erros → estado de erro com *retry*.
  - **arte** via `baixarArte` → `URL.createObjectURL` num `<img>` (DP-5);
    degrada para "Arte indisponível" sem derrubar a tela.
  - **"Baixar etiqueta"** → `baixarEtiqueta` + `salvarArquivo`
    (`etiqueta-<codigo>.pdf`). **"Visualizar etiqueta"** → blob → `MotionModal`
    com `<iframe>` (DP-4).
  - **"Voltar"** → `router.back()` (preserva os filtros da listagem via histórico)
    com **fallback `/provas`** (entrada direta/refresh) — DP-6.
  - **"Histórico de movimentações"** em **empty state** (DP-2): estruturado para a
    timeline do **C13** (dados do **C11**). O C08 **não** cria nem consulta
    `movimentacoes`.
  - Animações sobre os tokens (transform/opacity), instantâneas sob
    `prefers-reduced-motion`.
- `lib/provas/rota-labels.ts` (DP-7) — módulo reutilizável (`Rota`, `ROTA_LABELS`,
  `ROTAS_ORDEM_UI`, `rotuloRota`), espelhando `status-labels.ts`. `lib/api/provas.ts`
  re-exporta para manter os imports do C06/C07. O "Rota direta" do mockup era texto
  legado — o detalhe mostra o **nome real** da rota (sem categoria derivada).
- `lib/api/provas.ts` — `ProvaDetalhe`, `obterProva`, `baixarArte`.

## 4. Migration

`0012_ciclo_atual` (aditiva, DP-1): `provas.ciclo_atual integer NOT NULL DEFAULT 1`.
Nasce 1 na criação (server default; o C06 não a informa), **incrementada pelo C15**.
`downgrade` remove a coluna. Sem índice (não é coluna de filtro/ordenação).

## 5. Testes

**Backend** (`@db`, mesma `TEST_DATABASE_URL`):
- `tests/unit/test_provas_detalhe.py` — `obter`/`obter_arte`/`gerar_etiqueta` do
  serviço de consulta (offline): nome resolvido, 404 genérico, arte antes do
  storage, fallback `-` na etiqueta.
- `tests/integration/test_provas_detalhe_endpoints.py` — escopo por perfil,
  **anti-vazamento** (fora do escopo == inexistente, mesma mensagem), `ciclo_atual`/
  `vendedor_nome`, proxy da arte (bytes + content-type), etiqueta universal-em-escopo.
- `tests/integration/test_provas_endpoints.py` — etiqueta acessível ao vendedor dono
  (DP-8). `tests/integration/test_migrations.py` — `ciclo_atual` NOT NULL no head 0012.

**Frontend**: `prova-detalhe-view.test.tsx` (render fiel, arte por proxy, 404 →
toast+redirect, baixar/visualizar etiqueta, Voltar, erro+retry). **E2E**:
`e2e/prova-detalhe.spec.ts` (proteção da rota; live suite gated por `E2E_LIVE`).

## 6. Checklist dos critérios de aceitação (§6)

- [x] Detalhe carrega < 3 s (RNF-001); exibe arte, dados completos, **rota** (DP-7),
  **ciclo atual** (DP-1), **status** (rótulo do C07).
- [x] Vendedor fora do escopo → **redirect + toast**, sem revelar se a prova existe
  (RLS → 404 idêntico ao inexistente).
- [x] Arte exibida com segurança (proxy do backend; **sem** URL pública nem key do R2).
- [x] "Baixar etiqueta" baixa o PDF do C06; "Visualizar etiqueta" abre o preview (DP-4).
- [x] "Histórico" em empty state (DP-2), estruturado para a timeline do C13.
- [x] "Voltar" preserva filtros (histórico) + fidelidade ao design + animações com
  `prefers-reduced-motion` + responsivo.
- [x] `ciclo_atual` adicionado (default 1) e exibido; migration `upgrade`/`downgrade` limpa.
- [x] Stateless; sem segredos versionados; R$ 0; `ruff`/`mypy --strict`/`pytest`/
  `pnpm lint`/`build` verdes.

## 7. Fronteira com C11/C13 (e C14/C15)

- **C11** cria `movimentacoes` + a máquina de estados e popula `finalizada_em`.
- **C13** pluga a **timeline visual** na seção de histórico (hoje em empty state).
- **C14/C15** plugam os botões **Cancelar Prova**/**Reiniciar Ciclo** (o design os
  omite — DP-3; os recursos `cancelar_prova`/`reiniciar_ciclo` já existem na Matriz,
  admin) e o **C15 incrementa `ciclo_atual`**.
