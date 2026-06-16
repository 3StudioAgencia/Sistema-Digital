# CLAUDE.md

> Documento-mestre de contexto para o **Claude Code**. Leia este arquivo **primeiro**, em **toda** sessão, antes de qualquer ação. Ele tem precedência sobre suposições. Em caso de conflito entre este arquivo e o código existente, este arquivo vence — e o código deve ser corrigido.

---

## 1. O que é este projeto

**Sistema de Rastreio de Provas Digitais** — plataforma web que centraliza o controle do fluxo físico-digital de provas de impressão da 3Studio, do momento da criação até a conclusão na clicheria, com rastreabilidade integral, RBAC em duas camadas e máquina de estados de **14 estados** distribuída em **4 rotas**.

- **Organização:** 3Studio
- **Responsável de produto:** Mario Souza
- **Repositório:** `rastreio-provas-digitais` (monorepo). **No GitHub:** [`3studioagn/Sistema-Digital`](https://github.com/3studioagn/Sistema-Digital) *(o nome no GitHub difere do slug canônico)*. Branches: `main` (estável) + `develop` (integração, **padrão**) — ver ADR-016.
- **Linha de base:** v1.0 (Junho/2026) — versão definitiva e inicial, *greenfield*.

---

## 2. Fonte da verdade (HIERARQUIA — leia com atenção)

Existem documentos de especificação com **versões diferentes**. A regra de precedência é **obrigatória**:

| Documento | Versão | Autoridade |
| --- | --- | --- |
| **Requisitos** (`RequisitosProvasDigitais_v1_0`) | **v1.0** | **Fonte única de verdade** para regras de negócio, requisitos, histórias, matriz de transições e matriz de acesso. |
| **Backlog** (`BACKLOG_RastreioProvasDigitais_v1_0`) | **v1.0** | **Fonte única de verdade** para escopo de componentes, ordem de entrega, dependências e Definition of Done. |
| **Arquitetura Técnica / DAT** (`DAT_RastreioProvasDigitais`) | v3.0 | Autoridade **apenas** para **stack** e **padrões de arquitetura** (Ports & Adapters, máquina de estados em código, RBAC em profundidade, identificação câmera+manual, tokens de animação). **Ver §2.1 para ressalvas.** |
| **UML** (`UML_RastreioProvasDigitais`) | v3.0 | **DESATUALIZADO. Não usar como referência de domínio.** Ver §2.1. A ser regenerado como tarefa de documentação após a Wave 2. |

### 2.1 Ressalvas críticas (divergências conhecidas entre as versões)

O UML v3.0 e partes do DAT v3.0 foram escritos para um produto anterior (≈9–10 estados, 2 rotas). A v1.0 dos Requisitos/Backlog é a baseline atual e **diverge** nos pontos abaixo. **Sempre siga a coluna "v1.0 (VALE)".**

| Tema | UML/DAT v3.0 (NÃO seguir) | v1.0 — Requisitos/Backlog (VALE) |
| --- | --- | --- |
| Nº de estados | ~10 (`COM_MOTORISTA` único) | **14 estados** (três contextos distintos de "Com Motorista": ida laminação, volta laminação, entrega final) |
| Rotas | 2 (`PADRAO`, `DIRETA`) | **4 rotas**: `matriz`, `lam_matriz`, `filial`, `lam_filial` |
| Definição da rota | Inferida pela localização do vendedor (`determinarRota`) | **Escolhida manualmente pelo Administrador na criação**, livre da localização do vendedor, **imutável** após criar (RN-007) |
| Coluna `rota` | `NULL (set on approval)` | **`NOT NULL` desde a primeira migration**, definida na criação |
| Localização do vendedor | Determina a rota | **Apenas informativa** — não roteia nada (RN-009) |
| Migração de dados (DAT §6 / "Wave 7") | Estratégia v3.0→v4.0 | **NÃO se aplica.** Projeto é greenfield; não há dados legados. Ignorar DAT §6. |
| Referências cruzadas do DAT | "Requisitos v4.0, Seção 6" (Matriz de Acesso) | Nos Requisitos v1.0: **Matriz de Transições = §6**, **Matriz de Acesso = §7** |
| Modelo de perfil (Requisitos §3: "3Studio (Administrador)" = setor único admin) | — | **Setor × Administrador ORTOGONAIS** (W1-C04/DP-1, **o design governa** — ADR-023): `usuarios.setor` = escopo operacional; `usuarios.administrador` = flag de perfil (um Vendedor pode ser Admin). Releitura da Matriz §7: linhas "Exclusivo 3Studio" chaveiam pelo **flag**; escopos operacionais (◐/●) pelo **setor** |
| Etiqueta (o design do Figma omite o código textual e a rota) | — | **RF-003 governa** (W2-C06/DP-1 — ADR-038): a etiqueta SEMPRE traz o **código alfanumérico em destaque** (fonte grande abaixo do QR, posição do Backlog C06) **e a rota** (quinta linha do bloco de campos), mantendo o estilo do design. Etiqueta sem o código quebraria o fallback manual do C10 |
| Detalhe da prova: o mockup mostra **"Rota direta"** (não é um dos 4 valores) | — | **Nome REAL da rota** (W2-C08/DP-7 — ADR-046): "Rota direta" é **texto legado** do mockup; o detalhe exibe `matriz`/`lam_matriz`/`filial`/`lam_filial` via `rotuloRota` (sem categoria derivada). E a **etiqueta deixou de ser admin-only** (DP-8): detalhe/arte/etiqueta são **universais-em-escopo** (qualquer perfil que enxerga a prova pela RLS) |

> **Regra prática:** se a especificação de um componente referenciar algo do DAT que contradiga a tabela acima, prevalece a v1.0. Registre a divergência em `DECISIONS.md` se encontrar uma nova.

---

## 3. Pilares de engenharia (inegociáveis)

Estes pilares têm precedência sobre conveniências de implementação. Todo PR é avaliado contra eles.

1. **Robustez / à prova de erros** — falha isolada nunca corrompe o estado de uma prova nem derruba a app. Error boundaries por rota, degradação graciosa (câmera→digitação manual; offline→reenvio), transições em **transação atômica** (RNF-017) e **mutações idempotentes** (RNF-015).
2. **Escalabilidade** — backend **stateless** (estado no JWT), escala horizontal sem afinidade de sessão, pool de conexões reaproveitado, listagens paginadas server-side, colunas de filtro indexadas (RNF-018, RNF-019).
3. **Mínimo de requisições ao Supabase** — cada ida ao backend é custo. Cache *stale-while-revalidate*, TTL para dados estáveis, agregações server-side em consulta única (sem N+1), **uma única** subscription Realtime no dashboard (sem polling), debounce ≥ 300 ms nas buscas, keep-alive calibrado ao mínimo (RNF-020 a RNF-023).
4. **Animações leves e suaves** — sutis, **somente `transform`/`opacity`** (GPU), durações curtas (≤ 500 ms em page transitions), sempre respeitando `prefers-reduced-motion`. Proibido animar `width/height/top/left` em produção (RF-023 a RF-027, RNF-003, RNF-010).
5. **Observabilidade** — logging estruturado JSON com correlação por `request_id`, captura centralizada de erros (front + back) com alerta em erros críticos, health checks monitorados (RNF-024).

**Custo-alvo do projeto: R$ 0**, dentro dos limites do free tier (Supabase + Cloudflare R2).

---

## 4. Stack tecnológica (conforme DAT §1)

**Frontend**
- **Next.js (App Router), ≥ 14** — usar a última estável; *pinar* a versão exata instalada. SSR + middleware de roteamento (camada superior do RBAC).
- **TypeScript** — `strict: true` obrigatório em todo o projeto.
- **CSS Modules** — escopo local por componente; sem framework CSS externo.
- **Framer Motion** — camada transversal de animação (tokens em `lib/motion/tokens.ts`).
- **Recharts** — gráficos/contadores do dashboard.
- **html5-qrcode** — leitura de QR pela câmera.
- **qrcode.react** — geração do QR na criação.
- **react-signature-canvas** — captura de assinatura digital.

**Backend**
- **Python 3.12** (piso 3.11) · **FastAPI** (async, OpenAPI automático).
- **SQLAlchemy 2.0** async · **Pydantic v2** (validação + enforcement da máquina de estados).
- **Alembic** — migrations versionadas das **tabelas de domínio**.
- **PyJWT ≥ 2.8** — **apenas verifica** a assinatura dos JWT do Supabase Auth. **Nunca emite tokens.** (Não usar `python-jose`.)

**Banco / Auth / Realtime**
- **PostgreSQL via Supabase** (free tier) · **Supabase Auth** (fonte de verdade da autenticação) · **Supabase Realtime** (WebSocket) · **Row Level Security** (camada inferior do RBAC).

**Storage**
- **Cloudflare R2** (S3-compatível, egress zero) · **boto3** — artes das provas.

**Testes**
- **pytest ≥ 8.0** + **pytest-asyncio ≥ 0.23** (unitários) · **httpx AsyncClient** (integração, Postgres real isolado) · **Playwright ≥ 1.40** (E2E, câmera mockada via API de permissões).

---

## 5. Arquitetura

### 5.1 Monorepo (Ports & Adapters / Hexagonal)

```
rastreio-provas-digitais/
├── apps/
│   ├── api/                      # Backend FastAPI (Hexagonal)
│   │   ├── src/
│   │   │   ├── domain/           # Núcleo puro: entidades, value objects, regras
│   │   │   │   └── state_machine/  # rules.py, machine.py, enums.py (Wave 3)
│   │   │   ├── application/      # Casos de uso + PORTAS (interfaces abstratas)
│   │   │   │   └── ports/        # StoragePort, UnitOfWork, etc.
│   │   │   ├── adapters/
│   │   │   │   ├── inbound/http/ # Routers FastAPI, middlewares
│   │   │   │   └── outbound/     # DB (SQLAlchemy), storage (R2/boto3), etiqueta (fpdf2/segno), auth (PyJWT)
│   │   │   ├── infrastructure/   # config, database, logging, app factory
│   │   │   ├── tasks/            # Drivers de tarefas agendadas (keep_alive — W0-C02)
│   │   │   └── main.py           # Composition root (injeção de dependências)
│   │   ├── migrations/
│   │   │   ├── versions/         # Migrations Alembic
│   │   │   └── rls/              # Políticas RLS versionadas (.sql)
│   │   ├── tests/{unit,integration,e2e}/
│   │   ├── alembic.ini · pyproject.toml · Dockerfile · .env.example
│   ├── web/                      # Frontend Next.js
│   │   ├── src/app/              # App Router (rotas + page.tsx)
│   │   ├── src/lib/              # access-matrix.ts, motion/, supabase/
│   │   ├── src/proxy.ts          # Proxy do App Router = RBAC camada superior (Next 16; ex-middleware.ts — ADR-021)
│   │   └── package.json · .env.example
├── docs/                         # Documentação técnica viva
├── .github/workflows/            # CI/CD
├── docker-compose.yml            # Postgres local p/ dev e testes
├── CLAUDE.md · DECISIONS.md · CHANGELOG.md · README.md · SESSION_LOG.md
```

> Mapeamento de caminhos do DAT (relativos à app): `/domain/state_machine/` → `apps/api/src/domain/state_machine/`; `/migrations/rls/` → `apps/api/migrations/rls/`; `/proxy.ts` (ex-`middleware.ts`, renomeado no Next 16 — ADR-021), `/lib/access-matrix.ts`, `/lib/motion/tokens.ts` → `apps/web/src/...`.

### 5.2 Regra de dependência (Hexagonal)

`domain` **não importa nada** de fora (nem framework, nem ORM, nem FastAPI). `application` depende só de `domain` e define **portas** (interfaces). `adapters` implementam as portas. `infrastructure`/`main` fazem o *wiring*. **Dependências apontam sempre para dentro.**

### 5.3 Máquina de estados (Wave 3, mas o glossário vale desde já)

Vive em **código** (`apps/api/src/domain/state_machine/rules.py`), **nunca no banco**. Tabela `TRANSITION_RULES` indexada por `(rota, estado_atual) → [(acao, perfil_autorizado, estado_destino)]`. Sem wildcard/fallback: transição não listada é rejeitada (`422`). Cobertura de testes **≥ 95%** neste módulo.

### 5.4 RBAC — defesa em profundidade

A **Matriz de Acesso (Requisitos §7)** é fonte única. Implementada em **duas camadas independentes**:
- **Superior:** proxy do App Router (`apps/web/src/proxy.ts` — no Next 16 a convenção `middleware` virou `proxy`; ADR-021) + `lib/access-matrix.ts` (Matriz §7 reconciliada com ADR-023; fonte única lida pelo proxy **e** pela UI — `can(perfil, recurso)` / `podeAcessarRota`; Matriz canônica em `access-matrix.cells.json`). *(W1-C05)* o `proxy.ts` enforça por perfil após o refresh: claims via **`getClaims()`** (verificação local), acesso negado → redirect + flash de toast (`RbacFlash`). A proteção de **sessão** segue via `getUser()` (servidor de auth), **nunca** `getSession()`.
- **Inferior:** **RLS** do PostgreSQL, políticas versionadas em `apps/api/migrations/rls/` (uma por perfil × tabela sensível). *(W1-C05)* `usuarios` com RLS por perfil + **helpers** `app_setor()`/`app_is_admin()`/`app_current_user_id()`; o backend honra a RLS propagando claims por requisição (ADR-008/ADR-031: `SET LOCAL ROLE authenticated` + `request.jwt.claims`). A sessão de request é aberta por **`abrir_sessao_rls`** (`create_request_session_factory`), **fail-closed** — transação sem claims **levanta** em vez de cair no role *owner* (`BYPASSRLS`) (ADR-034). *(W2-C06)* **`provas` tem RLS por perfil** (`provas_*.sql` sobre os helpers: vendedor só as suas, motorista só "Em Trânsito", studio/clicheria/admin todas — ADR-039) e existe o **role de runtime não-owner `rastreio_runtime`** (`NOBYPASSRLS`; LOGIN/senha é passo de operação, fora do repo). Espelho de domínio em `apps/api/src/domain/rbac.py`.

> Negação em **qualquer** camada basta. **Toda alteração na Matriz exige PR único cobrindo `access-matrix.ts` E as migrations de RLS** — nunca só um lado.

### 5.5 Camada de animação (Wave 6, tokens desde já)

Tokens em `apps/web/src/lib/motion/tokens.ts` (`DURATION`, `EASING`, `SPRING`). **Proibido literais inline.** Componentes padrão: `<PageTransition>`, `<MotionModal>`, `<AnimatedCounter>`, `<AnimatedTimeline>`, `Toaster`. Hook `useReducedMotion` central zera durações quando `prefers-reduced-motion`. *(Desde o W1-C04 já existem `components/ui/modal/MotionModal` e `components/ui/toast/ToastProvider` — o C19 generaliza sem reescrever; ADR-028.)*

### 5.6 App shell (W1-C04 — layout de TODA a plataforma autenticada)

Grupo de rotas **`apps/web/src/app/(app)/`** com `layout.tsx` único: proteção server-side (`getUser()`), `InactivityGuard`, `ToastProvider` e `<AppShell>` (sidebar preta + área de conteúdo `#eaeaea` raio 40 — tokens `--app-*` em `globals.css`, extraídos 1:1 do design). **Páginas novas plugam criando rotas no grupo** e, se entram no menu, um item em `components/shell/nav-items.ts`. Visibilidade por perfil = C05. Detalhes: `docs/app-shell.md`.

**Usuários (W1-C04):** tabela `usuarios` (PK = UUID de `auth.users`, 1:1 — ADR-024) com `setor`/`localizacao`/`administrador`/`ativo`; provisionamento coordenado via **Admin API** com compensação/adoção de órfãos (ADR-025). **`SUPABASE_SECRET_KEY` é server-only** (só no ambiente do backend; jamais em `NEXT_PUBLIC_*`/cliente). Acesso ao dado SEMPRE via backend (guard de admin — ADR-027). Detalhes: `docs/usuarios.md`.

---

## 6. Glossário de domínio (CANÔNICO — não driftar)

Enums sincronizados Python (Pydantic v2) ↔ PostgreSQL. **Membro Python em MAIÚSCULA; valor em `snake_case`/`lowercase`** (igual ao PG).

**`Setor` / `setor_enum`:** `STUDIO` (`studio`; rótulo de UI "3Studio"), `VENDEDOR`, `MOTORISTA`, `CLICHERIA`
**`Localizacao` / `localizacao_enum`:** `MATRIZ`, `FILIAL` *(apenas informativa; obrigatória SÓ p/ Vendedor e indevida p/ os demais — RN-009/CHECK)*
**Perfil (`usuarios.administrador`):** flag booleano **ortogonal ao setor** (ADR-023); UI exibe `Admin`/`Usuário`
**`Rota` / `rota_enum`:** `matriz`, `lam_matriz`, `filial`, `lam_filial` *(imutável após criação)*
**`Acao` / ação de transição:** `IDENTIFICAR_E_ASSINAR`, `APROVAR`, `REPROVAR`, `REINICIAR_CICLO`, `CANCELAR`
**`EstadoProva` / `status_prova_enum` (14 estados):**

| # | Membro Python | Valor PG | Rotas |
| --- | --- | --- | --- |
| 01 | `CRIADA` | `criada` | todas (inicial) |
| 02 | `ENCAMINHADA_PARA_LAMINACAO` | `encaminhada_para_laminacao` | lam_matriz, lam_filial |
| 03 | `COM_MOTORISTA_IDA_LAMINACAO` | `com_motorista_ida_laminacao` | lam_matriz, lam_filial |
| 04 | `LAMINACAO_CONCLUIDA` | `laminacao_concluida` | lam_matriz, lam_filial |
| 05 | `COM_MOTORISTA_VOLTA_LAMINACAO` | `com_motorista_volta_laminacao` | lam_matriz |
| 06 | `DE_VOLTA_STUDIO_POS_LAMINACAO` | `de_volta_studio_pos_laminacao` | lam_matriz |
| 07 | `RETIRADA_VENDEDOR` | `retirada_vendedor` | matriz, lam_matriz |
| 08 | `ENCAMINHADA_PARA_VENDEDOR` | `encaminhada_para_vendedor` | filial, lam_filial |
| 09 | `APROVADA_VENDEDOR` | `aprovada_vendedor` | todas |
| 10 | `REPROVADA_VENDEDOR` | `reprovada_vendedor` | todas |
| 11 | `DE_VOLTA_STUDIO` | `de_volta_studio` | matriz, lam_matriz |
| 12 | `COM_MOTORISTA_ENTREGA_FINAL` | `com_motorista_entrega_final` | matriz, lam_matriz |
| 13 | `RECEBIDA_CLICHERIA` | `recebida_clicheria` | todas (terminal) |
| 14 | `CANCELADA` | `cancelada` | transversal (terminal) |

**Código identificador da prova:** `PRV-AAAA-MM-NNNNNN` — `NNNNNN` por aleatoriedade criptográfica (`secrets`, estilo nanoid; alfabeto A–Z 0–9 sem ambíguos `0/O`, `1/I/L` — ADR-036; fonte única `domain/provas.py`). É o **mesmo** conteúdo do QR Code, apenas exposto em texto na etiqueta. QR e código resolvem para o **mesmo** registro via `resolver_prova()`.

---

## 7. Roadmap de waves (ordem de execução)

Cada wave só inicia após **todas** as dependências da anterior. **Uma sessão = um componente completo.**

- **Wave 0 — Infra:** `01` Infraestrutura · `02` Cron Keep-Alive
- **Wave 1 — Auth/RBAC:** `03` Login/Sessão · `04` Usuários · `05` Matriz RBAC (2 camadas)
- **Wave 2 — Núcleo:** `06` Cadastro de Prova + Rota + Etiqueta · `07` Listagem/Filtros · `08` Detalhe · `09` Configurações
- **Wave 3 — Fluxo:** `10` Escaneamento (mobile-first) · `11` Máquina de Estados · `12` Assinatura no fluxo · `13` Timeline · `14` Cancelamento · `15` Reinício de ciclo
- **Wave 4 — Dashboard:** `16` Dashboard Realtime
- **Wave 5 — Relatórios/UX:** `17` Relatórios · `18` Atalhos
- **Wave 6 — Animações/Auditoria:** `19` Camada de animações · `20` Log de auditoria (UI)

---

## 8. Definition of Done (global — todo componente)

Antes de marcar um componente como concluído:

- [ ] Code review aprovado.
- [ ] Testes unitários da lógica de negócio: **≥ 80%** em domínio/serviço, **≥ 95%** na máquina de estados.
- [ ] Testes de integração passando em ambiente isolado.
- [ ] Migrations Alembic aplicadas, versionadas e documentadas.
- [ ] Validado contra os **critérios de aceitação** das US vinculadas (Requisitos §5).
- [ ] Validado contra a **Matriz de Acesso** (Requisitos §7) — teste de acesso não autorizado por perfil aplicável.
- [ ] Sem erros no console do browser nem logs críticos no backend.
- [ ] Documentação interna atualizada (README do módulo, comentários).
- [ ] Políticas RLS do componente versionadas em `apps/api/migrations/rls/`.
- [ ] Animações novas validadas com `prefers-reduced-motion` (degradação para instantânea).
- [ ] Escritas verificadas quanto à **idempotência** (RNF-015).
- [ ] Listagens/dashboard sem **N+1**; uso do backend dentro do mínimo de requisições (RNF-020 a 022).
- [ ] Error boundaries cobrindo a rota e caminho de recuperação testado (RNF-014, RNF-016).
- [ ] **Protocolo de encerramento de sessão executado (§10).**

---

## 9. Convenções de código e comandos

**Convenções**
- TypeScript `strict`; Python tipado e validado por **ruff** + **mypy** (`strict`).
- Commits em **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`). Escopo por componente: `feat(w0-c01): ...`.
- **Segredos nunca no código** — apenas em variáveis de ambiente; `.env.example` documenta todas as chaves.
- RLS: **todo** `.sql` existe em `migrations/rls/` **antes** de ser aplicado; reaplicar após qualquer `DROP/recriação` de tabela.
- Sincronização de enums: PR que toca só Python **ou** só o banco é **bloqueado** (ver DAT §4.5).

**Comandos** *(confirmados no W0-C01 e W1-C03 — fonte: README.md)*
```bash
# Backend (apps/api)
cd apps/api && uv sync                      # instalar deps (uv.lock pinado)
uv run uvicorn src.main:app --reload        # dev server → http://localhost:8000/docs
uv run alembic upgrade head                 # migrations (usa MIGRATIONS_DATABASE_URL)
uv run pytest --cov                         # testes + cobertura (offline; @db pula sem Postgres)
uv run ruff check . && uv run mypy          # lint + types (strict; mypy lê files do pyproject)
uv run python -m src.tasks.keep_alive       # keep-alive: ping read-only ao banco (W0-C02; exit 0/≠0)
uv run python -m src.tasks.bootstrap_admin -- --email <email> --nome "<Nome>"
                                            # 1º admin (W1-C04): upsert da linha de domínio a partir
                                            # da conta de auth EXISTENTE (exige SUPABASE_SECRET_KEY)

# Frontend (apps/web)
cd apps/web && pnpm install
pnpm dev                                     # dev server → http://localhost:3000
pnpm build && pnpm lint                      # build (type-check) + lint
pnpm test                                    # vitest (componentes/lógica — RTL/jsdom)  [W1-C03]
pnpm test:e2e                                # Playwright E2E (telas, responsivo)        [W1-C03]
pnpm format:check                            # Prettier

# Infra local
docker compose up -d db                      # Postgres 17 local (cria rastreio + rastreio_test)
```

> Notas operacionais: `alembic.ini` deve permanecer **ASCII puro** (o Alembic lê o `.ini` no encoding do locale — cp1252 no Windows). Testes `@db` usam `TEST_DATABASE_URL` (default: Postgres local) e viram falha com `REQUIRE_DB_TESTS=1` (CI).
>
> **Auth (W1-C03):** front via `@supabase/ssr` (clients browser/servidor + `src/proxy.ts` de refresh; proteção com `getUser()`). O backend **verifica** o JWT do Supabase (**ES256 via JWKS + HS256 fallback**) em `adapters/inbound/http/auth.py`, exposto por `GET /auth/me` (`uv run pytest tests/unit/test_auth.py tests/integration/test_auth_me.py`). Vars de auth: `SUPABASE_URL`, `SUPABASE_JWKS_URL`, `SUPABASE_JWT_SECRET` (api) · `NEXT_PUBLIC_SUPABASE_ANON_KEY` *publishable* (web). PyJWT **só verifica**, nunca emite. Detalhes em `docs/auth.md`.
>
> **Usuários (W1-C04):** gestão exige **`SUPABASE_SECRET_KEY`** no api (server-only; sem ela responde 503) e a migration `0002_usuarios` aplicada (`uv run alembic upgrade head`). Fluxo local: api de pé → `bootstrap_admin` (1º admin) → web em `/usuarios`. Testes @db usam o Postgres local (zonky 5433: `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/rastreio_test`). Detalhes em `docs/usuarios.md` e `docs/app-shell.md`.
>
> **RBAC (W1-C05):** Matriz §7 = fonte única em **`apps/web/src/lib/access-matrix.ts`** (`can`/`podeAcessarRota`) + RLS em **`apps/api/migrations/rls/`** (helpers `app_setor`/`app_is_admin`/`app_current_user_id`). **Regra do PR único:** mudança na Matriz cobre `access-matrix.cells.json` + `access-matrix.ts` + `domain/rbac.py` + as migrations de RLS — junto. Migrations `0004` (hook) + `0005` (RLS de `usuarios`) + `0006` (search_path fixo nas 5 funções — W1-A-004); habilitar o hook no dashboard (Auth → Hooks → `public.custom_access_token_hook`). Proxy decide com **`getClaims()`** (local); sessão de request **fail-closed** via `abrir_sessao_rls` (ADR-034). Testes RBAC (@db; mesma `TEST_DATABASE_URL`): `uv run pytest tests/integration/test_custom_access_token_hook.py tests/integration/test_rls_usuarios.py tests/integration/test_rls_helpers.py tests/integration/test_claims_propagation.py tests/unit/test_equivalencia_matriz.py`; harness de equivalência web em `pnpm test` (`access-matrix.equivalencia.test.ts`). Detalhes em `docs/rbac.md`.
>
> **Provas (W2-C06):** primeira tabela de domínio de provas — migrations **`0007`** (enums `rota_enum`/`status_prova_enum` completos, tabela `provas`, índices RNF-019, **trigger de rota imutável** `trg_provas_rota_imutavel`) + **`0008`** (**RLS de `provas` por perfil** + role de runtime **`rastreio_runtime`** NOBYPASSRLS), espelhos em `migrations/rls/provas_*.sql`/`_runtime_role.sql`. Código **`PRV-AAAA-MM-NNNNNN`** com fonte única em `domain/provas.py` (`gerar_codigo`/`validar_codigo`/`CODIGO_REGEX` — o C10 reutiliza; o **QR codifica o código puro**). **Etiqueta PDF 95×55 mm sob demanda** via `GET /provas/{id}/etiqueta.pdf` (`segno`+`fpdf2`, vetorial, template `EtiquetaTemplate` parametrizável — a configuração é do C09); criação via `POST /provas` (multipart, **exclusivo de admin**; arte JPG/PNG ≤ 10 MB validada por magic bytes, persistida no **R2** — exige as 4 `R2_*`). UI em `/provas/nova`. Testes: `uv run pytest tests/unit/test_provas_dominio.py tests/unit/test_provas_service.py tests/unit/test_etiqueta_pdf.py tests/unit/test_equivalencia_rls_provas.py tests/integration/test_rls_provas.py tests/integration/test_provas_endpoints.py` (@db, mesma `TEST_DATABASE_URL`). Ativar o role de runtime em produção é passo de operação (`docs/provas.md §6`). Detalhes em `docs/provas.md`.
>
> **Listagem de provas (W2-C07):** **`GET /provas`** (prefixo real **`/provas`**, não `/api/provas`) paginado server-side (`page`/`page_size`, teto 100), ordenado `created_at desc`, com **busca** (`busca` = nome **ou** requerimento) e filtros **`cliente`/`status`/`rota`/`vendedor_id`/`criada_de`/`criada_ate`/`finalizada_de`/`finalizada_ate`** → `PaginaProvasOut` (`items[]` com **`vendedor_nome`**+`finalizada_em`, `total`, `page`, `page_size`); **página universal** (Matriz §7) por `get_provas_consulta_service` (**sem** gate de admin — escopo é da RLS), **sem N+1**. **`GET /provas/vendedores`** (dropdown escopado). Migrations **`0010`** (adiciona `provas.finalizada_em` nullable — populada pelo **C11** — + a função **`nomes_de_vendedores(uuid[])`** SECURITY DEFINER que resolve o nome do vendedor sem ampliar a Matriz §7 — DP-7) e **`0011`** (move a função para o schema **`private`** não exposto pela Data API — remediação dos advisors 0028/0029; o backend chama `private.nomes_de_vendedores`); espelho em `migrations/rls/nomes_de_vendedores.sql`. **Todas aplicadas no Supabase real** (`alembic_version=0011`). Rótulos de status (14) em **`apps/web/src/lib/provas/status-labels.ts`** (reutilizável C08/C13/C16). UI em `/provas` (`ProvasView` **replica** a tabela do C04 — DP-1, sem `<DataTable>`; filtros na URL — DP-5; "Ver"→`/provas/[id]`, placeholder C08). Testes: `uv run pytest tests/unit/test_provas_listagem.py tests/integration/test_provas_listagem_endpoints.py` (@db, mesma `TEST_DATABASE_URL`). Detalhes em `docs/provas-listagem.md`.
>
> **Detalhe de provas (W2-C08):** **`GET /provas/{id}`** → `ProvaDetalheOut` (campos da prova + `vendedor_nome` + **`ciclo_atual`**); **`GET /provas/{id}/arte`** = **PROXY** da arte do R2 privado (lê via `StoragePort.download` e streama; **sem** URL pública nem key exposta — DP-5); a **etiqueta** (`GET /provas/{id}/etiqueta.pdf`) **deixou de ser admin-only** e agora é **universal-em-escopo** (DP-8). Os três usam **`get_provas_consulta_service`** (gate universal `Recurso.PROVAS` + RLS): fora do escopo / inexistente → **mesmo 404 genérico** (`prova_nao_encontrada`, mensagem idêntica — anti-enumeração §11). `ProvasConsultaService` ganhou `obter`/`obter_arte`/`gerar_etiqueta`; `ProvasService` ficou só com a criação. Migration **`0012`** (`provas.ciclo_atual integer NOT NULL DEFAULT 1` — nasce 1, **incrementado pelo C15**). UI em `/provas/[id]` (client, `apiFetch`; 404 → toast + `router.replace('/provas')`; "Voltar" = `router.back()`+fallback; etiqueta "Visualizar" em `MotionModal`, "Baixar" via blob; histórico em **empty state** — C13/C11). Rótulos de **rota** em **`apps/web/src/lib/provas/rota-labels.ts`** (reutilizável; espelha o de status). Testes: `uv run pytest tests/unit/test_provas_detalhe.py tests/integration/test_provas_detalhe_endpoints.py` (@db, mesma `TEST_DATABASE_URL`). Detalhes em `docs/provas-detalhe.md`.
>
> **Configurações do sistema (W2-C09 — fecha a Wave 2):** tabela **`system_settings`** chave-valor (migration **`0013`**; `key`/`value` jsonb/`updated_at`/`updated_by`) — guarda só **sobrescritas**; os **defaults e a validação por chave** vivem em **`apps/api/src/domain/settings.py`** (`SETTINGS: dict[str, SettingSpec]`; chaves: **`delay_horas_uteis`** int 1..9999 padrão 48 — RN-008/US-016; **`etiqueta_template`** objeto `{modo, largura, altura, margem, fonte, qr_zona_quieta_modulos}` — RN-011/DP-5). **RLS** (`migrations/rls/system_settings_*.sql`): **leitura `authenticated`** (valor não-sigiloso; alimenta C16/C06 na sessão RLS do request), **escrita admin-only** (`app_is_admin()`), **sem DELETE**. Endpoints **`GET /settings`** + **`PUT /settings/{chave}`** (prefixo real **sem `/api`**) por **`get_settings_service`** (gate `Recurso.CONFIGURACOES` + RLS — exclusivo 3Studio pelo flag `administrador`). **Sem cache (DP-4):** leitura fresca = imediato (US-016); upsert idempotente (RNF-015). **Integração da etiqueta (C06):** `EtiquetaPort.gerar_pdf(prova, vendedor_nome, config)` + `ProvasConsultaService` lê `etiqueta_template` e passa ao gerador (`personalizado` aplica os 5 campos; `padrao`/falha → template padrão). UI em `/configuracoes` (cards + **Salvar por card**; `lib/api/configuracoes.ts`). Testes: `uv run pytest tests/unit/test_settings_dominio.py tests/unit/test_settings_service.py tests/unit/test_equivalencia_rls_system_settings.py tests/integration/test_settings_endpoints.py tests/integration/test_rls_system_settings.py` (@db, mesma `TEST_DATABASE_URL`). Detalhes em `docs/configuracoes.md`.
>
> **Escaneamento (W3-C10 — abre a Wave 3):** identificação física→digital. **`POST /provas/identificar`** (prefixo real **sem `/api`**; `IdentificarIn{codigo}` → `ProvaDetalheOut`) por **`get_identificacao_service`** (gate **`Recurso.ESCANEAR`** — universal; escopo pela RLS de `provas`). `ProvasIdentificacaoService.identificar` (o `resolver_prova()` do backlog): **rate limit → commit → normaliza → valida formato → resolve por código**. **QR e manual = mesmo caminho** (o QR é o código puro do C06). **Anti-enumeração (RN-014):** malformado/inexistente/fora-de-escopo → **mesmo 404** `prova_nao_encontrada` (reuso do erro do C08). **Rate limiting 30/usuário/min** = contador Postgres de janela fixa: tabela **`rate_limit_contadores`** (migration **`0014`**, 1 linha/`(user_id,chave)`, upsert atômico que reseta por minuto) + **RLS `rate_limit_contadores_self`** (`FOR ALL`, `user_id=app_current_user_id()`, sem DELETE — espelhos em `migrations/rls/rate_limit_contadores_*.sql`); `LimiteDeTentativasError` → **429**. Código nunca é logado (RNF-024). Fonte única do formato: `domain/provas.py` (`normalizar_codigo`/`validar_codigo`/`CODIGO_REGEX`); espelho no front em **`apps/web/src/lib/provas/codigo.ts`**. UI em **`/escanear`** (mobile-first: câmera **html5-qrcode** in-app com degradação graciosa + manual com máscara `PRV-AAAA-MM-XXXXXX`; `lib/api/escaneamento.ts`) → navega à **tela de confirmação `/provas/[id]/confirmar`** (nome+requerimento+placeholder de assinatura — C11/C12 plugam). O C10 **só identifica**. Testes: `uv run pytest tests/unit/test_provas_identificacao.py tests/integration/test_provas_identificacao_endpoints.py tests/integration/test_rls_rate_limit.py` (@db, mesma `TEST_DATABASE_URL`). Detalhes em `docs/escaneamento.md`.

---

## 10. Protocolo de encerramento de sessão (OBRIGATÓRIO)

Ao final de **toda** sessão de trabalho, **antes** de encerrar, o Claude Code deve atualizar os documentos de contexto para que a próxima sessão tenha o máximo de contexto:

1. **`CHANGELOG.md`** — adicionar as mudanças da sessão em `[Unreleased]` (categorias *Added/Changed/Fixed/...*), referenciando o componente (ex.: `W0-C01`).
2. **`DECISIONS.md`** — registrar como ADR **toda** decisão de arquitetura/biblioteca/trade-off tomada na sessão (inclusive as que confirmam decisões "Propostas").
3. **`SESSION_LOG.md`** — nova entrada cronológica: data, objetivo (componente), o que foi feito, decisões, **pendências/itens em aberto** e **próximo passo**.
4. **`CLAUDE.md`** — atualizar **somente** se algo estrutural mudou (comandos, stack, convenção, glossário). Mantê-lo enxuto e verdadeiro.
5. **`README.md`** — atualizar setup/comandos/roadmap se mudaram.
6. Verificar a **Definition of Done (§8)** do componente e marcar o status no roadmap.
7. Deixar a árvore de trabalho limpa: commits semânticos, sem TODOs órfãos, sem segredos versionados.

> Nunca encerre uma sessão sem executar este protocolo. A continuidade de contexto depende disso.

---

## 11. O que NÃO fazer

- ❌ Não inferir rota por localização do vendedor. Rota é **manual e imutável**.
- ❌ Não usar o modelo de 2 rotas / ~10 estados do UML v3.0.
- ❌ Não colocar regras de transição no banco — elas vivem em `rules.py`.
- ❌ Não criar tabelas de domínio pelo painel do Supabase — só via Alembic.
- ❌ Não criar/alterar RLS sem versionar o `.sql` em `migrations/rls/`.
- ❌ Não emitir JWT no backend (Supabase Auth emite; PyJWT só verifica).
- ❌ Não animar `width/height/top/left`; só `transform`/`opacity`.
- ❌ Não adicionar polling no dashboard (uma subscription Realtime).
- ❌ Não revelar a existência/ator de uma prova fora do escopo (anti-enumeração: mensagem genérica idêntica para "não existe" e "sem permissão").
- ❌ Não escrever literais de duração/easing fora de `motion/tokens.ts`.
- ❌ Não implementar a migração de dados do DAT §6 (greenfield, sem dados legados).
