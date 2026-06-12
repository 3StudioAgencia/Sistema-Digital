# Auditoria da Wave 1 — Autenticação e Controle de Acesso (C03 · C04 · C05)

> **Tipo:** Auditoria independente, **read-only**, de prontidão (go/no-go) para iniciar a Wave 2.
> **Data:** 2026-06-12 · **Branch auditada:** `develop` @ `d4d2f31` · **Escopo:** C03 (Login/Sessão) + C04 (Usuários + App Shell) + C05 (RBAC), incluindo a fronteira C05↔C06.
> **Metodologia:** análise estática real (ruff/mypy/eslint/build), suíte de testes + cobertura, inspeção **read-only do Supabase real** (`wmpxxrzbzqgsorjwczvz`), leitura linha-a-linha dos arquivos de segurança, e auditoria adversarial multi-agente (11 dimensões × verificação cética por achado, 50 agentes). Cada achado foi **refutado** por um verificador antes de contar.
> **Ambiente:** o dono autorizou usar o **Supabase real** para a verificação de RLS/hook/roles (feita **somente com SELECT/inspeção de catálogo** — nada foi mutado). Os passos **destrutivos** (ciclo `upgrade→downgrade→upgrade`, suíte `@db` que dropa/recria schema) rodaram no **Postgres local portátil (porta 5433)** — rodá-los contra o projeto real violaria a regra read-only. Cada evidência abaixo indica sua origem.

---

## 1. Sumário executivo e VEREDITO

**VEREDITO: GO** — nenhum achado **Crítico** foi encontrado após verificação adversarial; a régua acordada (qualquer Crítico = NO-GO) **não é acionada**. A Wave 1 é uma base **sólida e bem construída** para a Wave 2.

**GO condicionado** a três recomendações que deveriam ser endereçadas **antes/no início da Wave 2** (não bloqueiam por régua, mas mitigam risco real que a Wave 2 herdaria):
1. **Decidir o endurecimento da RLS no caminho do backend (W1-A-001, Alto).** Hoje a camada inferior depende **exclusivamente** do `SET LOCAL ROLE authenticated` da aplicação, porque o role de runtime é `postgres` (**owner + `BYPASSRLS`**) e `FORCE ROW LEVEL SECURITY` está OFF. Não é explorável no estado entregue (todos os endpoints de `usuarios` passam pela propagação), mas o **C06 vai construir a RLS de `provas` sobre exatamente este padrão fail-open** — onde um único caminho de query sem propagação vazaria dados entre vendedores. Endereçar agora evita um Crítico latente na Wave 2.
2. **Cobrir com teste o enforcement do proxy/middleware (W1-A-002, Alto).** O critério de aceitação do C05 ("acesso direto por URL → redirect + toast") e o DoD §8/6 ("teste de acesso não autorizado por perfil") só estão cobertos no nível das **funções puras** da Matriz — o caminho real de enforcement (`updateSession`/redirect) não tem teste.
3. **Verificar/habilitar o Custom Access Token Hook no dashboard** (item de ambiente). Sem ele, o JWT não carrega `setor`/`administrador` e **todo** o RBAC degrada (admins perdem acesso admin; RLS trata todos como não-admin). É toggle operacional, não defeito de código — mas é pré-requisito funcional do C06.

**Destaques positivos (verificados):** verificação de JWT robusta (ES256/JWKS+HS256, `alg=none` e confusão de algoritmo bloqueados, `aud`/`exp`/assinatura validados); **zero vazamento de segredo** no cliente/bundle/repositório; Matriz §7 fielmente espelhada em 3 artefatos travados por harness de equivalência (100% das células de página); provisionamento de C04 robusto (compensação, adoção de órfão, RN-010 atômica sob lock, idempotência, ban bloqueia login); migrations no head `0005` com RLS versionada e reaplicável; **RLS de `provas` corretamente adiada** (nada meio-feito); regra hexagonal respeitada.

**Contagem de achados (pós-verificação adversarial):**

| Severidade | Qtde | Bloqueia Wave 2? |
|---|---|---|
| **Crítico** | **0** | — |
| Alto | 2 | Não (recomendado remediar cedo) |
| Médio | 10 | Não |
| Baixo | 11 | Não |
| Observação | 16 | Não |
| _Refutado na verificação_ | 1 | — |

---

## 2. Achados

> Local citado foi confirmado lendo a fonte. "Remediação" é **recomendação — não aplicada** (auditoria read-only).

### 2.1 Crítico
**Nenhum.**

### 2.2 Alto

