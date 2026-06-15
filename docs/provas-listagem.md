# Listagem de Provas (W2-C07)

> Tela de **operação diária**: listar/buscar/filtrar provas com paginação
> server-side, respeitando o **escopo por perfil** (Matriz §7) na UI e na RLS.
> Fonte da verdade do escopo: a **RLS de `provas`** (C06). A UI só **adapta** o
> que faz sentido mostrar. Componentes: Backlog **C07**; RF-013/RF-014/US-012;
> RNF-001/019/023.

---

## 1. Visão geral

- Página **universal** (Matriz §7: `provas` é acessível a qualquer perfil ativo)
  — **não** gateada a admin. O que muda por perfil é o **escopo dos dados**:
  3Studio/Clicheria/Admin veem **todas**, Vendedor **as suas**, Motorista as
  **"Em Trânsito"** — garantido pela RLS (claims propagados — ADR-008).
- Tabela **replicada** do Gerenciador de Usuários (C04 / DP-1 — ADR-041): mesmo
  card/colunas/scroll/pílulas, parametrizada para as colunas de provas e a ação
  **"Ver"**. Sem `<DataTable>` genérico (decisão do dono: replicar, não extrair).
- **Estado de filtros na URL** (DP-5 / ADR-042): refresh-safe e compartilhável;
  paginação por **scroll infinito** server-side (mesmo padrão do C04).

## 2. Endpoint — `GET /provas`

Prefixo real **`/provas`** (não `/api/provas`). Dependência
`get_provas_consulta_service` (sessão RLS fail-closed por requisição; gate
universal `Recurso.PROVAS` — qualquer ativo provisionado; 403 genérico
anti-enumeração para sem-linha/inativo).

**Query params** (todos opcionais, combináveis — AND):

| Param | Tipo | Efeito |
| --- | --- | --- |
| `busca` | str | nome **OU** requerimento (ILIKE, curingas escapados) — RF-013 |
| `cliente` | str | cliente contém (ILIKE) |
| `status` | enum | um dos 14 `status_prova_enum` (valor inválido → 422) |
| `rota` | enum | `matriz`/`lam_matriz`/`filial`/`lam_filial` |
| `vendedor_id` | uuid | filtra por vendedor |
| `criada_de` / `criada_ate` | date | intervalo de `created_at` (limite de dia inclusivo) |
| `finalizada_de` / `finalizada_ate` | date | intervalo de `finalizada_em` (exclui NULL) |
| `page` | int ≥1 | página (default 1) |
| `page_size` | int 1..100 | itens por página (default 20; teto RNF-019) |

> O **"Criada em"/"Finalizada em"** do design é um **único dia**: o frontend
> manda `..._de = ..._ate = <dia>`, e o backend cobre o dia inteiro
> (`>= dia` e `< dia+1`), mantendo o uso dos índices.

**Resposta** `200` (`PaginaProvasOut`), ordenada por `created_at desc, id`:

```json
{
  "items": [
    {
      "id": "…", "codigo": "PRV-2026-04-AAAAAA", "nome": "…",
      "requerimento": "123456", "cliente": "Moacyr",
      "vendedor_id": "…", "vendedor_nome": "Regiane",
      "rota": "matriz", "status": "cancelada",
      "created_at": "2026-04-09T12:00:00Z", "finalizada_em": null
    }
  ],
  "total": 42, "page": 1, "page_size": 20
}
```

- **Consulta única e eficiente** (sem N+1 — RNF-022): contagem + página na mesma
  sessão; o **nome do vendedor** é resolvido **uma vez por página** (não por
  linha) e nunca dispara N+1.
- Query **fora do escopo → 0 registros** (a RLS filtra; a borda não distingue
  "não existe" de "sem permissão").

## 3. `GET /provas/vendedores` — dropdown escopado

Lista `{id, nome}` dos vendedores **distintos** presentes nas provas **visíveis
ao ator** (RLS), ordenados por nome. Para 3Studio/Clicheria/Admin = todos os
vendedores com provas; para Vendedor = só ele (e o filtro nem aparece — DP-2).

## 4. Resolução do nome do vendedor (DP-7 / ADR-045)

