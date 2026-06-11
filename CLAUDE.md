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
│   │   │   │   └── outbound/     # DB (SQLAlchemy), storage (R2/boto3), auth (PyJWT)
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
│   │   ├── src/middleware.ts     # Middleware RBAC (camada superior)
│   │   └── package.json · .env.example
├── docs/                         # Documentação técnica viva
├── .github/workflows/            # CI/CD
├── docker-compose.yml            # Postgres local p/ dev e testes
├── CLAUDE.md · DECISIONS.md · CHANGELOG.md · README.md · SESSION_LOG.md
```

> Mapeamento de caminhos do DAT (relativos à app): `/domain/state_machine/` → `apps/api/src/domain/state_machine/`; `/migrations/rls/` → `apps/api/migrations/rls/`; `/middleware.ts`, `/lib/access-matrix.ts`, `/lib/motion/tokens.ts` → `apps/web/src/...`.

### 5.2 Regra de dependência (Hexagonal)

`domain` **não importa nada** de fora (nem framework, nem ORM, nem FastAPI). `application` depende só de `domain` e define **portas** (interfaces). `adapters` implementam as portas. `infrastructure`/`main` fazem o *wiring*. **Dependências apontam sempre para dentro.**

### 5.3 Máquina de estados (Wave 3, mas o glossário vale desde já)

Vive em **código** (`apps/api/src/domain/state_machine/rules.py`), **nunca no banco**. Tabela `TRANSITION_RULES` indexada por `(rota, estado_atual) → [(acao, perfil_autorizado, estado_destino)]`. Sem wildcard/fallback: transição não listada é rejeitada (`422`). Cobertura de testes **≥ 95%** neste módulo.

### 5.4 RBAC — defesa em profundidade

A **Matriz de Acesso (Requisitos §7)** é fonte única. Implementada em **duas camadas independentes**:
- **Superior:** middleware do App Router (`apps/web/src/middleware.ts`) + tabela determinística `lib/access-matrix.ts` `{ rota: [perfis, escopo] }` (lida por middleware **e** UI via hook `useAuthorization`).
- **Inferior:** **RLS** do PostgreSQL, políticas versionadas em `apps/api/migrations/rls/` (uma por perfil × tabela sensível).

> Negação em **qualquer** camada basta. **Toda alteração na Matriz exige PR único cobrindo `access-matrix.ts` E as migrations de RLS** — nunca só um lado.

### 5.5 Camada de animação (Wave 6, tokens desde já)

Tokens em `apps/web/src/lib/motion/tokens.ts` (`DURATION`, `EASING`). **Proibido literais inline.** Componentes padrão: `<PageTransition>`, `<MotionModal>`, `<AnimatedCounter>`, `<AnimatedTimeline>`, `Toaster`. Hook `useReducedMotion` central zera durações quando `prefers-reduced-motion`.

---

## 6. Glossário de domínio (CANÔNICO — não driftar)

Enums sincronizados Python (Pydantic v2) ↔ PostgreSQL. **Membro Python em MAIÚSCULA; valor em `snake_case`/`lowercase`** (igual ao PG).

**`Setor` / `setor_enum`:** `STUDIO`, `VENDEDOR`, `MOTORISTA`, `CLICHERIA`
**`Localizacao` / `localizacao_enum`:** `MATRIZ`, `FILIAL` *(apenas informativa)*
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

**Código identificador da prova:** `PRV-AAAA-MM-NNNNNN` — `NNNNNN` por **nanoid** (alfabeto A–Z 0–9 sem ambíguos `0/O`, `1/I/L`). É o **mesmo** conteúdo do QR Code, apenas exposto em texto na etiqueta. QR e código resolvem para o **mesmo** registro via `resolver_prova()`.

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

**Comandos** *(confirmados no W0-C01 — fonte: README.md)*
```bash
# Backend (apps/api)
cd apps/api && uv sync                      # instalar deps (uv.lock pinado)
uv run uvicorn src.main:app --reload        # dev server → http://localhost:8000/docs
uv run alembic upgrade head                 # migrations (usa MIGRATIONS_DATABASE_URL)
uv run pytest --cov                         # testes + cobertura (offline; @db pula sem Postgres)
uv run ruff check . && uv run mypy          # lint + types (strict; mypy lê files do pyproject)
uv run python -m src.tasks.keep_alive       # keep-alive: ping read-only ao banco (W0-C02; exit 0/≠0)

# Frontend (apps/web)
cd apps/web && pnpm install
pnpm dev                                     # dev server → http://localhost:3000
pnpm build && pnpm lint                      # build + lint
pnpm format:check                            # Prettier

# Infra local
docker compose up -d db                      # Postgres 17 local (cria rastreio + rastreio_test)
```

> Notas operacionais: `alembic.ini` deve permanecer **ASCII puro** (o Alembic lê o `.ini` no encoding do locale — cp1252 no Windows). Testes `@db` usam `TEST_DATABASE_URL` (default: Postgres local) e viram falha com `REQUIRE_DB_TESTS=1` (CI).

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