#### W1-A-001 · RLS — defesa em profundidade depende SÓ do `SET ROLE` da aplicação (role de runtime é owner + `BYPASSRLS`; `FORCE RLS` OFF)
- **Dimensão:** Segurança (§2.1).
- **Local:** `apps/api/src/infrastructure/database.py:113-140` (`propagar_claims_rls`) · `apps/api/src/adapters/inbound/http/dependencies.py:40-47` (único ponto que liga a propagação) · **Supabase real:** `usuarios.relrowsecurity=true`, `relforcerowsecurity=FALSE`, `owner=postgres`; role `postgres` tem `rolbypassrls=TRUE`; `DATABASE_URL` de runtime (ADR-007) conecta como `postgres.<ref>` → role `postgres`.
- **Descrição:** A camada inferior (RLS) só é eficaz porque a aplicação executa `SET LOCAL ROLE authenticated` por transação (listener `after_begin`). O role de conexão é o **owner** da tabela e ainda tem **`BYPASSRLS`**. Como `FORCE RLS` só anula a isenção do *owner* (não o atributo `BYPASSRLS`), **nenhum backstop de banco é possível enquanto o runtime conectar como `postgres`**: se qualquer caminho de query escapar da propagação, a RLS é integralmente contornada (fail-**open**). O padrão idiomático (PostgREST: conectar como `authenticator`, `NOINHERIT`, sem `BYPASSRLS`, e `SET ROLE`) falha **fechado**. Há teste de controle (`tests/integration/test_claims_propagation.py`) que **prova** que sem propagação o owner contorna a RLS.
- **Requisito/ADR/Pilar:** `CLAUDE.md §5.4` (RLS como camada **independente**; "negação em qualquer camada basta"); ADR-008 ("nunca operar o fluxo do usuário com credenciais que façam bypass de RLS"); DoD §8/9.
- **Impacto:** Nenhuma exposição no estado entregue (todos os 6 endpoints de `usuarios` passam por `get_usuarios_service`). **Mas** o C06 aplicará a RLS de `provas` (dado sensível por vendedor) sobre o mesmo padrão; um único repositório/caminho futuro sem a propagação → vazamento cruzado silencioso. Risco que escala para Crítico na Wave 2.
- **Remediação recomendada:** Conectar o runtime com um role **sem `BYPASSRLS` e não-owner** (ex.: `authenticator`→`SET ROLE authenticated`, modelo Supabase), de modo que um `SET ROLE` ausente **falhe fechado**; e/ou centralizar a propagação numa fábrica de sessão única (não em cada wiring) para o C06 herdá-la por padrão. `FORCE RLS` sozinho **não** resolve (o role tem `BYPASSRLS`).

#### W1-A-002 · Sem teste do enforcement do proxy/middleware (camada superior do RBAC)
- **Dimensão:** Conformidade de aceitação (§2.2/§2.3).
- **Local:** `apps/web/src/lib/supabase/middleware.ts:31-94` (`updateSession`/`redirectAcessoNegado`) e `apps/web/src/proxy.ts` — **sem arquivo de teste** (a cobertura web existe só em `access-matrix.test.ts`, `access-matrix.equivalencia.test.ts`, `Sidebar.test.tsx`, `rbac-flash.test.tsx`).
- **Descrição:** As funções puras (`can`/`podeAcessarRota`/`perfilDeClaims`) são 100% testadas, mas o **caminho que efetivamente bloqueia** — `getUser()` → `getClaims()` → decisão → `302` + flash — não tem teste (nem unitário do `updateSession`, nem E2E de "não-admin autenticado é redirecionado"). O E2E do C04 cobre só "sem credencial".
- **Requisito/ADR/Pilar:** C05 critério de aceitação 1 e 6; DoD §8/6 ("teste de tentativa de acesso não autorizado em cada perfil").
- **Impacto:** Um defeito de fiação/regressão no enforcement (ex.: ler o claim errado, esquecer o redirect) passaria verde. Combina perigosamente com W1-A-005 (teste que codifica comportamento errado).
- **Remediação recomendada:** Teste de integração do `updateSession` (mockando `getUser`/`getClaims`) cobrindo: não-admin → rota admin → `302 /dashboard` + cookie de flash; admin → rota admin → `next()`; e um E2E por perfil atrás de `E2E_LIVE`.

### 2.3 Médio

#### W1-A-003 · Landing pós-login e raiz apontam para `/usuarios` (admin-only) em vez de `/dashboard` (HOME do perfil)
- **Dimensão:** RBAC / Aceitação (§2.3/§2.2). _(Consolida 3 achados de mesma raiz; um deles foi ajustado de Crítico→Médio na verificação.)_
- **Local:** `apps/web/src/app/page.tsx:20` (`redirect(user ? "/usuarios" : "/login")`) · `apps/web/src/app/inicio/page.tsx:9` (`redirect("/usuarios")`) · `apps/web/src/app/login/page.tsx:25` (`if (user) redirect("/usuarios")`) · `apps/web/src/app/_components/login-panel.tsx:76` (`router.push("/usuarios")`).
- **Descrição:** C05 definiu `HOME_PADRAO=/dashboard` (universal, ● a todos na Matriz §7) mas os redirects de entrada continuaram apontando para `/usuarios` (recurso `cadastro_usuarios`, **admin-only**) — os comentários no código confirmam que eram placeholders "até o C05 definir a página inicial do perfil", e a atualização foi esquecida. Resultado: **todo perfil não-admin** que loga ou acessa a raiz cai em `/usuarios`, é negado pelo proxy e é jogado em `/dashboard` com um **toast de "acesso negado" espúrio**.
- **Requisito/ADR/Pilar:** Matriz §7 (Dashboard ● = home correta); ADR-030/`docs/rbac.md` (`HOME_PADRAO=/dashboard`); C03 critério 1; `CLAUDE.md §11` (anti-enumeração — toast indevido).
- **Impacto:** Invisível para o único admin provisionado hoje; **quebra a experiência de login dos 3 perfis não-admin** assim que existirem (Wave 2+).
- **Remediação recomendada:** Trocar os 4 redirects de `/usuarios` para `/dashboard` (`HOME_PADRAO`). Trivial.

