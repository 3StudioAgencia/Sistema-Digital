# Gestão de Usuários (W1-C04)

> Backend + frontend do CRUD de usuários (RF-018, RF-020, US-015) e o
> provisionamento coordenado com o Supabase Auth. Decisões registradas em
> `DECISIONS.md` (ADR-023 a ADR-028).

## 1. Modelo de domínio (DP-1 → ADR-023)

**Setor × Administrador são ortogonais** (modelo do design, que governa):

- `setor` ∈ `{studio, vendedor, motorista, clicheria}` — escopo **operacional**,
  exatamente um por usuário (RN-009). Rótulo de UI do `studio` é "3Studio".
- `administrador` (boolean) — flag de **perfil**, independente do setor
  (ex.: um Vendedor pode ser Admin). "Perfil" exibido na UI deriva do flag
  (`Admin`/`Usuário`).
- O antigo conceito "3Studio (Administrador)" dos Requisitos equivale a
  `setor=studio + administrador=true`.

**Leitura da Matriz de Acesso (Requisitos §7) sob este modelo** (vale p/ C05):
linhas "Exclusivo 3Studio" (Criar Prova, Cadastro de Usuários, Relatórios,
Configurações, Log de Auditoria, Reiniciar Ciclo, Cancelar) chaveiam pelo
**flag** `administrador`; células de escopo operacional (Vendedor ◐,
Motorista ◐, Clicheria ●) chaveiam pelo **setor**; a coluna "3Studio" vale para
`setor=studio` nas células não exclusivas de admin.

### Tabela `usuarios` (migration `0002_usuarios`, ADR-024)

| Coluna | Tipo | Regras |
| --- | --- | --- |
| `id` | uuid PK | **= `auth.users.id`** (vínculo 1:1; sem FK física — `auth.*` é gerenciado pelo Supabase, fora do Alembic) |
| `nome` | varchar(200) NOT NULL | |
| `email` | varchar(320) NOT NULL | único case-insensitive (`uq_usuarios_email_lower`) |
| `setor` | `setor_enum` NOT NULL | `studio·vendedor·motorista·clicheria` |
| `localizacao` | `localizacao_enum` NULL | `matriz·filial`; CHECK bidirecional: obrigatória ⟺ `setor='vendedor'` (RN-009) |
| `administrador` | bool NOT NULL default false | |
| `ativo` | bool NOT NULL default true | desativação **não** apaga a linha (US-015) |
| `created_at`/`updated_at` | timestamptz | server-side |

Índices de filtro/ordenação (RNF-019): `setor`, `ativo`, `lower(nome)`,
`created_at`. Enums sincronizados Python ↔ PG ↔ TS
(`src/domain/usuarios.py` · migration 0002 · `apps/web/src/lib/api/usuarios.ts`).

## 2. Provisionamento coordenado (ADR-025)

Criar usuário toca **duas fontes**: o auth user (Supabase Auth, via **Admin
API**) e a linha de domínio. Orquestração em
`apps/api/src/application/usuarios.py` (`UsuariosService.criar`):

1. Valida senha (min. 8 com letra e número) e RN-009 — **antes** de qualquer IO.
2. Rejeita e-mail já cadastrado no domínio (409).
3. `POST /auth/v1/admin/users` com `email_confirm: true` e
   `app_metadata = { setor, administrador, provisionado_por: "rastreio-api" }`.
4. INSERT em `usuarios` na transação (UoW) e commit.

**Falha parcial (RNF-015/017):**

- Banco falha após o passo 3 → **compensação**: o auth user recém-criado é
  removido. Se a própria compensação falhar → log **CRITICAL** e fica um órfão
  *marcado*.
- Retry do administrador → **adoção de órfão**: se o e-mail já existe no auth
  **com a nossa marca** (`provisionado_por`) e **sem** linha de domínio, a conta
  órfã é removida e recriada. Contas **sem** a marca (criadas no dashboard)
  nunca são tocadas → 409.

**Editar / Desativar / Reativar** (provedor-primeiro, *fail-closed*):

- Editar: muda `nome/setor/localizacao/administrador`. Se setor/flag mudam, o
  `app_metadata` é atualizado **antes** do banco; falha no banco reverte o
  metadata (best-effort + CRITICAL). E-mail **não é editável** (identidade do
  auth); senha não se altera por aqui (reset = componente futuro).
- Desativar = `ban_duration` longa no auth (bloqueia login/refresh) **+**
  revogação de sessões (best-effort) **+** `ativo=false`. Reativar desfaz.
  Idempotentes: repetir converge sem efeito colateral.

**Regras enforce no backend** (`domain/usuarios.py` + service):

- RN-009: localização obrigatória p/ Vendedor e **indevida** p/ demais
  (validação + CHECK no banco).
- RN-010: admin não se autodesativa; não remove o próprio flag; salvaguarda do
  **último admin ativo** (sistema nunca fica sem administrador).

## 3. Chave secreta e guard (DP-3/DP-5 → ADR-027)

- `SUPABASE_SECRET_KEY` (formato novo `sb_secret_...`; a `service_role` legada
  também funciona): **server-only**, vive apenas no ambiente do backend
  (Railway). Único consumidor:
  `adapters/outbound/identity/supabase_admin.py`. Logs registram somente status
  HTTP + `error_code` — nunca a chave/URL com header.
