# RBAC — Controle de Acesso por Perfil (W1-C05)

> Componente de **segurança** que fecha a Wave 1. A **Matriz de Acesso §7**
> (Requisitos v1.0) é a **fonte única**; este documento descreve como ela é
> aplicada em **duas camadas independentes** (defesa em profundidade) e como o
> C06 estende a camada de dados para `provas`.

## 1. Modelo de perfil (ADR-023 — ortogonal)

`usuarios.setor ∈ {studio, vendedor, motorista, clicheria}` = **escopo
operacional** (um por usuário, RN-009). `usuarios.administrador` (boolean) =
**flag de perfil**, ortogonal ao setor (um Vendedor pode ser Admin).

Releitura da Matriz §7 sob este modelo:

| Recurso (página/ação) | Quem acessa | Chave |
| --- | --- | --- |
| Dashboard · Escanear · Listagem/Detalhe/Timeline de Provas | qualquer autenticado (●/◐) | universal |
| Criar Prova · Cadastro de Usuários · Relatórios · Configurações · Log de Auditoria · Reiniciar Ciclo · Cancelar Prova | só Admin (○ p/ demais) | flag `administrador` |

> O **escopo de dado** das células ◐ (Vendedor vê as próprias provas; Motorista
> as "Em Trânsito") é **RLS de linha sobre `provas`**, aplicada no **C06** com os
> helpers desta wave (§6). Para `usuarios`, o escopo de dado já é RLS no C05 (§4).

A Matriz canônica de página vive em **`apps/web/src/lib/access-matrix.cells.json`**
(`"todos"` | `"admin"` por recurso) e trava as duas implementações (§5).

## 2. Camada superior — Proxy do App Router

`apps/web/src/proxy.ts` → `apps/web/src/lib/supabase/middleware.ts`
(`updateSession`). Após o refresh de sessão (C03):

1. `getUser()` valida a sessão no servidor de auth (mantém o refresh seguro);
2. `getClaims()` lê os claims de perfil em **verificação LOCAL** (chave
   assimétrica) — **não bate no auth server por request** (pilar de mínimo de
   requisições);
3. `podeAcessarRota(perfil, pathname)` decide pela `access-matrix.ts`;
4. acesso negado → **302 para `/dashboard`** (home ● a todos) preservando os
   cookies de refresh + cookie efêmero **`rbac_negado`**; o componente
   `RbacFlash` (`apps/web/src/app/_components/rbac-flash.tsx`, montado no layout
   autenticado) lê/limpa o cookie e dispara o **toast** de acesso negado.

A UI consome a MESMA Matriz: a **sidebar** (`components/shell/Sidebar.tsx`)
filtra os itens por perfil via `podeAcessarRota`; o helper **`can(perfil,
recurso)`** é o padrão de gating de ações que C06/C08/C14 reutilizam (Criar
Prova / Cancelar / Reiniciar).

## 3. Custom Access Token Hook (claims no JWT)

Migration **`0004_custom_access_token_hook.py`** cria
`public.custom_access_token_hook(event jsonb) returns jsonb`. Roda **antes de
cada emissão de token** (login e refresh) e **eleva ao nível superior** dos
claims o que a RLS lê:

- `user_id` = `sub` (UUID de `auth.users`);
- `setor` = `app_metadata.setor`;
- `administrador` = `app_metadata.administrador` (default `false`).

**Fonte = `app_metadata` já presente no `event.claims`** (DP-2 / opção B): o
Supabase injeta `app_metadata` no evento, e o C04 já o mantém sincronizado
(ADR-025/027). O hook **não lê a tabela `usuarios`** → rápido, `SECURITY
INVOKER` + `SET search_path = ''`, **nunca quebra a autenticação** por RLS/lock;
e **dispensa** grant de leitura ao `supabase_auth_admin`. Preserva todos os
claims obrigatórios; conta sem `app_metadata` emite token sem `setor` e com
`administrador=false` (menor privilégio, sem enumeração).

**Grants** (na migration, condicionados à existência das roles): `execute` só a
`supabase_auth_admin` + `usage` no schema; `execute` revogado de
`authenticated`/`anon`/`public`.

**Hardening de `search_path`** (W1-A-004): o hook e os 4 helpers de RLS fixam
`SET search_path = ''` (advisor `function_search_path_mutable`). Seguro porque os
corpos só usam built-ins de `pg_catalog` e chamadas já `public.`-qualificadas. As
migrations `0004`/`0005` criam endurecido; a `0006` aplica o `ALTER` no banco já
migrado (editar migration aplicada não a reexecuta).

### Registro do hook (passo de projeto, fora do SQL)

A função é criada pelo Alembic em qualquer banco-alvo, mas **habilitar** o hook é
config de projeto:

- **Dashboard:** Authentication → Hooks → *Customize Access Token (JWT) Claims* →
  apontar para `public.custom_access_token_hook`.
- **CLI/`config.toml`** (quando houver Supabase local):
  ```toml
  [auth.hook.custom_access_token]
  enabled = true
  uri = "pg-functions://postgres/public/custom_access_token_hook"
  ```
  *(Hoje o dev usa Supabase remoto; não há `supabase/config.toml` no repo.)*

## 4. Camada inferior — RLS de `usuarios` (definitiva)

Migration **`0005_rls_usuarios_e_helpers.py`** + espelho em
`apps/api/migrations/rls/*.sql` (regra do DAT §2). Substitui a postura restritiva
do C04 (DP-6 / **opção 6-A**):

- **Grants:** `authenticated` ganha `SELECT/INSERT/UPDATE/DELETE`; `anon` sem
  acesso.