#### W1-A-004 · `search_path` mutável nas 5 funções de segurança (hook + 4 helpers de RLS)
- **Dimensão:** Segurança (§2.1). _(Reportado também como Observação pela dimensão ARCH — mesmo item.)_
- **Local:** `apps/api/migrations/versions/0004_custom_access_token_hook.py:50-87` (`custom_access_token_hook`) e `0005_rls_usuarios_e_helpers.py:51-76` / `migrations/rls/_helpers.sql:18-60` (`app_current_claims`/`app_setor`/`app_is_admin`/`app_current_user_id`). **Supabase real:** advisor `function_search_path_mutable` (WARN) nas 5 funções; `proconfig=NULL`.
- **Descrição:** Nenhuma das funções fixa `search_path`. São funções de segurança (hook de auth + helpers lidos pelas policies). O risco prático aqui é baixo (os corpos usam só built-ins de `pg_catalog` e chamadas schema-qualificadas `public.*`), mas é exatamente o hardening que o **linter do próprio Supabase** sinaliza.
- **Requisito/ADR/Pilar:** `CLAUDE.md §3` (pilar de robustez/segurança); DoD §8/7 (sem alertas); Supabase Security Advisor 0011.
- **Remediação recomendada:** Adicionar `SET search_path = ''` (ou `pg_catalog, public`) às 5 funções, schema-qualificando referências — na migration **e** no espelho `.sql` (regra do PR único).

#### W1-A-005 · Teste pós-login codifica o comportamento defeituoso (`vendedor → /usuarios`) e o mascara
- **Dimensão:** Aceitação (§2.2). _(Ajustado Alto→Médio.)_
- **Local:** `apps/web/src/app/_components/login-panel.test.tsx:50-59`.
- **Descrição:** O teste asserta que o login empurra para `/usuarios` — fixando o defeito do W1-A-003 como "esperado", de modo que a correção exigiria mudar o teste e o bug não é capturado.
- **Requisito/ADR/Pilar:** DoD §8/5 e /6; C03 critério 1.
- **Remediação recomendada:** Reescrever o teste para asseverar `HOME_PADRAO` (`/dashboard`) após login válido.

#### W1-A-006 · Janela de divergência auth↔domínio em `editar`/`alterar_status` (mutação no provedor antes do recheck atômico da RN-010)
- **Dimensão:** C04 — robustez (§2.1/§2.6).
- **Local:** `apps/api/src/application/usuarios.py:245-265` (`editar`) e `:324-342` (`alterar_status`).
- **Descrição:** `update_app_metadata`/`set_banned` são executados **antes** do recheck atômico da RN-010 (sob advisory lock) dentro da transação. Se o recheck falhar (último admin), o serviço reverte o provedor **best-effort** (falha de reversão → log CRITICAL, divergência persistente). É um trade-off consciente (fail-closed na intenção), mas a janela existe.
- **Requisito/ADR/Pilar:** RNF-015/RNF-017; RN-010; Pilar 1.
- **Remediação recomendada:** Reordenar para validar a RN-010 sob lock **antes** da mutação no provedor, ou tornar a reversão garantida (outbox/retry) em vez de best-effort.

#### W1-A-007 · Gate de **formato** do CI vermelho no HEAD do backend (`ruff format --check` reprova 15 arquivos committados)
- **Dimensão:** Qualidade/config (§2.8).
- **Local:** `apps/api` → `uv run ruff format --check .` ⇒ "15 files would be reformatted" (todos C04/C05; ex.: `src/domain/usuarios.py`, `src/application/usuarios.py`, `src/adapters/.../usuarios.py`, `supabase_admin.py`, `migrations/versions/0002_usuarios.py`, vários `tests/`). Gate em `.github/workflows/ci.yml:72`. `ruff` fixado no `uv.lock` = `0.15.16` (= o local). Arquivos **committados** nesse estado (`git status` limpo).
- **Descrição:** O job `api` do CI **falharia** no passo "Lint (ruff)" no HEAD atual. `ruff check` e `mypy --strict` passam; o problema é só o `ruff format`.
- **Requisito/ADR/Pilar:** DoD §8/7 (interpretado como "CI verde"); W0-A-011 (gate de formato como barreira).
- **Remediação recomendada:** `uv run ruff format .` e commitar (cosmético, sem risco).

#### W1-A-008 · Gate de **formato** do CI vermelho no HEAD do frontend (`prettier --check` reprova 3 arquivos committados)
- **Dimensão:** Qualidade/config (§2.8).
- **Local:** `apps/web` → `pnpm format:check` ⇒ exit 1 em `src/app/_components/rbac-flash.tsx`, `src/lib/access-matrix.equivalencia.test.ts`, `src/lib/access-matrix.test.ts`. Gate em `.github/workflows/ci.yml:122-125`.
- **Descrição:** O job `web` do CI **falharia** no passo "Formatação (Prettier)". `eslint`, `vitest` (76/76) e `next build` passam.
- **Requisito/ADR/Pilar:** DoD §8/7; W0-A-011.
- **Remediação recomendada:** `pnpm format` (prettier --write) e commitar.

#### W1-A-009 · `SESSION_LOG`/`CHANGELOG` afirmam "ruff/prettier/format verdes", mas os gates de formato reprovam (drift)
- **Dimensão:** Integridade de documentos (§2.9).
- **Local:** `SESSION_LOG.md:50-51` (Sessão 07/C05: "ruff/mypy limpos", "lint/build limpos") e `:75,:88` (Sessão 06/C04: "prettier/format verdes") vs. evidência de W1-A-007/008.
- **Descrição:** O protocolo de encerramento registrou estado de CI mais otimista do que o real. Sub-achado de W1-A-007/008.
- **Requisito/ADR/Pilar:** `CLAUDE.md §10` (registro fiel); DoD/CI verde.
- **Remediação recomendada:** Corrigir os gates (W1-A-007/008) **e** o registro; ou registrar a dívida explicitamente.

