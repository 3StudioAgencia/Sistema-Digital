# SESSION_LOG.md

> Diário cronológico de sessões de trabalho. Cada sessão = um componente (em geral). Entrada mais recente no topo.
> Preenchido ao final de cada sessão pelo **Protocolo de Encerramento** (`CLAUDE.md §10`).

---

## Modelo de entrada (copiar para cada nova sessão)

```
## Sessão NN — AAAA-MM-DD — [Wave X / Componente CYY] Título

**Objetivo:** (o componente/escopo da sessão)

**Feito:**
- ...

**Decisões (ADRs):**
- ADR-XXX: ... (link/ref em DECISIONS.md)

**Testes / cobertura:**
- ...

**Pendências / em aberto:**
- [ ] ...

**Próximo passo:**
- (próximo componente conforme dependências do Backlog)

**Definition of Done:** (✅ atendida / ⚠️ parcial — detalhar)
```

---

## Sessão 13 — 2026-06-16 — [Wave 3 / Componente C10] Escaneamento (Câmera + Manual, mobile-first) — ABRE A WAVE 3

**Objetivo:** A ponte física→digital — identificar a prova pela leitura do QR (in-app) ou pela digitação manual, com um endpoint único e idempotente, tudo mobile-first, robusto (câmera negada → manual) e seguro (anti-enumeração + rate limiting). O C10 **só identifica**; transição é C11, assinatura é C12.

**Decisões (respostas dos Pontos de Decisão §4 — confirmadas pelo dono):**
- **DP-1 (bloqueante):** mantido o **formato canônico do C06** `PRV-AAAA-MM-NNNNNN`; a máscara "3S-/8 dígitos" do design é **legado**. Input com prefixo fixo `PRV-` + máscara `AAAA-MM-XXXXXX`; cliente em maiúsculas, **servidor normaliza** (`strip().upper()`) antes de validar. (ADR-052)
- **DP-2:** destino pós-identificação = **uma nova tela de confirmação** (`/provas/[id]/confirmar`) mostrando **nome + requerimento + status** + **placeholder de assinatura** (C12) e "Confirmar movimentação" desabilitado (C11). Não é o detalhe do C08. (ADR-053)
- **DP-3:** rate limiting = **contador Postgres de janela fixa** (`rate_limit_contadores`, 1 linha/ator, upsert atômico, reset por minuto, RLS `self`, sem DELETE); anti-enumeração por reuso do 404 do C08. (ADR-054)
- **DP-4:** lib de câmera = **html5-qrcode** (stack §4); mobile-first de fato (CSS base mobile, safe areas, terço inferior, degradação graciosa). (ADR-055)
- **DP-5:** "Última leitura" = indicador local/sessão; "Ver histórico" = placeholder (C13). (ADR-056)

**Feito:**
- **Grounding (workflow de 5 agentes):** confirmou o formato/regex/charset do C06 (`domain/provas.py`), o QR = código puro, que `resolver_prova()` **não existia** (é do C10), o padrão anti-enum/RLS/DI, a ausência de Redis (só Postgres), e o scaffolding do front (`/escanear` já no nav como placeholder; html5-qrcode **não instalado**).
- **Backend:** `domain/provas.normalizar_codigo` + `LimiteDeTentativasError` (429); `RateLimiterPort` + `SqlAlchemyRateLimiter` (upsert atômico com `app_current_user_id()`); `ProvasRepositoryPort.buscar_por_codigo`; `ProvasIdentificacaoService` (rate limit→commit→normaliza→valida→resolve); `get_identificacao_service` (gate `Recurso.ESCANEAR`); `POST /provas/identificar` (`IdentificarIn`→`ProvaDetalheOut`); `errors.py` mapeia 429; migration **`0014`** (`rate_limit_contadores` + RLS) + espelhos `.sql`; `RateLimitContadorRow` no models.
- **Frontend:** `lib/provas/codigo.ts` (espelho do formato) + `lib/api/escaneamento.ts`; `/escanear` (`EscanearView` + `CameraScanner` com import dinâmico de html5-qrcode + degradação graciosa; `EntradaManual` com máscara; toggle radiogroup; flash de sucesso; rodapé DP-5) + `escanear.module.css` **mobile-first**; `/provas/[id]/confirmar` (view + css). `html5-qrcode ^2.3.8` adicionado.
- **Validação contra Postgres real:** subido o cluster in-repo `.tmp-pg` (PG, porta 5433); corrigido um **desync** (alembic_version=0014 sem a tabela — crash de shutdown do embedded-postgres) via `stamp 0013` + `upgrade head`; ciclo up/down/up do `test_migrations` verde.
- **Revisão adversarial (workflow de 17 agentes, 4 dimensões × verificadores céticos):** 13 achados brutos → **3 confirmados** (1 baixo, 2 médios), corrigidos (ADR-057): anti-enum por comprimento (`IdentificarIn.codigo` `str` puro, comprimento tratado no serviço → mesmo 404, contado no limite); **leak de câmera** em race de unmount-durante-`start()` (`vivoRef` + para o track local na resolução tardia, com teste de regressão); touch target do toggle 42→48px.

**Testes / cobertura:**
- **api: 486 verdes, cobertura 94,55%** (domínio de provas 100%) — unit (`test_provas_identificacao`) + @db (`test_provas_identificacao_endpoints`, `test_rls_rate_limit`, `test_migrations` head 0014). Cobre **idempotência QR/manual** (mesmo registro), **anti-enumeração** (inválido==inexistente==fora-de-escopo, mensagem idêntica), **429** + isolamento por usuário, **RLS do contador**.
- **web: 136 verdes** (`codigo.test.ts`, `escanear-view.test.tsx` — incl. câmera negada→manual e QR==manual mesmo destino, `confirmar-view.test.tsx`) + **E2E** `escanear.spec.ts` (redirect sempre; live opt-in). `ruff`/`mypy --strict`/`lint`/`build`/`format:check` limpos.

**Pendências / em aberto:**
- [ ] **Migration `0014` no Supabase real** (operação de fechamento — não quebra o existente; o C10 não roda em prod sem ela). Padrão das waves anteriores (aplicar via MCP).
- [ ] (Herdadas) segredos `R2_*`/role de runtime/leaked-password protection no dashboard.

**Próximo passo:**
- **W3-C11 — Máquina de Estados (14 estados, 4 rotas):** `TRANSITION_RULES` em `domain/state_machine/rules.py` (cobertura ≥ 95%); pluga no botão "Confirmar movimentação" da tela de confirmação do C10 e popula `finalizada_em`/`ciclo_atual`.

**Definition of Done:** ✅ atendida (testes ≥80% domínio/serviço; anti-enumeração e idempotência QR/manual cobertas; sem erro de console/log crítico; error boundary `(app)` cobre a rota + degradação graciosa da câmera; animações com `prefers-reduced-motion`; RLS versionada; sem segredos versionados). ⚠️ **migration `0014` ainda não aplicada no Supabase real** (item de operação acima).

---

## Sessão 12 — 2026-06-15 — [Wave 2 / Componente C09] Tela de Configurações do Sistema (FECHA A WAVE 2)

**Objetivo:** Configurações do sistema (RF-022), exclusivas do 3Studio: tempo de atraso (RN-008/US-016) e template de etiqueta (RN-011), persistidos em `system_settings` com RLS, consumíveis server-side (etiqueta C06 agora; dashboard C16 depois). Último componente da Wave 2.

**Decisões (respostas dos Pontos de Decisão §4 — tudo conforme recomendado):**
- **DP-1** modelo **chave-valor** (`system_settings`) + registro de domínio (defaults/validação por chave). **DP-2** RLS **leitura `authenticated`** / **escrita admin-only** (valores não-sigilosos alimentam C16/C06 na própria sessão RLS — sem SECURITY DEFINER). **DP-3** página **3Studio-only** pelo flag `administrador` (proxy C05 + gate `Recurso.CONFIGURACOES` + RLS). **DP-4** **sem cache** — leitura fresca = imediato (US-016). **DP-5** "personalizado" = sobrescrita dos **5 campos do `EtiquetaTemplate`** do C06 (o gerador só passa a **ler** a config). **DP-6** settings desta sessão = **tempo de atraso + template**, **save por card**.

