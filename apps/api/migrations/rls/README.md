# migrations/rls/ — Políticas de Row Level Security versionadas

Camada **inferior** do RBAC em defesa em profundidade (CLAUDE.md §5.4, DAT §7).
A implementação efetiva chega na **Wave 1 / C05**; esta pasta existe desde o C01
para fixar a política de versionamento.

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

## Como aplicar (a partir da Wave 1)

O passo de deploy executa os `.sql` desta pasta após `alembic upgrade head`
(ordem alfabética; a idempotência garante segurança em reaplicações).
Localmente: `psql "$MIGRATIONS_DATABASE_URL" -f migrations/rls/<arquivo>.sql`.

> Nota (ADR-008): o backend propagará os claims do usuário por requisição via
> `SET LOCAL request.jwt.claims` para que as policies baseadas em `auth.jwt()`
> funcionem — desenho na Wave 1/C05; ponto de extensão já previsto em
> `src/infrastructure/database.py` (`SqlAlchemyUnitOfWork.begin`).