#### W1-A-010 · `migrations/rls/README.md` atribui a propagação de claims ao `SqlAlchemyUnitOfWork.begin` — contradiz o código real (`after_begin`) e a ADR-031
- **Dimensão:** Integridade de documentos (§2.9).
- **Local:** `apps/api/migrations/rls/README.md:53-58` vs. `apps/api/src/infrastructure/database.py:113-152` (a propagação é por listener `after_begin`, **não** no `begin()` — justamente porque leituras auto-begin não passam por `begin()`).
- **Requisito/ADR/Pilar:** ADR-031 (finaliza ADR-008); `CLAUDE.md §9`.
- **Remediação recomendada:** Atualizar o README para descrever o listener `after_begin`.

#### W1-A-011 · Proteção de leaked-password desabilitada no Supabase Auth
- **Dimensão:** Segurança / Aceitação (§2.1). _(Acrescentado pelo auditor-chefe a partir do advisor; ação do dono.)_
- **Local:** **Supabase real:** advisor `auth_leaked_password_protection` (WARN, desabilitado).
- **Descrição:** A checagem contra HaveIBeenPwned está off; e a política de senha (min 8, letra+dígito) do RF-018 ainda depende de configuração no dashboard (pendência já rastreada). O backend e o front **já validam** a política localmente (defesa em profundidade), então o impacto é incremental.
- **Requisito/ADR/Pilar:** RNF-005 (segurança de senha); RF-018; pendência DP-3 do C04.
- **Remediação recomendada:** Habilitar leaked-password protection e configurar a política de senha (min 8, letras+dígitos) no dashboard — ação do responsável.

#### W1-A-012 · Captura de erro do frontend ausente / sem error boundary do grupo `(app)`
- **Dimensão:** Pilares — robustez/observabilidade (§2.6). _(Consolida dois Baixo correlatos; ver W1-A-016/017.)_

> _Nota:_ tratado nos itens Baixo W1-A-016 e W1-A-017 (mantidos como Baixo na verificação); listado aqui só para visibilidade do tema "resiliência do frontend".

### 2.4 Baixo

| ID | Dimensão | Local | Descrição | Remediação |
|---|---|---|---|---|
| **W1-A-013** | SEC-JWT | `auth.py:43,122-133` | `iss` (issuer) não é validado (sem `issuer=`). Risco baixo no caminho ES256/JWKS (emissor implícito pelo `kid`); relevante só se o **segredo HS256 for compartilhado** entre projetos. | Passar `issuer=f"{supabase_url}/auth/v1"` e/ou incluir `iss` em `_REQUIRED_CLAIMS`. |
| **W1-A-014** | C04 | `application/usuarios.py:193-197`; `supabase_admin.py:50-57,148-153` | Adoção de órfão depende de `created_at` do GoTrue parseável; ausente/inválido → retry nunca converge (preso em 409). | Tratar `created_at` ausente como adotável (com cautela) ou expor caminho administrativo de limpeza. |
| **W1-A-015** | ARCH/Docs | `migrations/versions/0002_usuarios.py:9,36`; `docs/usuarios.md:98` | Docstring/migration referenciam `usuarios_baseline_restritiva.sql`, **removido** pelo ADR-032. | Atualizar comentários/doc para apontar a RLS definitiva (0005). |
| **W1-A-016** | Pilares | `apps/web/src/app/(app)/` (sem `error.tsx` próprio; só `app/error.tsx` + `global-error.tsx`) | Sem error boundary dedicado ao grupo autenticado — recuperação contextual ausente (o root boundary cobre, mas genérico). | Adicionar `app/(app)/error.tsx` com retry contextual. |
| **W1-A-017** | Pilares | `app/error.tsx:22-24`, `global-error.tsx:22-24` (só `console.error`) | RNF-024: captura **centralizada** de erros do frontend ausente (sem Sentry/report). | Integrar um sink de erros (mesmo simples) — fronteira do C19/observabilidade. |
| **W1-A-018** | Qualidade | `apps/api/src/tasks/bootstrap_admin.py` (cobertura 0%, 64 stmts) | Provisionamento do 1º admin (raiz de confiança do RBAC) sem nenhum teste. | Teste de idempotência do `bootstrap_admin` (upsert + marca). |
| **W1-A-019** | Docs | `docs/auth.md:11-24,58-67,165` | Descreve telas/fluxo **obsoletos** (`/bem-vindo` mobile, `/inicio` com `AuthProof`, `/`→`/bem-vindo`), superados por ADR-022/C04. | Reescrever o doc para o fluxo de rota única + app shell. |
| **W1-A-020** | Docs | `docs/usuarios.md:95-99` | §3 descreve a RLS provisória do C04 como atual e referencia `.sql` já removido. | Atualizar para a RLS definitiva (6-A, ADR-032). |
| **W1-A-021** | Fronteira | `migrations/rls/_helpers.sql:18-38`; `tests/integration/test_rls_usuarios.py` | `app_setor()` e `app_current_claims()` entregues p/ o C06 **sem teste direto** (só `app_is_admin`/`app_current_user_id` exercitados via policies). | Teste direto dos 4 helpers sob claims propagados. |
| **W1-A-022** | SEC-RLS | `migrations/versions/0002_usuarios.py:9,36` | (Duplicata de W1-A-015 vista pela dimensão de segurança.) | — |

### 2.5 Observação (dívida menor / por design)