- **Policies:** `usuarios_select_self` (cada um lê a própria linha — alimenta
  `/me`); `usuarios_select_admin` + `usuarios_{insert,update,delete}_admin` (flag
  `administrador`).
- **Helpers reutilizáveis** (`_helpers.sql`): `app_current_claims()`,
  `app_setor()`, `app_is_admin()`, `app_current_user_id()` — leem
  `request.jwt.claims` (o mesmo conteúdo que `auth.jwt()` expõe no Supabase),
  **portáteis** (não dependem do schema `auth`). O **C06 compõe a RLS de
  `provas` sobre eles** (§6).
- **Roles stand-in** (`_roles.sql`): cria `anon`/`authenticated` se ausentes
  (no-op no Supabase; viabiliza `CREATE POLICY TO authenticated` em Postgres
  limpo — DoD §8).

### Propagação de claims (ADR-008)

`SqlAlchemyUnitOfWork` não basta (leituras auto-iniciam transações). Em
`src/infrastructure/database.py`, **`propagar_claims_rls(session, claims)`** anexa
um listener `after_begin`: em **toda transação** (leitura ou escrita) executa
`set_config('request.jwt.claims', <json>, true)` + `SET LOCAL ROLE
authenticated`. Ligado por requisição em `get_usuarios_service`
(`dependencies.py`) com os claims do JWT verificado. Resultado: **as consultas
servidas pelo FastAPI respeitam a RLS** (sem isso, a conexão *owner* faria
bypass). Por transação (`SET LOCAL`) → seguro com o pooler em modo transação
(ADR-007).

A autorização de **recurso** no backend é a dependência reutilizável
**`requer_acesso(Recurso)`** (`dependencies.py`), generalização do guard de admin
do C04, alinhada à Matriz (`domain/rbac.py`). `get_admin_corrente =
requer_acesso(Recurso.CADASTRO_USUARIOS)`.

## 5. Equivalência das camadas + regra do PR único

`access-matrix.cells.json` é a **fonte única** de página. Dois testes a travam:

- **web** — `src/lib/access-matrix.equivalencia.test.ts`: `can()` ⇔ JSON.
- **api** — `tests/unit/test_equivalencia_matriz.py`: `autorizar()` ⇔ JSON.

Como ambas concordam com o mesmo arquivo, **concordam entre si**. As células de
**dado** de `usuarios` (admin lê todas; não-admin 0 alheias) são verificadas em
`tests/integration/test_rls_usuarios.py` e `test_claims_propagation.py`.

> **Regra do PR único (DAT §7.3 / CLAUDE.md §5.4):** toda mudança na Matriz exige
> **um único PR** cobrindo `access-matrix.cells.json`, `access-matrix.ts`,
> `domain/rbac.py` **E** as migrations de RLS em `apps/api/migrations/rls/`.
> Nunca só um lado.

## 6. Fronteira C05 → C06 (RLS de `provas`)

`provas` **não existe** no C05 — é criada no **C06**. Lá, a RLS de linha
(`provas_select_vendedor.sql`, `provas_select_motorista.sql`, etc., padrão DAT
§7.2) é escrita **sobre os helpers desta wave**:

```sql
-- C06 (exemplo): vendedor vê apenas as próprias provas
CREATE POLICY provas_select_vendedor ON provas FOR SELECT TO authenticated
  USING (app_setor() = 'vendedor' AND vendedor_id = app_current_user_id());
-- motorista vê apenas as "Em Trânsito"
CREATE POLICY provas_select_motorista ON provas FOR SELECT TO authenticated
  USING (app_setor() = 'motorista' AND status IN
         ('com_motorista_ida_laminacao','com_motorista_volta_laminacao',
          'com_motorista_entrega_final'));
```

O harness de equivalência é **estendido no C06** para essas células de dado; a
aceitação "Vendedor vê só as suas / Motorista só as Em Trânsito" é validada **no
C06** (DP-3).

## 7. Checklist dos critérios de aceitação (§6)

- [x] Cada perfil acessa só as páginas ●/◐ (proxy); acesso direto por URL →
  redirect `/dashboard` + toast (`RbacFlash`).
- [x] Hook injeta `setor`+`user_id`(+`administrador`) na posição lida pela RLS;
  auth segue funcionando (`test_custom_access_token_hook.py`).
- [x] RLS de `usuarios` por perfil ativa e versionada; query direta fora do
  escopo → 0 registros (`test_rls_usuarios.py`).
- [x] Propagação de claims (ADR-008): consultas do backend respeitam a RLS
  (`test_claims_propagation.py`, com teste de controle negativo).
- [x] Sidebar filtrada por perfil; `can(...)` disponível para gating.
- [x] Harness de equivalência cobre 100% das células de página; células de dado
  de `usuarios` cobertas pela RLS; as de `provas` → C06.
- [x] Regra do PR único documentada (§5).
- [x] Mínimo de requisições (`getClaims()` local); stateless; sem segredos
  versionados; R$ 0.

## 8. Testar localmente

```bash
# Backend (apps/api) — @db usa o Postgres local (zonky 5433)
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/rastreio_test \
  uv run pytest tests/integration/test_custom_access_token_hook.py \
                tests/integration/test_rls_usuarios.py \
                tests/integration/test_claims_propagation.py \
                tests/unit/test_equivalencia_matriz.py
uv run alembic upgrade head   # cria hook + helpers + policies (roles stand-in locais)

# Frontend (apps/web)
pnpm test   # access-matrix + equivalência + sidebar + rbac-flash
```