- Sem a chave → a app sobe e a gestão de usuários responde **503** claro
  (mesma filosofia do storage não configurado).
- **Guard mínimo de admin**: endpoints de gestão exigem JWT válido (C03) **e**
  linha `usuarios` do chamador com `administrador=true` e `ativo=true` → senão
  403. `GET /usuarios/me` é a exceção (qualquer autenticado lê a própria linha
  — alimenta o app shell). Enforcement por página + RLS por perfil = **C05**.
- **RLS (definitiva desde o C05)**: o C04 ligou uma postura **provisória**
  restritiva na migration 0002 (RLS habilitada, sem policies, REVOKE de
  `anon`/`authenticated`); o **C05 a SUBSTITUIU** pela RLS definitiva por perfil
  (opção 6-A / ADR-032, migration 0005): `GRANT` a `authenticated` + policy
  `usuarios_select_self` (cada um lê a própria linha) e
  `usuarios_{select,insert,update,delete}_admin` (flag `administrador`); `anon`
  segue sem acesso. Espelhada em `migrations/rls/*.sql` (o
  `usuarios_baseline_restritiva.sql` foi removido). O guard de admin permanece
  como camada explícita extra.
- **Claims para o C05**: `app_metadata.setor` e `app_metadata.administrador`
  são gravadas/sincronizadas em todo provisionamento/edição — é o que o Custom
  Access Token Hook e as policies (`auth.jwt()`) consumirão.

## 4. Endpoints

| Método/rota | Quem | O quê |
| --- | --- | --- |
| `GET /usuarios/me` | autenticado | linha de domínio própria (404 se não provisionado) |
| `GET /usuarios?busca&setor&status&page&page_size` | admin | listagem paginada server-side (máx. 100/página), busca ILIKE escapada em nome/e-mail, ordenada por nome |
| `POST /usuarios` | admin | criação coordenada (201) |
| `PATCH /usuarios/{id}` | admin | edição parcial (e-mail imutável) |
| `POST /usuarios/{id}/desativar` · `/reativar` | admin | ban/unban + `ativo` (idempotente) |

Erros no envelope canônico (`{"error":{code,message,request_id}}`): `409
email_ja_cadastrado` · `404 usuario_nao_encontrado` · `422` regras
(`senha_fraca`, `localizacao_invalida`, `auto_desativacao`,
`auto_remocao_admin`, `ultimo_admin`) · `502 provedor_identidade` · `503
identidade_nao_configurada`.

## 5. Bootstrap do primeiro administrador

O guard exige uma linha admin — mas a primeira conta (criada no dashboard para
o C03) não tem linha de domínio:

```bash
cd apps/api   # exige SUPABASE_URL + SUPABASE_SECRET_KEY no .env
uv run python -m src.tasks.bootstrap_admin -- --email admin@dominio --nome "Nome"
```

Localiza o auth user pelo e-mail, grava `app_metadata` e faz **upsert** da
linha como `setor=studio, administrador=true, ativo=true`. Idempotente. Não
cria conta nem define senha (conta precisa existir no dashboard).

## 6. Política de senha

Mínimo 8 caracteres com pelo menos 1 letra e 1 número — validada no domínio
(fonte única), na borda Pydantic e no frontend (`lib/validacao.ts`).
**Ação externa (responsável):** configurar a MESMA política no dashboard do
Supabase (Authentication → Sign In / Providers → Password requirements:
*letters and digits*, min. 8) para cobrir fluxos fora desta API.

## 7. Frontend (Gerenciador de usuários)

- `app/(app)/usuarios/` — página dentro do app shell (ver `docs/app-shell.md`).
  Dados **sempre** via backend (nunca leitura direta do client Supabase).
- Busca com debounce 300ms; filtros de setor/status server-side; **scroll
  infinito** dentro da área rolável da tabela (estética do design preservada).
- Mutações atualizam a lista em memória com a resposta do backend (sem refetch
  desnecessário — RNF-020); criação refaz a primeira página.
- Modal "Novo usuário"/"Editar usuário" sobre o `MotionModal` reutilizável;
  validação em tempo real; campo **Localização condicional** (aparece só para
  Vendedor — RN-009); 409 vira erro inline no e-mail.
- Desativar/Reativar com modal de confirmação; o botão da linha alterna
  conforme o status ("Reativar" usa o amarelo de ação primária — derivação
  documentada; o mock só mostra "Desativar").
- 403 do guard → estado "Acesso restrito a administradores".

## 8. Testes

- `apps/api/tests/unit/test_usuarios_dominio.py` — senha/RN-009/enums.
- `apps/api/tests/unit/test_usuarios_service.py` — provisionamento, compensação,
  adoção de órfão, RN-010, idempotência, fail-closed (fakes, offline).
- `apps/api/tests/unit/test_identity_supabase.py` — contrato HTTP da Admin API
  (httpx MockTransport, offline).
- `apps/api/tests/integration/test_usuarios_endpoints.py` (@db) — guard 401/403,
  CRUD, filtros/paginação/busca escapada, compensação com Postgres real.
- `apps/api/tests/integration/test_migration_usuarios.py` (@db) — RLS ativa,
  índices, CHECK da RN-009, e-mail único case-insensitive.
- `apps/web` — vitest (form/validação/tabela/toasts/modal/sidebar) e Playwright
  (proteção de rotas sem credencial; fluxo autenticado atrás de `E2E_LIVE=1`).