| ID | Tema | Nota |
|---|---|---|
| W1-A-023 | HS256 fallback habilitável em produção | Trade-off documentado (ADR-018/019); isolado corretamente. Recomenda-se **não** definir `SUPABASE_JWT_SECRET` em produção ES256. |
| W1-A-024 | Sem `leeway` de clock skew no `exp` | Default seguro; considerar `leeway` pequeno se houver skew operacional. |
| W1-A-025 | `.env` reais no disco com segredos | **Ignorados** pelo `.gitignore` (verificado: `git check-ignore` confirma). Sem vazamento; proteção depende do gitignore (correto). |
| W1-A-026 | Múltiplas policies PERMISSIVE de SELECT em `usuarios` | Advisor de performance (WARN); por design (self + admin). Avaliar policy única se necessário. |
| W1-A-027 | Sidebar deriva flag de `/me` (DB) e proxy de `getClaims()` (JWT) | Fontes distintas que podem divergir transitoriamente; sidebar é espelho (não autoridade) — aceitável. |
| W1-A-028 | Célula `provas` ◐ não enforçada na Wave 1 | Escopo de dado adiado ao C06 (ADR-033); ◐ é dado, não página. Correto. |
| W1-A-029 | Trade-off de claims "stale até refresh" não documentado | `getClaims()` local decide por claims do token; documentar a janela. |
| W1-A-030 | `search_path` (visão ARCH) | Mesmo que W1-A-004. |
| W1-A-031 | RLS no backend depende de wiring único (`get_usuarios_service`) | Mesmo tema de W1-A-001; risco de regressão no C06 se não generalizado. |
| W1-A-032 | Ativação do hook é passo manual sem verificação automatizada | Ver "Itens que requerem ambiente". |
| W1-A-033 | RNF-024: "alerta em erros críticos" não implementado (só log CRITICAL) | Fronteira de observabilidade (C19/infra). |
| W1-A-034 | Proxy roda `getUser()` (round-trip ao auth server) por requisição navegável | Tensão com o Pilar 3; é a decisão de segurança do C03 (`getUser` valida no servidor). Aceitável; `getClaims` já é local. |
| W1-A-035 | Versão do `ruff` "≥0.6" no `pyproject` | Fixada de fato no `uv.lock` (0.15.16); sem drift real (lockfile congelado no CI). |
| W1-A-036 | `docs/app-shell.md` diz "todo autenticado vê o menu inteiro" | Já superado (sidebar filtrada no C05). Atualizar. |
| W1-A-037 | Nomes dos helpers (`app_*`) renomeiam `is_3studio()`/`current_app_user_id()` do prompt | Por design (ADR-023/031); cobrem a mesma função. Não é defeito. |
| W1-A-038 | (reservado) | — |

### 2.6 Refutado na verificação
- **docs/auth.md §7 "declara todos os gates verdes incluindo formato"** — o verificador **refutou**: o doc não faz essa afirmação de forma que sustente o achado. Excluído.

---

## 3. Resultados das execuções

### 3.1 Análise estática e testes (origem: **Postgres local 5433** para `@db`)
| Verificação | Comando | Resultado |
|---|---|---|
| Lint backend | `uv run ruff check .` | ✅ **All checks passed** |
| Formato backend | `uv run ruff format --check .` | ❌ **15 arquivos reformatariam** (W1-A-007) |
| Tipos backend | `uv run mypy` (strict) | ✅ **Success, 44 arquivos** |
| Testes backend | `uv run pytest --cov` (`REQUIRE_DB_TESTS=1`, PG 5433) | ✅ **229 passed**, cobertura **90.44%** (piso 80) |
| Lint web | `pnpm lint` (eslint) | ✅ passou |
| Formato web | `pnpm format:check` (prettier) | ❌ **3 arquivos** (W1-A-008) |
| Testes web | `pnpm test` (vitest) | ✅ **76 passed** (13 arquivos) |
| Build web | `pnpm build` (next build) | ✅ sucesso |

**Cobertura por arquivo (domínio/serviço — DoD §8/2):** `domain/usuarios.py` 100% · `domain/rbac.py` 93% · `application/usuarios.py` 94% · `adapters/.../auth.py` 98% · `supabase_admin.py` 87% · `usuarios_repository.py` 90% · `tasks/bootstrap_admin.py` **0%** (W1-A-018). Piso de domínio/serviço (≥80%) **atendido**; máquina de estados (≥95%) **N-A** (Wave 3).

### 3.2 Cobertura da Matriz de Acesso (células ●/◐/○)
- **100% das células de PÁGINA** (10 recursos × {admin, não-admin}) cobertas em **ambas** as linguagens: `access-matrix.equivalencia.test.ts` (web) e `tests/unit/test_equivalencia_matriz.py` (api), travadas ao mesmo `access-matrix.cells.json`. Verificado.
- **◐ (escopo de dado de `provas`)** — adiado ao C06 (ADR-033); não é célula de página.
- **Escopo de dado de `usuarios`** — coberto por RLS: `usuarios_select_self` (cada um a própria linha) + `usuarios_select_admin`. Testado em `test_rls_usuarios.py`.

### 3.3 Testes negativos de RLS (origem mista)
- **Local (PG 5433):** `test_claims_propagation.py` prova que **sem** propagação a conexão owner **contorna** a RLS (controle negativo correto) e que **com** propagação a RLS filtra; `test_rls_usuarios.py` exercita as policies sob `SET LOCAL ROLE authenticated`.
- **Supabase real (read-only):** policies de `usuarios` conferidas 1:1 com o design 6-A; `anon` sem grants/policies; `alembic_version` travado (RLS on, grants só `postgres`/`service_role`).