A coluna/dropdown **Vendedor** mostra o **nome**, mas `provas` guarda só
`vendedor_id`. A RLS de `usuarios` (C05) só deixa **admin/self** lerem outras
linhas — um **3Studio/Clicheria não-admin** ou um **Motorista** (que veem provas
de vários vendedores) não conseguiriam resolver o nome num JOIN. Solução **sem
ampliar a Matriz §7**: a função **`public.nomes_de_vendedores(uuid[]) → (id,
nome)`** (migration `0010`, espelho em `migrations/rls/nomes_de_vendedores.sql`):

- **SECURITY DEFINER** (roda como owner → vê todas as linhas), `SET search_path
  = ''`, corpo schema-qualificado (blindagem W1-A-004);
- projeta o **mínimo**: só `id`+`nome`, **só de vendedores** (`setor='vendedor'`);
- `EXECUTE` revogado de `PUBLIC` e concedido só a `authenticated`.

## 5. Escopo por perfil — UI × RLS

| Perfil | Vê (RLS) | Filtro "Vendedor" na UI |
| --- | --- | --- |
| 3Studio / Clicheria | todas | aparece |
| Admin (qualquer setor) | todas | aparece |
| Vendedor (não-admin) | as suas | **escondido** (escopo "as próprias") |
| Motorista | as "Em Trânsito" | aparece |

A UI deriva o escopo de `usuario.setor`+`administrador` (`escopoDeProvas`, DP-2)
**apenas para adaptar a barra** — o escopo real é da RLS, no servidor.

## 6. Rótulos de status (DP-4 / ADR-043)

Módulo reutilizável `apps/web/src/lib/provas/status-labels.ts`
(`STATUS_PROVA_LABELS`, `STATUS_PROVA_ORDEM`, `rotuloStatus`) — um rótulo curto
por estado, cobrindo os **14** (o filtro lista todos + "Todos"). C08/C13/C16
reusam.

## 7. `finalizada_em` (DP-3 / ADR-044)

Coluna `timestamptz NULL` (migration `0010`, índice parcial
`ix_provas_finalizada_em`), **populada pelo C11** nas transições terminais. O C07
só **lê e filtra**; até o C11, o filtro "Finalizada em" retorna vazio (as provas
ainda não têm carimbo) — comportamento documentado, não bug.

## 8. Frontend

- `app/(app)/provas/page.tsx` (server): resolve o **escopo** e monta
  `<ProvasView>` sob `<Suspense>` (usa `useSearchParams`).
- `app/(app)/provas/_components/provas-view.tsx`: barra de filtros (busca/cliente
  com debounce ≥300ms → URL; status/rota/vendedor/datas → URL imediata; "Limpar"
  zera a query), tabela replicada + cards no mobile, scroll infinito, estados de
  loading/vazio/erro, animações sobre os tokens (transform/opacity,
  `prefers-reduced-motion`).
- `"Ver"` → `/provas/{id}` (placeholder C08 até o detalhe — DP-6).

## 9. Testes

- **api** (`tests/integration/test_provas_listagem_endpoints.py`, @db): escopo
  por perfil (incl. **3Studio não-admin e Motorista resolvendo o nome** — DP-7),
  filtros combináveis, busca por nome/requerimento, períodos, paginação +
  ordenação, **sem N+1** (contador de SELECTs), dropdown escopado, 401/403.
  `tests/unit/test_provas_listagem.py`: serviço (resolução de nomes 1×/página) +
  saneamento dos filtros. `tests/integration/test_migrations.py`: 0010 up/down.
- **web** (`provas-view.test.tsx`): render fiel, debounce, hidratação da URL,
  filtro→URL, adaptação por perfil, "Limpar", "Ver", vazio/erro/403.
- **e2e** (`provas-listagem.spec.ts`): proteção da rota (offline) + fluxo live.

## 10. Checklist de aceitação (§6 do prompt)

- [x] Filtros combináveis; escopo respeitado em UI **e** RLS; fora do escopo → 0.
- [x] Busca com debounce ≥300ms (nome **e** requerimento).
- [x] Paginação server-side com teto; sem N+1; índices do C06.
- [x] Tabela idêntica à do C04; barra fiel ao design; ação "Ver".
- [x] "Limpar" reseta; filtros na URL (refresh-safe/compartilhável).
- [x] Loading/vazio/erro; animações com `prefers-reduced-motion`; responsivo.
- [x] Stateless; sem segredos versionados; R$ 0; `ruff`/`mypy`/`pytest`/`lint`/`build` verdes.