**Feito:**
- **Recon (workflow de 7 agentes)** confirmou o estado real e divergências do prompt: o recurso/rota/nav **`configuracoes` já existiam** (C05, admin-only); **não há cache** no `apps/api`; o `EtiquetaTemplate` do C06 expõe **só 5 campos**; prefixo HTTP real é **sem `/api`**; próxima migration **0013**; próximo ADR **047**.
- **Backend:** migration **`0013`** (`system_settings` chave-valor + RLS: SELECT authenticated, INSERT/UPDATE admin, sem DELETE) + espelhos `migrations/rls/system_settings_*.sql`. Domínio `domain/settings.py` (registro de chaves: defaults/validação + `ConfiguracaoEtiqueta` + `efetivar_*`); `SettingsRepositoryPort`/`SqlAlchemySettingsRepository` (upsert idempotente, sem commit); `SettingsService` (`listar`/`salvar`/`obter_config_etiqueta`); router `/settings` (`GET`+`PUT/{chave}`) gateado por `get_settings_service`. **Integração C06:** `EtiquetaPort.gerar_pdf(... , config)`; `_template_efetivo`; `ProvasConsultaService.gerar_etiqueta` lê a config na mesma sessão RLS.
- **Frontend:** `/configuracoes` (server fino → `ConfiguracoesView` client): cards **Tempo de atraso** e **Template de etiqueta** com **Salvar por card**, validação em tempo real, estados carregando/erro(retry)/**restrito (403)**, toast; `lib/api/configuracoes.ts`. Segmented Modo com pílula `layoutId` + teclado WAI-ARIA; reveal por `AnimatePresence`; reduced-motion. `nav-items.ts` sem o marcador placeholder.
- **Revisão adversarial (workflow de 14 agentes, 4 dimensões × verificadores céticos):** **7 confirmados** (2 médios, 5 baixos), todos corrigidos — **`qr_zona_quieta_modulos`** ignorado (lia `self._t`, não o template efetivo) → fix + teste por bytes; segmented sem teclado → navegação WAI-ARIA; save-padrão gravava dimensões antigas → grava defaults; `toastRef` morto removido; +testes (save-padrão, teclado, reduced-motion, payload completo).
- **Deploy:** migration **`0013`** aplicada no **Supabase real** via MCP (tabela + RLS + 3 policies + bump `alembic_version=0013`); advisors de segurança sem achados novos.
- **Refino pós-entrega (a pedido do dono):** padding horizontal maior no segmented de **Modo** (`.segmentoItem`) — vale para "Padrão" e "Personalizado".
- **Docs:** `docs/configuracoes.md`; **ADR-047 a ADR-051**; CLAUDE.md §9.

**Testes / cobertura:**
- api: **461 verdes (offline + `@db`, PG 17 local 5433), cobertura 95%** — `test_settings_dominio.py`, `test_settings_service.py`, `test_equivalencia_rls_system_settings.py`, `test_etiqueta_pdf.py` (config + qr), `test_settings_endpoints.py` (@db: defaults, delay imediato, 422, **403 não-3Studio**, etiqueta padrão×personalizado), `test_rls_system_settings.py` (@db: escrita admin-only, leitura authenticated, sem DELETE), `test_migrations.py` (head `0013`). `ruff`/`ruff format`/`mypy --strict` limpos.
- web: **122 verdes** (`configuracoes-view.test.tsx`: render, salvar delay+toast, validação sem API, personalizado revela+salva objeto completo, save-padrão, teclado, reduced-motion, 403→restrito, erro→retry); E2E `e2e/configuracoes.spec.ts` (proteção + live opt-in). `pnpm lint`/`build` limpos.

**Pendências / em aberto:**
- [x] **Migration `0013` aplicada no Supabase real** (via MCP): `alembic_version=0013`, `system_settings` + RLS (3 policies); advisors sem achados novos (os 2 pré-existentes — RLS-no-policy do `alembic_version` lockado e leaked-password — permanecem).
- [ ] **Responsável (operação):** nada novo obrigatório p/ o C09 (a página funciona com os defaults; o admin salva quando quiser). Pendências antigas seguem (R2_*, política de senha, leaked-password protection).
- [ ] **Wave 2 concluída** — sugerir **auditoria da Wave 2** (C06→C09) antes da Wave 3, como na Wave 1.

**Próximo passo:**
- **W3-C10 · Escaneamento por Câmera + Fallback Manual (Mobile-First)** — abre a Wave 3 (fluxo de movimentação). Sugerido **auditar a Wave 2** antes.

**Definition of Done:** ✅ atendida (code review adversarial + remediação; testes ≥80% domínio/serviço; migration+RLS versionadas e aplicadas; acesso negado a não-3Studio em middleware **e** RLS; sem erros de console/log; docs do módulo; error boundary do grupo `(app)`; animações com reduced-motion; sem segredos versionados).

---

## Sessão 11 — 2026-06-15 — [Wave 2 / Componente C08] Visualização de Prova (Detalhe)

**Objetivo:** Página de detalhe da prova (`/provas/[id]`): arte, metadados completos, rota/status, ciclo atual, ações de etiqueta (visualizar/baixar) e o histórico em empty state — universal, com escopo pela RLS e redirect sem vazar existência.

**Feito:**
- **Recon (workflow de 5 agentes)** confirmou o estado de C04/C05/C06/C07 e revelou divergências do prompt: `useAuthorization` **não existe** (C05 = `access-matrix`+proxy+`RbacFlash`); a etiqueta do C06 era **admin-only** (colidia com o detalhe universal); não havia `GET /provas/{id}`; a `StoragePort` **não tem URL pré-assinada**; rótulos de rota viviam em `lib/api/provas.ts`.
- **Backend:** migration **`0012`** (`provas.ciclo_atual` NOT NULL default 1 — DP-1); `ProvasConsultaService` ganhou `obter`/`obter_arte`/`gerar_etiqueta` (+ deps opcionais `storage`/`etiqueta`); `ProvasService` perdeu a etiqueta (só criação). Endpoints `GET /provas/{id}` (detalhe), `GET /provas/{id}/arte` (**proxy** do R2 — DP-5) e etiqueta migrada para o serviço **universal RLS-escopado** (DP-8) — os três por `get_provas_consulta_service`; fora-do-escopo == inexistente == **mesmo 404** (anti-enumeração §11).
- **Frontend:** `/provas/[id]` (server fino `key={id}` + `ProvaDetalheView` client): busca `obterProva`; 404 → toast + `router.replace('/provas')`; arte por proxy (blob→objectURL→`<img>`); "Visualizar etiqueta" em `MotionModal`, "Baixar" via blob; "Voltar" = `router.back()`+fallback; histórico em empty state. Módulo **`lib/provas/rota-labels.ts`** (DP-7); `ProvaDetalhe`/`obterProva`/`baixarArte`; token `--app-card-white`.
- **Revisão adversarial (workflow de 14 agentes, 4 dimensões × verificadores céticos):** 10 achados, **5 confirmados (todos baixos)**, corrigidos: arte ausente no R2 de prova visível → **404** (não 503) + log de órfã; **vazamento do objectURL** da etiqueta no unmount com modal aberto → efeito de cleanup; 2 docstrings-fóssil (topo de `http/provas.py`; `(DP-7)`→`(RF-003)` em `provas.ts`).
- **Refino de animações (pós-entrega, a pedido do dono):** fade-in da arte ao carregar o blob; cascata do card de histórico após o de detalhe (`delay 0.07`); feedback tátil (`SPRING` `scale 0.97`) em Voltar/Visualizar/Baixar — tudo transform/opacity + reduced-motion. + ajustes manuais de layout do dono (bordas removidas do Voltar/card; fontes `nome`/`campoValor` levemente menores).
- **Etiqueta — molduras pontilhadas removidas (C06, a pedido do dono):** o PDF saía com 4 caixas tracejadas (`_caixa_pontilhada`) "como no design"; removidas as chamadas + o helper (`set_dash_pattern`). Mantidos os contornos sólidos e o texto; verificado por render. Emenda à ADR-038. `test_etiqueta_pdf.py` verde.

**Decisões (ADRs):**
- **ADR-046** (DP-1..DP-8): `ciclo_atual` (0012, incrementado pelo C15); histórico empty state (fronteira C11/C13); sem botões Cancelar/Reiniciar (C14/C15); preview de etiqueta em modal; **arte por proxy** (rejeitada a pré-assinada); 404 idêntico + Voltar=back+fallback; módulo de rótulos de rota; **etiqueta universal-em-escopo** (deixou de ser admin-only). Reconciliações de design na CLAUDE.md §2.1.

**Testes / cobertura:**
- api: **263 offline / 395 com `@db`** (`REQUIRE_DB_TESTS=1`, PG 17 local 5433) — novos `test_provas_detalhe.py` (serviço: detalhe/arte/etiqueta, 404 genérico, arte-antes-do-storage, arte ausente→404, fallback `-`) e `test_provas_detalhe_endpoints.py` (@db: **escopo por perfil**, **anti-vazamento** fora-do-escopo==inexistente com mensagem idêntica, `ciclo_atual`/`vendedor_nome`, proxy da arte, etiqueta universal); `test_provas_endpoints.py` (etiqueta acessível ao vendedor dono); `test_migrations.py` (head 0012). `ruff`/`ruff format`/`mypy --strict` limpos.
- web: **113 verdes** (`prova-detalhe-view.test.tsx`: render fiel, arte por proxy, 404→toast+redirect, baixar/visualizar etiqueta, Voltar, erro+retry, revogação do objectURL no unmount); E2E `e2e/prova-detalhe.spec.ts` (proteção + live opt-in). `pnpm lint`/`format:check`/`build` limpos.

**Pendências / em aberto:**
- [x] **Migration `0012` aplicada no Supabase real** (via MCP, **pós-entrega**, ao diagnosticar a listagem quebrada — ver abaixo): `alembic_version=0012`, coluna `ciclo_atual` NOT NULL default 1; advisors de segurança sem achados novos.
- [ ] Rodar `pnpm test:e2e` com `E2E_LIVE=1` quando houver stack + sessão (suite live opt-in). Demais pendências de operação do C06/C07 (vars `R2_*`, role de runtime, leaked-password) seguem em `DECISIONS.md`.

**Incidente pós-entrega (mesma sessão):** a tela `/provas` (listagem do C07) parou de carregar ("Não foi possível carregar as provas"). **Causa:** o C08 adicionou `ciclo_atual` ao modelo ORM **compartilhado** `ProvaRow`, então `select(ProvaRow)` (listagem E detalhe) passou a projetar `provas.ciclo_atual`; como a `0012` ainda **não** estava aplicada no Supabase real (estava em `0011`), a query batia em coluna inexistente → 500. **Mesmo padrão do C07** (a `0010` que faltava derrubou a listagem). **Fix:** aplicada a `0012` em produção (SQL de `alembic upgrade 0011:0012 --sql` + bump do `alembic_version`); listagem volta a carregar. **Lição:** migration que altera o modelo ORM compartilhado precisa ir a produção **junto** com o deploy do código (a `0012` deveria ter sido aplicada no encerramento, como C06/C07 fizeram com 0009/0011).

**Próximo passo:**
- **W2-C09 · Tela de Configurações do Sistema** (parametrização da etiqueta — RN-011 — e demais ajustes).

**Definition of Done:** ✅ atendida (testes ≥80% domínio/serviço; integração @db verde; migration versionada/up-down **e aplicada em produção**; escopo por perfil + anti-vazamento testados; arte sem URL pública; error boundary do grupo; animações com `prefers-reduced-motion`; sem segredos versionados; gates verdes).

---

## Sessão 10 — 2026-06-15 — [Wave 2 / Componente C07] Listagem, Pesquisa e Filtros de Provas

**Objetivo:** Entregar a tela de **operação diária** — listar/buscar/filtrar provas com paginação server-side, escopo por perfil (UI + RLS), tabela igual à do C04.

**Grounding (antes de codar):** investigação multi-agente do estado real (C04/C05/C06) que **corrigiu 3 premissas do prompt**: (1) **não existe** `useAuthorization(...).scope` — C05 só entregou RBAC de página (`can`/`podeAcessarRota`); (2) o prefixo real é **`/provas`**, não `/api/provas`; (3) **descoberto** que a coluna "Vendedor" quebraria sob a RLS de `usuarios` para 3Studio/Clicheria não-admin e Motorista.

**Decisões do dono (Pontos de Decisão, 1 rodada):** DP-1 = **Replicar** a tabela do C04 (não extrair `<DataTable>`); DP-5 = **scroll infinito + filtros na URL**; DP-4 = **rótulos curtos por estado (14)**; DP-7 (descoberto) = **função SECURITY DEFINER id→nome**. DP-2/DP-3/DP-6 = recomendações (adaptar barra por escopo; adicionar `finalizada_em`; `GET /provas` sem gate de admin, "Ver"→`/provas/[id]`). → ADR-041 a ADR-045.

**Feito:**
- **Backend:** migration **`0010_listagem_provas`** (`provas.finalizada_em timestamptz NULL` + índice parcial; função **`public.nomes_de_vendedores(uuid[])`** SECURITY DEFINER + espelho `migrations/rls/`). Porta `ProvasRepositoryPort` estendida (`FiltrosProvas`/`PaginaProvas`, `listar`/`vendedor_ids_distintos`/`nomes_de_vendedores`); `ProvasConsultaService`; dependência **`get_provas_consulta_service`** (universal, sessão RLS fail-closed); endpoints **`GET /provas`** (busca+filtros+paginação, ordem `created_at desc`, sem N+1) e **`GET /provas/vendedores`** (dropdown escopado).
- **Frontend:** `/provas` real (`ProvasView` replicando a tabela do C04 — C04 intocado), barra de filtros de 2 linhas, **estado na URL** (debounce 300ms, "Limpar"), **adaptação por perfil** (esconde Vendedor no escopo "as próprias"), "Ver"→`/provas/[id]` (placeholder **C08**); módulo `lib/provas/status-labels.ts` (14 rótulos); `escopoDeProvas`/`listarProvas`/`listarVendedoresProvas`. Animações por tokens; cards no mobile; loading/vazio/erro.

**Decisões (ADRs):** ADR-041 (replicar tabela + listagem universal), ADR-042 (filtros na URL + scroll infinito), ADR-043 (rótulos curtos/14), ADR-044 (`finalizada_em` aditiva, populada pelo C11), ADR-045 (nome do vendedor via SECURITY DEFINER, **endurecida na remediação** para re-aplicar o escopo do chamador) — todas **Aceitas**.

**Remediação da revisão adversarial (5 dimensões × verificadores céticos; 8/13 confirmados):** (alta) `ruff format` nos 3 arquivos novos — o gate de CI é `ruff format --check`, que eu não rodara; (média) `fetchUsuarioAtual` memoizado com React `cache()` (a página não re-busca o `/usuarios/me` do layout); (média a11y) `aria-label` redundante removido dos inputs envolvidos por `<label>` (WCAG 2.5.3); (baixa segurança) `nomes_de_vendedores` re-aplica o escopo do chamador no corpo (fecha o vetor de RPC direto do PostgREST); (baixas) data em UTC, `:focus-visible`, espaçador do "Limpar". Não corrigido por ser correto: literal de stagger `0.025` (cópia fiel do C04 — vai para o C19).

**Testes / cobertura:**
- **api 377 verdes** (`ruff format`/`ruff`/`mypy --strict` limpos): escopo por perfil @db incl. **3Studio não-admin e Motorista resolvendo o nome** (DP-7); **chamada RPC-style da função como Vendedor com id alheio → vazio** (hardening); filtros combináveis; busca nome/requerimento; períodos; paginação+ordenação; **contador de SELECTs provando ausência de N+1**; dropdown escopado; 401/403; `0010` up/down em `test_migrations`.
- **web 104 verdes** (lint 0 erros — 2 warnings pré-existentes em C04/C06; `build`/`format:check` ok): `provas-view.test.tsx` (render fiel, debounce, hidratação da URL, filtro→URL, adaptação por perfil, "Limpar", "Ver", vazio/erro/403). E2E `provas-listagem.spec.ts` (proteção offline + live opt-in).

**Pendências / em aberto:**
- [x] **Operação (feito nesta sessão):** migrations `0010`→`0011` aplicadas no Supabase real (`alembic_version=0011`, sem drift). O dono reportou a listagem em 500 → diagnóstico via MCP (prod estava em `0009`, sem `finalizada_em`/função); `0010` desbloqueou; os **advisors** flagraram a função SECURITY DEFINER em `public` como chamável por RPC (DEFAULT PRIVILEGES do Supabase) → **`0011`** move `nomes_de_vendedores` para o schema **`private`** (não exposto), revoga `anon`, concede só a `authenticated`. **Advisors limpos**, listagem funcional (admin vê as 2 provas; nome resolve via `private.nomes_de_vendedores`).
- [ ] O filtro **"Finalizada em"** só retorna resultados após o **C11** popular `finalizada_em` (por design).
- [ ] **C08** consome a rota `/provas/[id]` (hoje placeholder) e pode reusar `ProvaListagem`/rótulos/`status-labels`.
- [ ] (Opcional) Se o C08+ precisar do `usuario` no cliente, considerar um contexto no app shell para evitar o 2º `GET /usuarios/me` da página de provas.

**Próximo passo:**
- **W2-C08 · Visualização de Prova (Detalhe)** — comando: cole `PROMPTS/W2-C08-...md` no Claude Code com os arquivos de contexto + a imagem do design da tela de detalhe.

**Definition of Done:** ✅ atendida — testes (escopo por perfil, sem N+1, migration `0010` versionada/up-down, render/estados, `prefers-reduced-motion`), error boundary do grupo `(app)`, docs (`docs/provas-listagem.md`), sem segredos versionados, R$ 0.

---

## Sessão 09 — 2026-06-12 — [Wave 2 / Componente C06] Cadastro de Prova + Rota + Etiqueta

**Objetivo:** Abrir a Wave 2 com a porta de entrada do domínio: criação de provas com seleção manual de rota (imutável), código `PRV-AAAA-MM-NNNNNN`, QR, etiqueta PDF 95×55 e a RLS de `provas` que fecha a pendência do C05.

**Decisões do dono (Pontos de Decisão, 1 rodada):** DP-1 = **(A)** reconciliar a etiqueta (código em fonte grande abaixo do QR + rota como 5ª linha do bloco); DP-2 = 95×55 landscape confirmado, logos 3STUDIO + Studio&ART **fixas** (SVGs fornecidos em `apps/web/public/`); DP-3/4/5/6/7 = recomendações aceitas (código canônico + QR puro; enum completo 14 estados; sem PATCH + trigger; RLS com admin vendo todas; segno+fpdf2 sob demanda + toast/download/navegação). Rápidas: requerimento texto-de-dígitos; cliente texto livre; ano da etiqueta dinâmico.

**Feito:**
- Migrations **`0007_provas`** (enums, tabela, índices RNF-019, trigger de imutabilidade, RLS restritiva provisória) e **`0008_rls_provas_e_runtime_role`** (grants mínimos SELECT/INSERT, 6 policies por perfil, role `rastreio_runtime` NOBYPASSRLS) + espelhos 1:1 em `migrations/rls/` — ciclo `upgrade→downgrade→upgrade` limpo no PG 5433.
- Backend hexagonal: `domain/provas.py` (código/charset/regex p/ C10, magic bytes, vendedor ativo), portas `ProvasRepositoryPort`/`EtiquetaPort`, `ProvasService` (criação atômica: upload R2 → INSERT com retry de colisão → commit; compensação logada), adapter `FpdfEtiquetaGenerator` (vetorial, determinístico, template parametrizável), repositório SQLAlchemy, endpoints `POST /provas` + `GET /provas/{id}/etiqueta.pdf` (admin-only, 1 sessão RLS/request), `StorageError`→503.
- Frontend: `/provas/nova` real (cartão branco, segmented control de rota sem pré-seleção, dropzone, vendedores em 1 consulta, pós-criação com download automático + retry); `apiFetch` multipart + `apiFetchBlob`; `lib/api/provas.ts`.
- Dívidas herdadas absorvidas: **role não-owner** (ADR-034 item 3) e **`SqlAlchemyUnitOfWork` → `adapters/outbound/db/`** (W0-A-018).
- Etiqueta validada VISUALMENTE (PDF de amostra renderizado e comparado ao design — código e rota presentes, logos vetoriais ok).

**Decisões (ADRs):** **ADR-035** (modelo/trigger), **ADR-036** (código+QR puro), **ADR-037** (enum completo, fronteira C06↔C11), **ADR-038** (etiqueta segno+fpdf2/DP-1), **ADR-039** (RLS de provas + admin vê todas + role de runtime — fecha ADR-033/034), **ADR-040** (remediação da revisão adversarial).

**Revisão adversarial (multi-agente, pós-merge):** 4 dimensões × verificadores céticos → 15 achados confirmados (1 alto, 3 médios, 11 baixos), corrigidos na mesma sessão (migration **`0009`** + middleware + idempotência + a11y; ver ADR-040):
- **Alto:** etiqueta PDF dava **500 permanente** para travessão/aspas curvas/emoji (nome/cliente são texto livre) — corrigido com `core_fonts_encoding='windows-1252'` + sanitização cp1252; fallback de vendedor `—`→`-`.
- **Médios:** (a) **idempotência real** via `prova_id` (reenvio após timeout converge / 409 divergente); (b) **`BodyLimitMiddleware`** 12 MB pré-auth (anti-DoS); (c) **WITH CHECK de INSERT endurecido** (`0009`: status/código/vendedor) contra acesso direto via Data API.
- **Baixos:** R2 recalibrado p/ upload (read 60s, retries 3); roving tabindex + setas no radiogroup; aria nos erros de Vendedor/Rota; `Dropdown` `disabled`/`invalido`; `transition: color` removido; aviso de truncamento >100 vendedores; drifts de doc (`/api`, nanoid→secrets).

**Testes / cobertura (pós-remediação):**
- api: **349 verdes** (era 255 no início da wave; `REQUIRE_DB_TESTS=1`, PG 17 local 5433), cobertura **94.84%** (domínio e serviço de provas: **100%**); `ruff`/`ruff format --check`/`mypy --strict` limpos; ciclo Alembic limpo (head **0009**).
- RLS de provas validada célula a célula @db (vendedor só as suas; motorista só os 3 "Em Trânsito" via fixtures de status; studio/clicheria/admin todas; fantasma → **0**; INSERT só admin com invariantes; UPDATE sem grant; trigger rejeita rota até para owner) + **equivalência anti-drift** domínio↔sql↔migration.
- web: **94 verdes** (era 85; 17 arquivos); `eslint`/`prettier --check`/`next build` limpos; Playwright **9 verdes** (+ specs live gateados).

**Refinos pós-merge + deploy de infra (mesma sessão):**
- **UI (feedback do dono ao vivo):** tela `/provas/nova` sem scroll no desktop (cartão preenche o shell; folga inferior = lateral) + tipografia reduzida; folga da pílula no segmented de Rota; **etiqueta** com contornos afinados (~2px) e "Aponte a câmera para o QR CODE" centralizado sobre o QR. Commits `a21ac41`, `edc0cd4`, `09d6891`.
- **Infra via MCP:** migrations `0007`→`0008`→`0009` aplicadas no **Supabase real** (`rastreio-provas-digitais`/`wmpxxrzbzqgsorjwczvz`) — `alembic_version=0009`, sem drift (SQL de `alembic upgrade --sql` com os `UPDATE alembic_version`); estado verificado (provas/enums/trigger/6 policies/role runtime) + advisors de segurança sem achado sobre `provas`. Bucket **R2 `rastreio-provas-artes`** já existia (nada a criar).

**Pendências / em aberto:**
- [x] **Infra aplicada (sessão 09):** Supabase em `0009`; bucket R2 confirmado.
- [ ] **Dono (só segredos/dashboard):** 4 vars `R2_*` no ambiente da api (`R2_BUCKET=rastreio-provas-artes` + endpoint/keys via API token do Cloudflare); **(opcional)** ativar o role de runtime (`ALTER ROLE rastreio_runtime LOGIN PASSWORD ...` + `DATABASE_URL`); habilitar leaked-password protection (Auth — W1-A-011).
- [ ] Itens herdados que permanecem: `KEEPALIVE_DATABASE_URL` (W0-A-001), TTL do access token (DP-3 do C03), W1-A-006 (outbox), sink real de erros (C19/C20).
- [ ] C07 estende `ProvasRepositoryPort` com listagem paginada/filtros; C08 serve a arte (decidir bytes-via-backend vs presigned URL — a porta de storage não tem presigned hoje).

**Próximo passo:**
- **W2-C07 — Listagem, Pesquisa e Filtros de Provas** (a página `/provas` hoje é placeholder e recebe a navegação pós-criação).

**Definition of Done:** ✅ atendida (testes ≥80%/máquina de estados n/a nesta wave; migrations versionadas/documentadas; critérios US-001 e Matriz §7 validados com teste de acesso não autorizado por perfil; RLS versionada; sem N+1; idempotência/atomicidade verificadas; error boundary do grupo cobre a rota; animações com reduced-motion; sem segredos versionados; protocolo §10 executado).

---

## Sessão 08 — 2026-06-12 — [Wave 1 / Remediação] Auditoria da Wave 1 → GO

**Objetivo:** Resolver os achados de `docs/audits/AUDITORIA-WAVE-1.md` (escopo `PROMPTS/W1-REMEDIACAO-wave1.md`) — Críticos/Altos primeiro — re-verificar a Wave 1 inteira e atualizar o veredito para **GO** antes da Wave 2.

**Decisões do dono (1 rodada):** W1-A-001 = endurecer in-repo agora (fail-closed) + adiar o role não-owner ao C06; W1-A-006 = aceitar como dívida rastreada; escopo = remediação in-repo completa (+ seam de captura); ações de dashboard (leaked-password + política de senha; aplicar migrations) com o dono — **hook já habilitado** por ele.

**Feito (19 achados Resolvidos · 0 falso-positivo · grounding multi-agente antes de cada fix):**
- **W1-A-001 (Alto):** `abrir_sessao_rls` + `create_request_session_factory` (`_RlsSyncSession` + guarda `after_begin`) → sessão de request **fail-closed** (sem claims → levanta, não lê como owner). Sistema/seed seguem owner de propósito. Role não-owner → C06. (ADR-034)
- **W1-A-002 (Alto):** `middleware.test.ts` cobre o enforcement do proxy (não-admin→redirect+flash; admin→next; não-auth→sem getClaims).
- **W1-A-003/005 (Méd):** 4 redirects → `HOME_PADRAO` (`/dashboard`); teste pós-login reescrito; E2E alinhado.
- **W1-A-004 (Méd):** `SET search_path = ''` nas 5 funções (hook+helpers) + migration **`0006`** p/ o banco real; `test_migrations` head=0006.
- **W1-A-007/008/009 (Méd):** `ruff format`/`prettier` reaplicados (gates verdes); **correção da narrativa:** o SESSION_LOG do C04/C05 dizia "format verde", mas o gate estava vermelho no HEAD auditado — reaplicado nesta sessão e agora **realmente verde** (api `ruff format --check` 77 ok; web `prettier --check` ok).
- **W1-A-010/013/014/015/016/017/018/019/020/021/036:** issuer do JWT (config-gated); órfão `created_at` ausente converge; `(app)/error.tsx` + seam `reportClientError`; testes do bootstrap (0%→100%) e dos helpers de RLS; drifts de doc (README RLS, 0002, auth/usuarios/app-shell).

**Decisões (ADRs):** **ADR-034** (sessão de request fail-closed; role não-owner adiado ao C06; + issuer/search_path; W1-A-006 = dívida).

**Testes / cobertura (re-verificação §4, saída real):**
- api: **255 verdes** (era 229), cobertura **95.12%** (piso 80); `ruff`/`ruff format --check`/`mypy --strict` limpos; ciclo Alembic upgrade→downgrade→upgrade limpo (head 0006).
- web: **85 verdes** (era 76, 16 arquivos); `eslint`/`prettier --check`/`next build` limpos.
- RLS positivo+negativo (fail-closed) + helpers default-deny; equivalência da Matriz intacta.

**Pendências / em aberto:**
- [ ] **Dono (dashboard):** habilitar **leaked-password protection** + **política de senha** (min 8, letras+dígitos) — W1-A-011/DP-3; e rodar `alembic upgrade head` no Supabase real (aplica `0006`).
- [ ] **Dívida rastreada:** W1-A-006 (reordenar recheck RN-010 / outbox); **role não-owner `NOBYPASSRLS`** da RLS → **C06** (junto dos GRANTs de `provas`); W1-A-017 sink real de erros → C19/C20.
- [ ] Itens herdados: `KEEPALIVE_DATABASE_URL` (W0-A-001), TTL do access token (DP-3 do C03), mover `SqlAlchemyUnitOfWork` p/ `adapters/outbound/db/` no C06 (W0-A-018).

**Próximo passo:**
- **W2-C06 · Cadastro de Prova com Seleção de Rota + Etiqueta** — abre a Wave 2 e aplica a RLS de `provas` sobre a fundação fail-closed deste sessão. *(O prompt de remediação citou "W2-C07", mas o roadmap do Backlog/CLAUDE.md §7 e o SESSION_LOG têm o **C06** como primeiro da Wave 2 — divergência registrada, CLAUDE.md §2.1.)*

**Definition of Done:** ✅ Veredito **GO** — re-verificação inteira verde; cada achado Resolvido tem teste/commit; dívida remanescente rastreada e não-bloqueante; protocolo de encerramento executado.

---

## Sessão 07 — 2026-06-12 — [Wave 1 / W1-C05] Controle de Acesso por Perfil (Matriz RBAC em duas camadas)

**Objetivo:** Formalizar o RBAC por perfil em **duas camadas independentes** (proxy do App Router + RLS do PostgreSQL), com a Matriz §7 como fonte única, fechando a **Wave 1**.

**Feito:**
- **Hook de claims** (migration `0004`): `public.custom_access_token_hook` eleva `setor`/`user_id`/`administrador` do `app_metadata` ao topo do JWT (posição lida pela RLS), `SECURITY INVOKER`, grants restritos ao `supabase_auth_admin`.
- **RLS definitiva de `usuarios`** (migration `0005` + espelhos em `migrations/rls/`): grants a `authenticated` + policies `self`/`admin` (opção 6-A), **helpers** `app_current_claims/app_setor/app_is_admin/app_current_user_id` (reuso no C06), `_roles.sql` (stand-ins locais). Removido `usuarios_baseline_restritiva.sql`.
- **Propagação de claims (ADR-008)**: `propagar_claims_rls` (listener `after_begin` + `SET LOCAL ROLE authenticated`) ligado em `get_usuarios_service`; guard generalizado em `requer_acesso(Recurso)` + `domain/rbac.py`.
- **Camada superior (web)**: `lib/access-matrix.ts` (+ `access-matrix.cells.json`), enforcement no `proxy.ts` (claims via `getClaims()`, redirect + flash), `RbacFlash` (toast), **sidebar filtrada** por perfil.
- **Harness de equivalência** travando `access-matrix.ts` (web) e `rbac.py` (api) à Matriz canônica; **`docs/rbac.md`**.

**Decisões (ADRs):**
- ADR-029 (hook lê `app_metadata` do evento — opção B), ADR-030 (duas camadas + equivalência/PR único), ADR-031 (propagação `after_begin` + helpers portáteis — finaliza **ADR-008**), ADR-032 (RLS de `usuarios` 6-A), ADR-033 (fronteira C05↔C06). **DP-1…DP-7 confirmados** pelo dono ("segue com as recomendações"): Matriz ortogonal (Vendedor-Admin vê páginas admin), hook opção B, redirect→`/dashboard`+cookie, RLS 6-A.

**Testes / cobertura:**
- api: **229 verdes, cobertura 90%** (hook por perfil + evento malformado; RLS de `usuarios` sob `SET ROLE authenticated`; propagação ADR-008 + controle negativo; equivalência da Matriz; ciclo upgrade/downgrade das `0004/0005`). `ruff`/`mypy` limpos. **Revisão adversarial de segurança** (5 lentes): 2 achados de baixo risco endurecidos no hook (SECURITY INVOKER explícito + guard de evento malformado).
- web: **76 verdes** (access-matrix por célula, equivalência, sidebar por perfil, `RbacFlash`); `lint`/`build` limpos.
- Cobertura de células: **100% das de PÁGINA** (proxy/`can` ⇔ `autorizar`); **dado de `usuarios`** via RLS (admin todas; não-admin 0 alheias). 

**Pendências / em aberto:**
- [ ] **RLS de linha de `provas` (Vendedor as próprias / Motorista as "Em Trânsito") é do C06** (DP-3) — usando os helpers desta sessão; o harness é estendido lá.
- [ ] **Habilitar o hook no dashboard** do Supabase (Auth → Hooks → `public.custom_access_token_hook`) — passo de projeto (não-código). Aplicar `0004/0005` no projeto real via `alembic upgrade head`.

**Próximo passo:**
- **W2-C06 · Cadastro de Prova com Seleção de Rota + Etiqueta** (abre a Wave 2; aplica a RLS de `provas` sobre os helpers do C05).

**Definition of Done:** ✅ atendida (testes ≥ piso incl. acesso não autorizado por perfil + equivalência; RLS versionada em `/migrations/rls/`; migrations `upgrade`/`downgrade` em ambiente limpo; sem erro de console/log crítico; docs do módulo; sem segredos versionados; idempotência preservada). Itens de animação reusam o sistema do C04.

---

## Sessão 06 — 2026-06-12 — [Wave 1 / W1-C04] Cadastro e Gestão de Usuários + App Shell

**Objetivo:** CRUD de usuários (RF-018, RF-020, US-015) com provisionamento via Supabase Auth Admin API, **primeira tabela/migration de domínio** (`usuarios`) e o **app shell** (sidebar + área de conteúdo) que hospeda toda a plataforma autenticada.

**Feito:**
- **Pré-flight** — limpeza de `__pycache__` órfãos (resíduo de tentativa anterior de C04) e commit do ajuste cosmético pendente do C03 (`login.module.css`).
- **Tokens do design** — o MCP do Figma estourou o limite do plano Starter; extração feita por **amostragem de pixel dos exports PNG 1:1** (Downloads: `Gerenciamento de usuários - admin (3).png` + `- Modal (1).png`; lossless → cores exatas) com 3 sondas Python/Pillow: paleta completa (`#eaeaea` shell r40, `#ff5959` Desativar, `#d7d7d7` controles, `#979797` divisores, scrim `rgba(0,0,0,.76)` medido, modal idêntico aos tokens `--auth-*` do C03), geometria (colunas da tabela com frações medidas, pills 56/29px, pitch 56px) e tipografia. Tokens centralizados em `globals.css` (`--app-*`).
- **Backend** — migration **`0002_usuarios`** (enums `setor_enum`/`localizacao_enum`, PK = UUID de `auth.users` 1:1, CHECK bidirecional RN-009, índices RNF-019, **RLS restritiva** aplicada e versionada em `migrations/rls/usuarios_baseline_restritiva.sql`; ciclo upgrade→downgrade→upgrade validado em PG 16 real porta 5433); domínio puro (`domain/usuarios.py`); portas `IdentityProviderPort`/`UsuariosRepositoryPort`; **`UsuariosService`** com provisionamento coordenado (**compensação** em falha parcial, **adoção de órfãos marcados** via `app_metadata.provisionado_por`, **fail-closed** nas mutações de status, salvaguarda do **último admin ativo**, sync de `app_metadata.{setor,administrador}` p/ o C05); adapter **`SupabaseAdminIdentityProvider`** (httpx, `sb_secret` server-only) + stand-in 503; endpoints `/usuarios` (listagem paginada server-side com busca escapada + filtros, criar, editar com e-mail imutável, desativar/reativar idempotentes, `/me`) com **guard mínimo de admin**; task **`bootstrap_admin`**; `.env.example` com `SUPABASE_SECRET_KEY`.
- **Frontend** — **app shell** no grupo `(app)` (`AppShell` + `Sidebar` com indicador ativo via `layoutId`, busca inerte, rodapé via `GET /usuarios/me` com fallback gracioso; placeholders DP-6; transição de conteúdo por rota); **Gerenciador de usuários** fiel ao design (debounce 300ms, filtros server-side, scroll infinito na área da tabela, mutações em memória); **`MotionModal`** reutilizável (DAT §5.2, focus trap, reduced-motion) + form Novo/Editar (validação em tempo real, localização condicional p/ Vendedor, 409 inline) + confirmação de status; **toasts** (`useToast`); **responsivo** DP-7 (drawer/cards/folha, ≥44px). Rotas `/`, `/login`, `/inicio` → `/usuarios`; `AuthProof`/`ApiStatus` removidos (mortos).
- **Fidelidade visual** — verificada por rota de preview temporária + screenshot Playwright **1920×1080 comparado pixel a pixel** com os exports (cores idênticas; scrim `#343434` vs `#333333`); preview removido antes do commit.
- **Qualidade** — api: ruff + mypy strict verdes, **201 testes** (90% cobertura) incl. compensação com PG real e estrutura da migration; web: eslint + prettier + build verdes, **50 testes** vitest + Playwright 8/8 (5 live gated); **revisão adversarial multi-agente** (5 dimensões × céticos) sobre os dois commits.
- **Docs** — `docs/usuarios.md`, `docs/app-shell.md`; CLAUDE.md §2.1/§5.5-5.6/§6/§9; README (deploy confirmado, setup C04, roadmap); CHANGELOG (duas seções `### Fixed` consolidadas).

**Decisões (ADRs):**
- **ADR-023** — DP-1: modelo **Setor × Administrador ortogonal** (o design governa) + releitura da Matriz §7 p/ o C05; refletida em CLAUDE.md §2.1.
- **ADR-024** — DP-2: `usuarios` 1:1 com `auth.users` (PK = UUID do auth, sem FK física) + schema/índices.
- **ADR-025** — DP-3/DP-4: provisionamento via Admin API (httpx, sem SDK), compensação/adoção de órfãos, `SUPABASE_SECRET_KEY` server-only, desativar = ban + `ativo=false` (US-015), e-mail imutável.
- **ADR-026** — app shell como layout do grupo `(app)` (DP-6/DP-7/DP-9: lucide-react, wordmark do C03, status no 2º dropdown, scroll infinito, "Satus"→"Status").
- **ADR-027** — DP-5: guard mínimo de admin agora + RLS provisória + `app_metadata`; RBAC completo no C05.
- **ADR-028** — DP-8: `MotionModal`/toasts criados já no contrato do C19 (que generaliza sem reescrever).

**Testes / cobertura:**
- api: `uv run pytest` → **201 passed** (REQUIRE_DB_TESTS=1, PG 16 real), cobertura **90%** (fail_under 80); ruff + mypy strict limpos.
- web: `pnpm test` → **50 passed** (10 arquivos); `pnpm test:e2e` → 8 passed + 5 live-gated; lint/build/format verdes.

**Pendências / em aberto:**
- [ ] **Responsável:** cadastrar `SUPABASE_SECRET_KEY` no backend (Railway/.env), configurar a **política de senha** no dashboard (min. 8, letras+dígitos), rodar `alembic upgrade head` no Supabase real e o `bootstrap_admin` do primeiro administrador.
- [ ] Visibilidade dos itens de menu por perfil + enforcement de rota + RLS por perfil + Custom Access Token Hook → **C05**.
- [ ] Busca global da sidebar (inerte até a Wave 2); reset/troca de senha (componente futuro); "página inicial do perfil" (C05).
- [ ] Itens herdados: W0-A-001 (`KEEPALIVE_DATABASE_URL`), TTL do access token (DP-3 do C03), W0-A-018 (mover `SqlAlchemyUnitOfWork` p/ `adapters/outbound/db/` no C06).

**Próximo passo:**
- **W1-C05 · Controle de Acesso por Perfil — Matriz RBAC** (access-matrix.ts + enforcement no proxy + políticas RLS por perfil + Custom Access Token Hook, sobre o `app_metadata` já gravado).

**Definition of Done:** ✅ atendida — testes (incl. provisionamento/RN-009/RN-010/idempotência), migration versionada e documentada, RLS versionada em `migrations/rls/`, sem erros de console/log crítico, docs do módulo, animações validadas com `prefers-reduced-motion`, sem segredos versionados, árvore limpa.

**Pós-entrega (mesma sessão):**
- **Suporte live ao dono:** o 500 em `/usuarios` no ambiente real era a migration `0002` não aplicada no Supabase — `alembic upgrade head` executado lá + primeiro admin provisionado por upsert direto (a `SUPABASE_SECRET_KEY` ainda não está no `.env`; sem ela, criar/editar/desativar respondem 503 — pendência do responsável).
- **Revisão adversarial concluída** (38 agentes; 27 confirmados/6 refutados) → correções em dois commits `fix(w1-c04)`: concorrência no backend (adoção de órfão com idade mínima, lock otimista + 409, RN-010 com advisory lock transacional, idle-in-transaction, bootstrap reordenado, migration **`0003`** trancando `alembic_version` no PostgREST — aplicada no Supabase real, `/docs` off em produção, JWKS timeout) e robustez no frontend (loop infinito do scroll, corrida de paginação, timeout combinado, modais durante submit, drawer back/forward, signOut, motion/ARIA/touch). api: **207 testes**, 90%; web: **50 testes**.
- **Fidelidade (feedback do dono):** sidebar/conteúdo escalados ao quadro de 1080px do Figma via unidade `--u` — pixel a pixel em 1080 (±2px), proporcional em janelas menores.
- Refutados pela verificação cética (sem ação): cap da busca por e-mail, acesso do desativado até o TTL (mitigado pelo ban+revogação), `layoutId` duplicado desktop/drawer, falta de `error.tsx` no grupo, ILIKE sem índice dedicado (escala ~30 usuários).

---

## Sessão 05 — 2026-06-11 — [Wave 1 / W1-C03] Tela de Login e Sessão

**Objetivo:** Autenticação por e-mail/senha (Supabase Auth), sessão stateless em cookie + refresh, encerramento por inatividade de 30 min, verificação de JWT no backend e as **três telas do design** — primeiro componente da Wave 1.

**Feito:**
- **Backend** — `JwtVerifier` (`adapters/inbound/http/auth.py`): **ES256 via JWKS** cacheado (`PyJWKClient`) + **HS256 fallback**, valida `aud="authenticated"`/`exp`, rejeita `alg=none` e confusão de algoritmo; **`GET /auth/me`** (prova). `Settings` ganhou `SUPABASE_JWKS_URL`/`effective_jwks_url`; dependência `pyjwt[crypto]`. 18 testes offline; ruff + mypy + pytest verdes (cobertura **98%**, 104 passed/7 skipped).
- **Frontend** — clients **`@supabase/ssr`** (browser/servidor) + `updateSession` + **`src/proxy.ts`** (só refresh; `getUser()`); **três telas** em CSS Modules fiéis ao Figma (`/login` adaptativa desktop-split/mobile, `/bem-vindo`, `/inicio` placeholder com `AuthProof → /auth/me` + Sair); **erro de login genérico**; **inatividade 30 min** (`InactivityGuard`); fundação de **motion** (tokens DAT §5.1 + `useReducedMotion`) com **Framer Motion** (transform/opacity, reduced-motion-aware). **Inter** self-hospedada; herói **17,8 MB → 540 KB**. **vitest 11/11** + **Playwright 4/4** (+1 *live* gated); `pnpm lint`/`build` verdes; fidelidade conferida por screenshots.
- **Docs** — `docs/auth.md`; `.env.example` (api/web) atualizados.
- **Refino (pós-feedback do dono):** (1) fluxo mobile corrigido — **boas-vindas primeiro**, login revelado ao clicar em "Entrar", em **rota única `/login`** (`<AuthFlow>`, troca de passo, sem redirect por viewport); `/` e `/bem-vindo` redirecionam para `/login`; `export const viewport` adicionado. (2) Herói do desktop com o **formato custom EXATO do Figma** (máscara SVG). (3) Animações (fade do contorno no foco dos campos, hover/press dos botões, transição boas-vindas→form; **imagem-herói estática** — parallax/zoom removidos a pedido do dono). (4) **Harmonização do motion:** contorno do input com **fade-in/out** no foco (overlay de opacity) e **mola única `SPRING`** (`tokens.ts`) para todas as interações + stagger/easing consistentes (emenda ADR-020). `Welcome`/`bem-vindo.module.css` removidos. vitest 11/11 + Playwright 5/5 verdes; screenshots reconferidos. **ADR-022.**

**Decisões (ADRs):**
- **ADR-018** (auth/sessão), **ADR-019** (verificação JWT ES256/JWKS+HS256 — corrige a premissa HS256), **ADR-020** (fundação de motion C03↔C19), **ADR-021** (`proxy.ts` no Next 16), **ADR-022** (fluxo adaptativo em rota única + herói custom + animações, refino); **emendas** ADR-014 (Inter local) e ADR-009 (Vercel + Railway confirmados).
- **Pontos de decisão (respostas do dono):** DP-1 ✓ · DP-2 = ES256/JWKS+HS256 + publishable moderna · DP-3 ✓ · DP-4 = `/inicio` · DP-5 = link inerte · DP-6 = instalar Framer Motion · DP-7 ✓ (breakpoint 768px) · DP-8 = tokens via link do Figma.

**Testes / cobertura:**
- Backend: **104 passed / 7 skipped (@db)**, cobertura **98%**. Web: **vitest 11/11**, **Playwright 4/4** (+1 *live* gated). ruff/mypy/eslint/`next build` verdes.

**Pendências / em aberto:**
- [ ] **Reset de senha** (fora do escopo do C03 — DP-5; link inerte por ora).
- [ ] **Caminho feliz E2E autenticado**: atrás de `E2E_LIVE` (requer usuário semeado + API rodando; a checagem `getUser` do servidor não é route-mockável). Sucesso já coberto pelo teste de componente.
- [ ] **Responsável:** ajustar o **TTL do access token** no dashboard (DP-3); cadastrar `KEEPALIVE_DATABASE_URL` (W0-A-001, herdada).
- [ ] Node Figma `70:171` (login mobile) reproduzido por tokens compartilhados + PNG anexado (rate limit do Figma Starter) — revalidar se necessário.

**Próximo passo:**
- **W1-C04 · Cadastro e Gestão de Usuários.**

**Definition of Done:** ✅ (subconjunto aplicável ao C03): testes verdes; sem erro de console/log crítico; docs do módulo (`docs/auth.md`); error handling (401 genérico, error boundaries herdados); animações validadas com `prefers-reduced-motion`; sem segredos versionados. RLS/migrations **não se aplicam** ao C03 (tabelas de auth são do Supabase).

---

## Sessão 04 — 2026-06-11 — [Wave 0 / W0-REMEDIATION] Remediação da Wave 0

**Objetivo:** Corrigir os achados da auditoria (`docs/audits/wave-0-audit.md`) por severidade/dependência, com teste por correção e **gate de re-verificação**, sem regressão nem escopo novo (escopo de `PROMPTS/W0-REMEDIATION-remediacao.md`).

**Feito:**
- **29/29 achados endereçados** (0 Blocker · 0 High · 2 Medium · 16 Low · 11 Nit): **26 Resolvidos**, **1 Resolvido documental** (W0-A-018 → ADR-017, código na Wave 2), **1 Ação do responsável** (W0-A-001), **1 Parcial + dívida** (W0-A-029).
- **Medium:** W0-A-002 — CI dispara em push para `develop` (decisão do responsável); W0-A-001 — o responsável **cadastrará o secret** `KEEPALIVE_DATABASE_URL` (workflow mantido fail-loud, correto após o secret existir).
- **Robustez/observabilidade:** log da causa no readiness/`ping`/storage (003), R2 com timeouts (004), keep-alive sem vazar credencial na carga de config (005), `LOG_LEVEL` validado no boot (013), hermeticidade total da suíte vs. env de shell (012), downgrade defensivo da baseline (014).
- **Segurança HTTP:** guarda CORS curinga (015), security headers nosniff/no-store (016), whitelist de `X-Request-ID` (023), SHA-pinning de actions + Dependabot (008).
- **Frontend:** validação de shape + `error.tsx` (017). **Workflows:** permissions/concurrency/format:check/--no-dev (009/010/011/024). **Docs/ADRs:** emenda ADR-013 (007), ADR-017 (018), keep-alive §6 (006), `.env.example` (020/021), CLAUDE §5.1 (019), README (028); nits (022/025/026/027/029).
- Suíte **70 → 88 testes**, cobertura **100%** mantida. Log completo em `docs/audits/wave-0-remediation.md`.

**Decisões (ADRs):**
- **ADR-017** (novo): lar das implementações de porta de DB = `adapters/outbound/db/` (UoW move na Wave 2). **ADR-013 emendada** (catch-all = `ErrorHandlingMiddleware` interno ao CORS). **ADR-016** checklist: parte CI resolvida (`develop` nos gatilhos de push); secret = ação do responsável.

**Testes / cobertura:**
- **Gate de re-verificação (§5) VERDE:** ruff + ruff format + mypy strict; ciclo Alembic `upgrade→downgrade→upgrade` (PostgreSQL 16.9 real, porta 5433); **88 passed, cobertura 100%** (`REQUIRE_DB_TESTS=1`); keep-alive `exit 0`; domínio limpo; varredura de segredos limpa; `pnpm install/lint/format:check/build` verdes; lockfiles versionados.

**Pendências / em aberto:**
- [ ] **W0-A-001 (responsável):** cadastrar `KEEPALIVE_DATABASE_URL` no GitHub (Settings → Secrets and variables → Actions) e validar via `workflow_dispatch`. Até lá o cron diário falha e o Supabase fica desprotegido.
- [ ] **Dívida W0-A-029:** pinar as imagens base do `Dockerfile` por digest ao definir a plataforma de deploy (ADR-009).
- [ ] **W0-A-018:** mover `SqlAlchemyUnitOfWork` para `adapters/outbound/db/` na Wave 2 (C06).
- [ ] (Herdada) `apps/web/public/` untracked (assets do W1-C03); confirmar plataformas de deploy (ADR-009).

**Próximo passo:**
- **Wave 1 · W1-C03 · Tela de Login e Sessão** na branch `develop`.

**Definition of Done:** ✅ Gate verde; correções testadas e aderentes ao `CLAUDE.md`; sem regressão; sem segredos versionados; protocolo de encerramento executado.

---

## Sessão 03 — 2026-06-11 — [Wave 0 / W0-AUDIT] Auditoria read-only da Wave 0

**Objetivo:** Auditoria independente e somente-leitura dos componentes W0-C01 e W0-C02 (escopo de `PROMPTS/W0-AUDIT-auditoria.md`) — inspecionar, verificar e relatar, **sem corrigir nada**.

**Feito:**
- Verificações executáveis contra **PostgreSQL 17.10 real** (binários portáteis, porta 5433; env sobrescrita — Supabase real intocado): ruff + ruff format ✅ · mypy strict ✅ · pytest offline (70 passed/6 skip, 98,81%) ✅ · pytest com `REQUIRE_DB_TESTS=1` (**76 passed, cobertura 100%**) ✅ · ciclo Alembic `upgrade→downgrade→upgrade` em banco limpo ✅ · keep-alive sucesso (`exit 0`) e falha controlada (`exit 1`, sem vazar credencial) ✅ · smoke test da API (`/health` 200, `/health/ready` 503 `degraded` sem R2, `/docs` 200, `X-Request-ID` propagado) ✅ · pnpm lint/build ✅ · varredura de segredos limpa ✅.
- Auditoria multi-agente: 12 auditores por dimensão (§4.1–4.12 + 2 varreduras extras) × verificação adversarial cética de cada achado (48 agentes). 36 achados brutos → **29 únicos** após deduplicação.
- **Relatório entregue:** `docs/audits/wave-0-audit.md` (matriz de conformidade C01 §5/C02 §5/DoD, 29 achados com ID estável `W0-A-001`…`W0-A-029`, lista priorizada de remediação, apêndice de evidências).

**Veredito:** **Wave 0 apta a servir de base à Wave 1 — continuidade NÃO bloqueada.** Contagem: **0 Blocker · 0 High · 2 Medium · 16 Low · 11 Nit**. Os 2 Medium são handoffs operacionais já registrados no ADR-016 e ainda não executados: **W0-A-001** (cron do keep-alive armado na branch padrão **sem** o secret `KEEPALIVE_DATABASE_URL` → falha diária + Supabase real desprotegido, pausa possível ~2026-06-18) e **W0-A-002** (CI não dispara em push para `develop` — o HEAD da branch de integração nunca rodou no CI do GitHub).

**Pendências / em aberto:**
- [ ] Executar a **sessão de remediação da Wave 0** consumindo `docs/audits/wave-0-audit.md` (ordem sugerida no §5 do relatório; começar por W0-A-001/W0-A-002).

**Próximo passo:**
- **Sessão de remediação da Wave 0** consumindo `docs/audits/wave-0-audit.md`. (A Wave 1 / W1-C03 segue na fila após a remediação dos itens Medium.)

**Definition of Done:** N/A (sessão de auditoria — protocolo leve do prompt W0-AUDIT §8: relatório salvo + esta entrada; `CHANGELOG.md`/`DECISIONS.md`/código intocados por regra).

---

## Sessão 02 — 2026-06-11 — [Wave 0 / Componente C02] Cron Job de Keep-Alive

**Objetivo:** Entregar o keep-alive que impede a pausa do Supabase no free tier (>7 dias sem requisições): rotina read-only de *ping*, workflow agendado, alerta de falha e docs — reutilizando a infra do C01 (escopo de `PROMPTS/W0-C02-keep-alive.md`).

**Feito:**
- **Consolidação DRY:** extraída `fetch_db_time()` em `src/infrastructure/database.py` (núcleo único do *ping*, `SELECT now()`); `ping()` do readiness passou a envelopá-la (contrato `-> bool` intacto); novo `create_direct_engine()` para a conexão *one-shot* na direta/sessão (5432).
- **Rotina** `src/tasks/keep_alive.py` (`uv run python -m src.tasks.keep_alive`): conexão curta via `MIGRATIONS_DATABASE_URL`, log JSON estruturado (`event`/`status`/`latency_ms`/`db_time`/`correlation_id`/`env`), exit 0/≠0, erro sem vazar credencial (só `error_type`).
- **Workflow** `.github/workflows/keep-alive.yml`: `schedule 0 9 * * *` (06:00 BRT) + `workflow_dispatch`, `concurrency`, `timeout-minutes: 5`, `permissions: contents: read`, secret `KEEPALIVE_DATABASE_URL`, alerta opcional `if: failure()` + `ALERT_WEBHOOK_URL` (pulado sem o secret).
- **Testes:** offline (`tests/unit/test_keep_alive.py` — campos do log, exit codes, prova de não-vazamento de senha) e `@db` (`tests/integration/test_keep_alive.py` — sucesso real). Fix de hermeticidade do `test_main.py` (`chdir(tmp_path)`) e *fixture* autouse `_isola_logging_global` em `conftest.py`.
- **Docs:** `docs/keep-alive.md` (racional, cadência, ligar em produção, teste manual, alternativa Cloudflare Worker Cron) + link em `docs/setup-infra.md`.
- **Validação em execução real:** *ping* read-only ao **Supabase real** → `exit 0`, `status="ok"`, `db_time` real, `latency_ms≈331ms`; falha com credencial inválida → `exit 1`, `status="error"`, sem vazar a senha.
- Revisão adversarial multi-agente (6 dimensões × verificação cética) sobre o change set.
- **Publicado no GitHub:** repositório [`3studioagn/Sistema-Digital`](https://github.com/3studioagn/Sistema-Digital) criado; remote `origin` configurado; branches `main` (estável) e `develop` (integração, **padrão**) enviadas em `abc293c` via Git Credential Manager (ambiente sem `gh`).

**Decisões (ADRs):**
- **ADR-015** (keep-alive externo; scheduler primário GitHub Actions; conexão direta para o *one-shot*; cadência diária; alerta nativo + webhook opcional; alternativa Cloudflare documentada). **Nota:** o prompt referenciava "ADR-012", mas 012–014 já existiam (W0-C01) → adotado o próximo livre, **015** (divergência registrada, `CLAUDE.md §2.1`).

**Testes / cobertura:**
- **70 passaram, 6 skip** (`@db`, sem Postgres local) offline; cobertura **98.81%** (linhas restantes são caminhos de sucesso `@db`, cobertos no CI). `ruff`, `ruff format` e `mypy --strict` verdes. Sem segredos versionados.

**Pendências / em aberto:**
- [x] Push para o remoto — **feito**: `3studioagn/Sistema-Digital` (branches `main` + `develop`). Resolve também a pendência herdada do C01.
- [ ] **Ligar keep-alive em produção:** cadastrar o secret `KEEPALIVE_DATABASE_URL` (e opcional `ALERT_WEBHOOK_URL`) em **Settings → Secrets and variables → Actions** — o cron diário (06:00) **falha** sem ele; validar via `workflow_dispatch`.
- [ ] **CI em `develop`:** `ci.yml` só dispara em `main` + PRs; pushes diretos em `develop` não acionam a CI. Decidir adicionar `develop` aos gatilhos de push **ou** adotar fluxo por PR (ADR-016).
- [ ] **`apps/web/public/`** (`login-bg.png` 18 MB + `logo-3studio.svg`) untracked — decidir **Git LFS** vs commit normal; pertence ao W1-C03.
- [ ] (Opcional) Branch padrão no GitHub = `develop`; trocar para `main` em Settings → Branches se preferir.
- [ ] (Herdada) Confirmar plataformas de deploy (ADR-009).

**Próximo passo:**
- **Wave 1 · W1-C03 · Tela de Login e Sessão** (primeiro componente da Wave 1; Wave 0 concluída). Trabalhar na branch `develop`.

**Definition of Done:** ✅ atendida no subconjunto aplicável (testes ≥ piso, observabilidade/log estruturado, error handling com exit code + alerta, docs do módulo, sem segredos versionados, idempotência N/A — operação read-only sem escrita).

---

## Sessão 01 — 2026-06-10 — [Wave 0 / Componente C01] Configuração de Infraestrutura

**Objetivo:** Fundação completa do monorepo: backend FastAPI hexagonal, Alembic, storage R2, observabilidade, frontend Next.js, CI e docs de provisionamento (escopo do prompt `PROMPTS/W0-C01-infraestrutura.md`).

**Feito:**
- Monorepo inicializado (git, `.gitignore`, `.editorconfig`, `.gitattributes`, `docker-compose.yml` com Postgres 17 + banco de teste isolado).
- `apps/api`: arquitetura Ports & Adapters completa (config → logging → database → porta de storage → adapter R2 → middleware/erros → health → app factory → composition root). Alembic async + baseline `0001` (pgcrypto) + `migrations/rls/README.md`. Dockerfile multi-stage non-root. `.env.example` integral.
- `apps/web`: Next 16.2.9 (App Router, TS strict, CSS Modules), página de status com consulta única ao readiness, client Supabase mínimo lazy, ESLint+Prettier, build hermético.
- CI GitHub Actions (api: ruff/mypy/alembic↑↓/pytest com Postgres service; web: lint/build) + deploy documentado parametrizável.
- `docs/setup-infra.md` (provisionamento Supabase/R2 + checklist de aceitação).
- Validação contra **PostgreSQL 17.10 real** (binários portáteis, porta 5433): 66 testes verdes com `REQUIRE_DB_TESTS=1`, ciclo `alembic upgrade head → downgrade base → upgrade head` via CLI em banco limpo, API de pé com `/health` 200, `/health/ready` 503 `degraded` (storage down sem R2 — degradação esperada) e `/docs` servindo OpenAPI.
- Revisão adversarial multi-agente (6 dimensões × verificação cética) sobre os critérios de aceitação, regra hexagonal, segredos, escopo, CI e ADR-007.

**Decisões (ADRs):**
- ADR-007 → **Aceita** (validada em execução); ADR-010 → **Aceita** (uv/pnpm confirmados); ADR-003 anotada com as versões pinadas.
- **ADR-012** (porta de storage síncrona + threadpool), **ADR-013** (catch-all no middleware de request-id, envelope canônico de erro), **ADR-014** (Next 16 pinado, build hermético) — novas.

**Testes / cobertura:**
- 66 testes (unit + integração), **100% de cobertura** da camada (piso configurado: 80%). `ruff` e `mypy --strict` verdes. `pnpm lint`/`pnpm build` verdes. Sem warnings na suíte.
- Testes `@db` fazem skip sem Postgres local e FALHAM no CI se o banco sumir (`REQUIRE_DB_TESTS=1`).

**Pendências / em aberto:**
- [x] Provisionar Supabase + R2 — **já existiam** (verificado via MCP em 2026-06-10): projeto `rastreio-provas-digitais` (ref `wmpxxrzbzqgsorjwczvz`, sa-east-1, PG 17, `pgcrypto` instalado) e bucket R2 `rastreio-provas-digitais`. `.env` locais preenchidos com URL e chave publishable.
- [x] Senha do banco preenchida e validada (2026-06-10). Descoberta: conexão direta é IPv6-only → `MIGRATIONS_DATABASE_URL` ajustada para o **session pooler** (aws-1:5432, emenda na ADR-007). `alembic upgrade head` aplicado no Supabase real (`0001 (head)`); **readiness 200 com `database: ok` + `storage: ok`** — infraestrutura real completa.
- [x] API Token do R2 criado e validado (2026-06-10): `storage: ok` no readiness e roundtrip real upload→download→delete via `StoragePort` (roteiro `docs/setup-infra.md` §5) executado com sucesso contra o bucket `rastreio-provas-digitais`.
- [ ] Confirmar plataformas de deploy com o responsável (ADR-009) e ligar os jobs comentados no `ci.yml`.
- [ ] Push para o remoto `rastreio-provas-digitais` quando o repositório for criado no GitHub.

**Próximo passo:**
- **W0-C02 · Cron Job de Keep-Alive** (depende do C01, agora concluído).

**Definition of Done:** ✅ atendida no subconjunto aplicável à infraestrutura (testes ≥ piso, migrations versionadas e aplicáveis, sem erros de console/log crítico, docs por módulo, RLS = política versionada [implementação na W1], observabilidade e error handling validados; itens de UI/animação/N+1 não se aplicam a este componente).

---

## Sessão 00 — 2026-06-09 — Bootstrap do projeto (Engenharia de Prompts)

**Objetivo:** Analisar os documentos de especificação, estabelecer a fundação de contexto e preparar a execução da Wave 0.

**Feito:**
- Análise integral de: Requisitos v1.0, Backlog v1.0, DAT v3.0 e UML v3.0.
- Criação dos documentos de contexto na raiz: `CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`.
- Definição da hierarquia de fontes da verdade e mapeamento das divergências entre as versões dos documentos (`CLAUDE.md §2.1`).
- Consolidação do glossário de domínio canônico (14 estados, 4 rotas, enums) em `CLAUDE.md §6`.
- Baseline de ADRs (001–011) em `DECISIONS.md`.
- Preparação do prompt de execução do **W0-C01 — Configuração de Infraestrutura**.

**Decisões (ADRs):**
- ADR-001 a ADR-006 — Aceitas (monorepo, hexagonal, stack, rota manual/imutável, máquina de estados em código, RBAC em profundidade).
- ADR-007 a ADR-010 — Propostas (conexão Supabase, RLS por request, deploy, gerenciadores de pacote) — a confirmar nas waves indicadas.
- ADR-011 — Aceita (tratamento dos documentos desatualizados; UML a regenerar; DAT §6 ignorado).

**Pendências / em aberto:**
- [ ] Confirmar plataformas de deploy (ADR-009) com o responsável.
- [ ] Validar estratégia de conexão Supabase (pooler de transação + NullPool) em execução (ADR-007, na W0-C01).
- [ ] Regenerar UML alinhado à v1.0 — após a Wave 2.

**Próximo passo:**
- Executar **W0-C01 — Configuração de Infraestrutura** (prompt em `prompts/wave-0/W0-C01-infraestrutura.md`).

**Definition of Done:** N/A (sessão de preparação; nenhum componente de código fechado ainda).