### 3.4 Inspeção do Supabase real (`wmpxxrzbzqgsorjwczvz`, read-only)
- `alembic_version = 0005` (head). 1 usuário de domínio ↔ 1 auth user; `app_metadata` com `setor`+`administrador`; **sem órfãos**.
- Funções `custom_access_token_hook` + 4 helpers presentes, `SECURITY INVOKER`, `proconfig=NULL` (W1-A-004). Hook com `EXECUTE` restrito a `supabase_auth_admin`/`service_role`/`postgres` (não PUBLIC/anon/authenticated). ✅
- Advisors: 5× `function_search_path_mutable` (WARN); `auth_leaked_password_protection` desabilitado (WARN); `rls_enabled_no_policy` em `alembic_version` (INFO, lockdown intencional); 3× `unused_index` (INFO, tabela quase vazia); `multiple_permissive_policies` (WARN perf).

---

## 4. Checklist da DoD global (Backlog §2 — 13 itens)

| # | Critério | Status | Evidência |
|---|---|---|---|
| 1 | Code review aprovado | ✅* | Revisões adversariais multi-agente registradas (C03/C04/C05). *Caveat: gate de formato do CI vermelho (W1-A-007/008). |
| 2 | ≥80% domínio/serviço; ≥95% máquina de estados | ✅ / N-A | Domínio 100%/93%, serviço 94% (§3.1); máquina de estados é Wave 3. |
| 3 | Integração em staging | ⚠️ | Suíte `@db` verde em PG local; Supabase real no head `0005`, mas **hook enablement não verificável offline** (§5). |
| 4 | Migrations aplicadas/versionadas/documentadas | ✅* | head `0005`, RLS espelhada 1:1 em `/migrations/rls/`. *Drift menor em docstrings (W1-A-015). |
| 5 | Validado vs critérios de aceitação (Req §5) | ⚠️ | Em geral atendido; **landing /usuarios** quebra a home do perfil para não-admin (W1-A-003). |
| 6 | Validado vs Matriz §7 (acesso não autorizado por perfil) | ⚠️ | Funções 100% testadas + guard backend testado; **enforcement do proxy sem teste** (W1-A-002). |
| 7 | Sem erro no console / log crítico no backend | ✅ | Build limpo; logs CRITICAL só em falhas reais. (CI-formato é item à parte.) |
| 8 | Documentação do módulo | ⚠️ | Existe e em boa parte correta; drifts em `auth.md`/`usuarios.md`/`app-shell.md`/`rls/README` (W1-A-010/019/020/036). |
| 9 | RLS versionada em `/migrations/rls/` | ✅ | Todas as policies espelhadas, reaplicáveis; `_roles`/`_helpers`/lockdown. |
| 10 | Animações com `prefers-reduced-motion` | ✅ | Reusa fundação C03/C04 (`useReducedMotion`); testes presentes. |
| 11 | Escritas idempotentes (RNF-015) | ✅ | `editar` early-return; `alterar_status` converge; testado. |
| 12 | Sem N+1; mínimo de requisições | ✅ | Listagem = 2 queries; debounce 300ms; `getClaims` local. (Tensão `getUser`/request: W1-A-034.) |
| 13 | Error boundaries por rota + recuperação | ⚠️ | Root `error.tsx`+`global-error.tsx` cobrem; sem boundary do grupo `(app)` nem captura central (W1-A-016/017). |

---

## 5. Itens que requerem verificação em ambiente (não confirmáveis offline)

1. **Custom Access Token Hook HABILITADO no dashboard** (Auth → Hooks → `public.custom_access_token_hook`). **Funcionalmente crítico:** sem ele o JWT não carrega `setor`/`administrador` → proxy trata todos como não-admin e a RLS `app_is_admin()` retorna false. A função existe e está correta; falta confirmar a ativação no GoTrue (não exposto via SQL). _Pendência já registrada no SESSION_LOG._
2. **Assinatura ES256 real / comportamento de RLS ponta-a-ponta** com uma sessão viva (login real → claims elevados → query sob `authenticated`).
3. **TTL do access token** alinhado à inatividade de 30 min (RNF-004) — config de dashboard (DP-3 do C03).
4. **Política de senha + leaked-password** no dashboard (W1-A-011; RF-018/RNF-005).
5. **Status do CI no GitHub** para o HEAD de `develop` — a reprodução local indica que os jobs falhariam nos gates de formato (W1-A-007/008); confirmar na aba Actions.
6. (Herdado W0) `KEEPALIVE_DATABASE_URL` cadastrado.

---

## 6. Lista priorizada de remediação

### Deveria ser corrigido **antes/no início da Wave 2** (não bloqueia por régua, mas mitiga risco que a Wave 2 herda)
1. **W1-A-001 (Alto)** — decidir e implementar o endurecimento da RLS (role de runtime sem `BYPASSRLS`/não-owner, fail-closed) **antes** de o C06 construir a RLS de `provas` sobre o padrão atual. _Maior risco arquitetural._
2. **W1-A-003 (Médio)** — repointar os 4 redirects de `/usuarios`→`/dashboard` (corrige a experiência de todo não-admin). Trivial.
3. **W1-A-002 (Alto)** — adicionar teste do enforcement do proxy/middleware (e corrigir W1-A-005, o teste que mascara o bug).
4. **W1-A-007/008/009 (Médio)** — rodar `ruff format`/`prettier --write`, commitar, e alinhar o SESSION_LOG → CI verde.
5. **Ambiente §5.1** — verificar/habilitar o hook (pré-requisito funcional do C06).

