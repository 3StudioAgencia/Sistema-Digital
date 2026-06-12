# migrations/rls/ — Políticas de Row Level Security versionadas

Camada **inferior** do RBAC em defesa em profundidade (CLAUDE.md §5.4, DAT §7).
A implementação efetiva chegou na **Wave 1 / C05** (esta pasta existe desde o C01
para fixar a política de versionamento).

## Estado atual (pós-C05)

| Arquivo | Papel |
| --- | --- |
| `_roles.sql` | Stand-ins locais de `anon`/`authenticated` (no-op no Supabase) — aplica **primeiro** (prefixo `_`). |
| `_helpers.sql` | Funções reutilizáveis lidas pelas policies: `app_current_claims()`, `app_setor()`, `app_is_admin()`, `app_current_user_id()`. O **C06** compõe a RLS de `provas` sobre elas. |
| `usuarios_grants.sql` | Privilégios de tabela definitivos (grant a `authenticated`; `anon` sem acesso). **Substitui** a postura restritiva provisória do C04 (`usuarios_baseline_restritiva.sql`, removido). |
| `usuarios_select_self.sql` | Cada usuário lê a própria linha (`/me`). |
| `usuarios_select_admin.sql` | Admin lê todas (flag `administrador`). |
| `usuarios_insert_admin.sql` · `usuarios_update_admin.sql` · `usuarios_delete_admin.sql` | Mutações restritas a admin. |
| `alembic_version_baseline_restritiva.sql` | Lockdown da tabela de controle do Alembic (W1-C04). |

> O **C06** adiciona `provas_select_*.sql` (uma por perfil) usando os helpers acima — sem reescrevê-los (DP-3). A divisão é documentada em `docs/rbac.md`.

## Regras (obrigatórias — DAT §2 e CLAUDE.md §9/§11)

1. **Toda** política RLS existe como arquivo `.sql` **nesta pasta, antes** de ser
   aplicada ao banco. Nunca criar/alterar RLS apenas pelo painel do Supabase.
2. **Uma política por perfil × tabela sensível** (`provas`, `movimentacoes`,
   `usuarios`, `audit_log`, `system_settings`), com nome descritivo:
   `"<tabela>_<operacao>_<perfil>.sql"` — ex.: `provas_select_vendedor.sql`.
3. Após **qualquer `DROP`/recriação de tabela** via Alembic, as políticas da
   tabela devem ser **reaplicadas** a partir dos arquivos desta pasta
   (RLS não sobrevive à recriação da tabela).
4. Cada arquivo é **idempotente**: `DROP POLICY IF EXISTS ...; CREATE POLICY ...;`
   — reaplicar nunca pode falhar nem duplicar.
5. Toda alteração na **Matriz de Acesso** (Requisitos v1.0 §7) exige **PR único**
   cobrindo `apps/web/src/lib/access-matrix.ts` **e** os `.sql` desta pasta —
   nunca só um lado (CLAUDE.md §5.4).

## Como aplicar

A migration Alembic **0005** aplica o conteúdo desta pasta (inline, statement a
statement — asyncpg não aceita múltiplos comandos por instrução). Após qualquer
`DROP`/recriação de tabela, reaplicar manualmente na **ordem alfabética** (o
prefixo `_` faz roles→helpers→grants→policies virem antes), a idempotência
garante segurança:

```bash
for f in _roles _helpers usuarios_grants \
         usuarios_select_self usuarios_select_admin \
         usuarios_insert_admin usuarios_update_admin usuarios_delete_admin; do
  psql "$MIGRATIONS_DATABASE_URL" -f migrations/rls/$f.sql
done
```

> Nota (ADR-008 — agora implementado): o backend propaga os claims do usuário por
> requisição via `set_config('request.jwt.claims', …, true)` + `SET LOCAL ROLE
> authenticated` (ver `src/infrastructure/database.py`,
> `SqlAlchemyUnitOfWork.begin`), de modo que as policies que leem
> `app_current_claims()` (= o que `auth.jwt()` lê no Supabase) valem também para
> as consultas servidas pelo FastAPI. Detalhes em `docs/rbac.md`.