### Dívida rastreada (pode seguir; agendar)
- **W1-A-004** (search_path nas 5 funções) — hardening; idealmente junto com a RLS de `provas` (PR único).
- **W1-A-006** (janela auth↔domínio) — reordenar recheck RN-010 antes da mutação no provedor.
- **W1-A-010/015/019/020/036** — drifts de documentação.
- **W1-A-013** (`iss`), **W1-A-014** (órfão sem `created_at`), **W1-A-016/017** (error boundary/captura front), **W1-A-018** (testes do bootstrap), **W1-A-021** (testes dos helpers).
- **W1-A-011** (leaked-password) e demais itens de ambiente — ação do responsável.
- Observações §2.5 — avaliar caso a caso.

---

## 7. Conformidades verificadas (destaques)

> Itens **confirmados corretos** durante a auditoria (lista completa por dimensão no apêndice da execução do workflow).

- **JWT (C03):** ES256/RS256 via JWKS + HS256 fallback; `alg=none` e confusão de algoritmo bloqueados (chaves particionadas por família); `verify_signature/exp/aud` ligados + `require [exp,aud,sub]`; backend **nunca** emite (`jwt.encode` só em testes); 401 genérico anti-enumeração; JWKS `timeout=5`; `deny-all` por default; `sub` validado.
- **Segredos:** zero exposição no cliente/bundle/repo; `SUPABASE_SECRET_KEY`/`R2`/`JWT_SECRET` como `SecretStr` server-only; único consumidor é o adapter; `.gitignore` correto; teste de regressão de não-vazamento em respostas de erro.
- **RBAC:** equivalência tri-artefato (`cells.json` ↔ `access-matrix.ts` ↔ `domain/rbac.py`) travada por harness; ortogonalidade ADR-023 (Vendedor-Admin vê admin) testada; proxy `getUser()`+`getClaims()` local; sidebar filtrada; guard backend `requer_acesso` + RLS como defesa adicional.
- **C04:** desativação = ban real (`ban_duration` longo) + revogação de sessões; RN-010 (auto-desativação, auto-rebaixamento, último admin) com recheck **atômico sob advisory lock**; compensação + adoção de órfão com guarda de idade; idempotência; e-mail imutável; 503 sem segredo.
- **Arquitetura:** regra hexagonal respeitada (domínio não importa adapters/infra); ADR-007 (NullPool + caches off; migrations diretas); ADR-008/031 (propagação `after_begin`); RLS versionada 1:1; enums sincronizados Python↔PG.
- **Fronteira C05↔C06:** 4 helpers prontos e corretos; RLS de `provas` **corretamente adiada** (nada meio-feito; tabela `provas` inexistente); pendência no SESSION_LOG precisa.

---

## 8. Nota metodológica e limites

- **Read-only:** nenhum arquivo de código/migração/RLS/config/doc foi alterado; a única escrita foi este relatório. O Supabase real foi tocado **apenas** com `SELECT`/catálogo/advisors.
- **Origem das evidências:** estática e `@db` no **Postgres local 5433**; estado de RLS/hook/roles no **Supabase real** (read-only). Itens que exigem o GoTrue/sessão viva estão na §5.
- **Verificação adversarial:** cada um dos 39 achados brutos passou por um verificador cético; 1 foi refutado, 4 tiveram severidade ajustada (3 reduzidas, incluindo um Crítico→Médio em W1-A-003 e um Alto→Médio em W1-A-005).
- **Remediação é decisão separada:** este relatório **propõe** correções; nenhuma foi aplicada. *(O desfecho de cada achado está na §9, acrescentada na sessão de remediação.)*

---

## 9. Remediação (sessão 2026-06-12) — desfecho por achado e VEREDITO atualizado

> Sessão de remediação dirigida por este relatório (escopo: `PROMPTS/W1-REMEDIACAO-wave1.md`). Cada fix foi feito de forma cirúrgica, com teste provando o fechamento e re-verificação de que nada regrediu, em **commit semântico por achado** (`fix/test/docs/style(w1-audit): <ID>`). **Decisões do dono:** W1-A-001 = endurecer in-repo agora (fail-closed) + adiar o role não-owner ao C06; W1-A-006 = aceitar como dívida rastreada; escopo = remediação in-repo completa; ações de dashboard (leaked-password + política de senha; aplicar migrations no Supabase real) com o dono (hook **já habilitado**).

### 9.1 Fragilidade da verificação (anti-regressão)
- **Nenhum falso-positivo:** os 20 achados acionáveis foram **confirmados contra o código real** antes de qualquer correção (grounding multi-agente). Nada foi "corrigido no escuro".
- **RLS positivo + negativo:** `test_request_sem_propagacao_falha_fechado` (sessão de request sem claims → **levanta**, não lê como owner) + `test_backend_com_propagacao_respeita_rls` (admin vê tudo, não-admin só a própria) + `test_sessao_de_sistema_roda_como_owner` (owner/seed segue bypassando de propósito). Sem super-restrição: os endpoints de `usuarios` e a suíte `@db` seguem verdes.

### 9.2 Desfecho por achado

| ID | Sev | Desfecho | Evidência (commit · teste) |
|---|---|---|---|
| **W1-A-001** | Alto | **Resolvido (parcial + dívida)** — fail-closed in-repo (`abrir_sessao_rls` + `create_request_session_factory` + guarda `after_begin`); **role não-owner adiado ao C06** (decisão do dono) | `2eeb430` · `test_claims_propagation.py` (fail-closed + positivo + controle) |
| **W1-A-002** | Alto | **Resolvido** | `31c8efd` · `middleware.test.ts` (4 casos do enforcement) |
| **W1-A-003** | Médio | **Resolvido** | `1291b15` · 4 redirects → `HOME_PADRAO`; `login-panel.test.tsx` |
| **W1-A-004** | Médio | **Resolvido (in-repo; aplicar 0006 no Supabase = dono)** | `f559169`/`012121d` · `test_funcoes_de_seguranca_tem_search_path_fixo` + `test_migrations` |
| **W1-A-005** | Médio | **Resolvido** (junto com 003) | `1291b15` · teste reescrito p/ `HOME_PADRAO` |
| **W1-A-006** | Médio | **Adiado (dívida rastreada)** — trade-off ADR-025 consciente; revisitar com outbox | decisão do dono |
| **W1-A-007** | Médio | **Resolvido** | `a54560e` · `ruff format --check` verde (77 arquivos) |
| **W1-A-008** | Médio | **Resolvido** | `c896a9a` · `prettier --check` verde |
| **W1-A-009** | Médio | **Resolvido** | esta §9 + entrada de SESSION_LOG corrigem a narrativa de "format verde" |
| **W1-A-010** | Médio | **Resolvido** | `926889d` · README aponta `propagar_claims_rls`/`after_begin` |
| **W1-A-011** | Médio | **Ação do dono** — habilitar leaked-password + política de senha no dashboard | dono fará |
| **W1-A-012** | Médio | **Resolvido** (umbrella de 016/017) | `a266950` |
| **W1-A-013** | Baixo | **Resolvido** | `f938719` · issuer validado config-gated; testes ES256+HS256 |
| **W1-A-014** | Baixo | **Resolvido** | `12ff6e7` · `created_at` ausente converge; 2 testes |
| **W1-A-015** | Baixo | **Resolvido** | `926889d` · docstring/comentário de 0002 atualizados |
| **W1-A-016** | Baixo | **Resolvido** | `a266950` · `(app)/error.tsx` + teste |
| **W1-A-017** | Baixo | **Resolvido (seam in-repo; sink real → C19/C20)** | `a266950` · `reportClientError` + teste |
| **W1-A-018** | Baixo | **Resolvido** | `b8e55c0` · bootstrap_admin 0%→**100%** (idempotência/claims/unban + guards) |
| **W1-A-019** | Baixo | **Resolvido** | `8ba018d` · `auth.md` reescrito p/ rota única + app shell |
| **W1-A-020** | Baixo | **Resolvido** | `8ba018d` · `usuarios.md` → RLS definitiva 6-A |
| **W1-A-021** | Baixo | **Resolvido** | `b8e55c0` · `test_rls_helpers.py` (app_setor/app_current_claims + default-deny) |
| **W1-A-022** | Baixo | **Resolvido** (duplicata de 015) | `926889d` |
| **W1-A-023..035, 037** | Obs | **Mantidos (por design / dívida menor)** — trade-offs documentados; sem ação | — |
| **W1-A-036** | Obs | **Resolvido** | `8ba018d` · `app-shell.md` (sidebar filtrada) |

**Contagem:** Resolvidos **19** (2 Altos, 7 Médios, 8 Baixos, 1 Obs, + 12/22 umbrella/duplicata) · Adiados **1** (W1-A-006) + a perna de role do W1-A-001 → C06 · Ações do dono **1** (W1-A-011) + dashboard/migrations · **Falso-positivo: 0**.

### 9.3 Re-verificação final (saída real)
- **Backend:** `ruff check` ✅ · `ruff format --check` ✅ (77) · `mypy --strict` ✅ (45) · `pytest --cov` ✅ **255 passed**, cobertura **95.12%** (piso 80) · ciclo Alembic `upgrade→downgrade→upgrade` limpo (head **0006**).
- **Frontend:** `eslint` ✅ · `prettier --check` ✅ · `vitest` ✅ **85 passed** (16 arquivos) · `next build` ✅.
- **prefers-reduced-motion:** o novo boundary não anima (N/A); fundação de motion intacta. **Idempotência** (bootstrap) testada. **Sem erro de console/log crítico.**
- Δ testes: api **229→255** (+26) · web **76→85** (+9).

### 9.4 VEREDITO atualizado — **GO** para a Wave 2
Os **2 Altos foram endereçados** (W1-A-001 fail-closed in-repo, com a perna de role conscientemente adiada ao C06 onde entra junto dos GRANTs de `provas`; W1-A-002 coberto). Todos os Médios/Baixos in-repo foram resolvidos; a dívida remanescente (**W1-A-006** aceito; **role não-owner** no C06; **W1-A-011** e aplicar migrations = dono) **não bloqueia** a Wave 2. A régua "qualquer Crítico = NO-GO" segue não acionada (0 Críticos).

**Próximo passo: W2-C06 · Cadastro de Prova + Rota + Etiqueta** — abre a Wave 2 e aplica a RLS de `provas` **sobre a fundação fail-closed** (`abrir_sessao_rls` + helpers) entregue aqui. *(Divergência registrada — CLAUDE.md §2.1: o prompt de remediação citou "W2-C07 · Listagem/Filtros", mas o roadmap do Backlog/CLAUDE.md §7 e o SESSION_LOG têm o **C06** como primeiro componente da Wave 2; prevalece o roadmap.)*
