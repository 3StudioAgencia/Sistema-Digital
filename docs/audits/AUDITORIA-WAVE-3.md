# Auditoria — Wave 3 · Movimentação (C10–C15)

> Sessão de **auditoria adversarial read-only**. Nada do código de produção foi alterado. Toda evidência abaixo é **reproduzível** (comando + saída, teste + resultado, ou query + linhas). Princípio dominante: **executar, não confiar**.
>
> - **Data:** 2026-06-17
> - **Escopo:** C10 Escaneamento · C11 Máquina de Estados · C12 Assinatura · C13 Timeline · C14 Cancelamento · C15 Reinício de Ciclo
> - **Fonte da verdade do comportamento:** Requisitos v1.0 §6 (Matriz de Transições) e §7 (Matriz de Acesso), RF/RN/RNF citados.
> - **Ambiente:** Postgres 17.10 local (`rastreio_test`, `alembic_version=0018` = head), Python 3.12/uv, Next 16.

---

## 1. Sumário executivo

### ✅ VEREDITO: **GO**

**Zero achados Críticos e zero achados Altos.** O **estado de uma prova é íntegro, consistente e inviolável** sob o comportamento especificado: a §6 está implementada fielmente, há **um único caminho de mudança de status** (o motor do C11), as transições são **atômicas, idempotentes e serializadas sob lock**, os estados terminais não têm saída, a RLS isola escopos no caminho de request, e as ações administrativas têm **defesa em duas camadas**. As duas perguntas que guiam a auditoria respondem **NÃO** com evidência:

- *"O estado de uma prova pode ser corrompido ou contornar o motor?"* → **Não** (Áreas A, B, C, E — PASSA empiricamente).
- *"Um usuário pode ver ou mover o que não deveria?"* → **Não demonstrado** (Áreas D, F, G — isolamento de escopo provado no caminho de request; ações admin barradas em duas camadas).

### Contagem de achados

| Severidade | Qtd | Bloqueia GO? |
| --- | --- | --- |
| 🔴 Crítico | **0** | — |
| 🟠 Alto | **0** | — |
| 🟡 Médio | **3** | Não — registrados como dívida |
| ⚪ Baixo | **5** | Não |

> **Nota de honestidade metodológica:** um dos cinco auditores estáticos (fan-out) classificou a ausência de `FORCE ROW LEVEL SECURITY` como **Crítico**. A **verificação empírica rebaixou** esse achado para **Médio** (M-01): o caminho de request **força a RLS estruturalmente** via `SET LOCAL ROLE authenticated` por transação (fail-closed), o que neutraliza até um role de conexão *superuser/owner* — e é por isso que **todos** os testes de isolamento de escopo passam mesmo conectados como `postgres`. Não há vazamento demonstrável. A análise completa está em **M-01**. Registrar a discordância e o porquê faz parte do "executar, não confiar".

### Linha de base de qualidade (Área I1) — tudo verde

| Gate | Resultado | Evidência |
| --- | --- | --- |
| `uv run pytest --cov` (backend, @db) | **736 passed**, 0 fail, cobertura **94.02%** | `EXIT=0`, 134 s |
| Cobertura do **motor** (≥95% exigido) | `machine.py` **100%**, `rules.py` **100%**, `enums.py` **100%**, `transicoes.py` **99%** | term-missing |
| `uv run ruff check .` | **All checks passed** | `RUFF_EXIT=0` |
| `uv run mypy` (strict) | **Success: no issues** (84 arquivos) | `MYPY_EXIT=0` |
| `pnpm lint` (web) | **0 errors** (2 warnings → L-04) | `LINT_EXIT=0` |
| `pnpm build` (web, type-check) | **Compiled successfully** | `BUILD_EXIT=0` |
| `pnpm test` (web, vitest) | **165 passed** (25 arquivos) | `TEST_EXIT=0` |
| `audit/run_audit.py` (concorrência/terminais) | **5/5 PASS** | ver Apêndice |

---

## 2. Achados

### 🟡 Médios

#### M-01 · (Área F) Nenhuma tabela usa `FORCE ROW LEVEL SECURITY`; `.env.example` aponta o runtime ao role *owner*

- **Descrição.** Nenhuma migration emite `FORCE ROW LEVEL SECURITY` — apenas `ENABLE` (grep por `FORCE ROW LEVEL SECURITY` em `apps/api` → **zero** ocorrências; introspecção da tabela: `force=False` nas seis tabelas sensíveis). Em PostgreSQL, o *owner* da tabela é isento da RLS a menos que `FORCE` esteja ligado. Além disso, `apps/api/.env.example:22` documenta `DATABASE_URL` como o role *owner/superuser* (`postgres`), e a ativação do role não-owner `rastreio_runtime` é um "passo de operação" não imposto (`_runtime_role.sql:10-14`, criado `NOLOGIN`).
- **Verificação empírica que define a severidade.** O caminho de request **não** depende de `FORCE`: a fábrica de sessões de request (`main.py:68` → `create_request_session_factory`) executa, em **toda** transação, `SET LOCAL ROLE authenticated` (`infrastructure/database.py:195-199`), com **guarda fail-closed** que **levanta** se não houver claims (`database.py:130-147`). Como `SET ROLE authenticated` rebaixa até um *superuser* para um role não-owner/`NOBYPASSRLS` **dentro da transação**, a RLS **passa a valer**. Isso é provado: os testes de isolamento conectam como `postgres` (superuser) e mesmo assim o escopo é respeitado (`vendedor2` recebe 404 para a prova de `vendedor1` — `test_transicoes_endpoints.py::test_fora_do_escopo_e_inexistente_mesmo_404`, PASS; e `audit/run_audit.py` confirma isolamento). Introspecção: `authenticated` e `rastreio_runtime` são ambos `bypassrls=False`.
- **Evidência.**
  - `apps/api/audit/introspect_rls.py` →
    ```
    authenticated     bypassrls=False  ...
    rastreio_runtime  bypassrls=False  login=False  ...
    postgres          bypassrls=True   login=True   super=True
    provas        enable=True  force=False    (idem nas 6 tabelas)
    ```
  - `apps/api/.env.example:22` (`DATABASE_URL=...@localhost:5432/rastreio`, role `postgres`).
  - `apps/api/src/infrastructure/database.py:130-147,164-199` (fail-closed + `SET LOCAL ROLE authenticated`); `apps/api/src/main.py:68`.
- **Impacto.** **Nenhum vazamento demonstrado** no caminho de request (a RLS é forçada pelo *role switch* fail-closed). O risco é de **profundidade de defesa / operação**: a independência da camada de banco é hoje *procedural* (depende do `SET LOCAL ROLE`, ainda que fail-closed). Um deploy que conecte com role privilegiado **e** uma futura consulta de dado de usuário que abra sessão fora de `abrir_sessao_rls` cairiam para fora da RLS. `FORCE` por si só **não** fecharia o cenário do `.env.example` (superuser ignora `FORCE` de qualquer modo) — o controle que realmente importa é conectar como role não-superuser/`NOBYPASSRLS`.
- **Recomendação (remediação).** (1) Tornar **mandatório em produção** o `DATABASE_URL` apontando a `rastreio_runtime` (NOBYPASSRLS, não-owner) — ajustar `.env.example`/docs com aviso explícito ao lado da chave. (2) Adicionar uma **asserção de boot** que recuse subir se o role conectado for superuser/`rolbypassrls` (controle estrutural barato). (3) Como cinto-e-suspensório, `ALTER TABLE ... FORCE ROW LEVEL SECURITY` nas seis tabelas — **atenção**: os resolvedores `SECURITY DEFINER` em `private.*` rodam como owner e re-aplicam o escopo do chamador; validar que `FORCE` não os quebre (ou que sejam *owned* por role isento).

#### M-02 · (Área F/E) Drift do resolvedor `private.nomes_de_vendedores` vs. escopo do Motorista ampliado (C11)

- **Descrição.** `migrations/rls/nomes_de_vendedores.sql:46-49` re-aplica o escopo **antigo e estreito** do Motorista (só os 3 estados "Em Trânsito") dentro do `EXISTS`, enquanto a RLS real `provas_select_motorista` foi **ampliada** no C11/0015 para incluir também os 3 estados de origem (`encaminhada_para_laminacao`, `laminacao_concluida`, `de_volta_studio`). O resolvedor irmão `nomes_de_usuarios.sql:48-54` (C13) **foi** atualizado para os 6 estados — então os dois resolvedores agora **divergem**. O próprio cabeçalho do arquivo avisa "mantenha-os em sincronia" (`nomes_de_vendedores.sql:20-21`).
- **Evidência.** Predicado estreito (3 estados): `apps/api/migrations/rls/nomes_de_vendedores.sql:46-49`. Escopo real (6 estados): `apps/api/migrations/rls/provas_select_motorista.sql:14-21`. Irmão correto (6 estados): `apps/api/migrations/rls/nomes_de_usuarios.sql:48-54`.
- **Impacto.** **Restritivo, não vaza dados.** Um Motorista que vê uma prova num estado de **origem** na listagem (C07) veria o **nome do vendedor em branco/NULL** em vez do nome real. Defeito **cosmético** de completude de dado para um perfil, em caso raro. Sem corrupção de estado, sem leak cross-escopo.
- **Recomendação.** Adicionar os 3 estados de origem ao ramo `motorista` de `private.nomes_de_vendedores` (nova migration + espelho), ou documentar a divergência intencional em `DECISIONS.md`.

#### M-03 · (Área I2) Espelhos RLS da Wave 3 sem teste de equivalência — risco de drift silencioso

- **Descrição.** As migrations aplicam as policies/grants como **strings SQL inline duplicadas**, e os arquivos `migrations/rls/*.sql` são espelhos de reaplicação manual (CLAUDE.md §9: "reaplicar após DROP/recriação"). O harness de equivalência offline cobre **apenas** `provas_*` e `system_settings` (`tests/unit/test_equivalencia_rls_provas.py:79-104`); **não há** teste assegurando que `movimentacoes_*`, `assinaturas_*` e `rate_limit_contadores_*` continuem iguais ao SQL inline de 0014/0015/0016. O achado **M-02 é a prova viva** de que esse tipo de drift acontece e passa despercebido.
- **Evidência.** SQL inline: `0015_movimentacoes.py:88-102`, `0016_assinaturas.py:72-86`, `0014_rate_limit_identificacao.py:53-59`. Cobertura do harness: `tests/unit/test_equivalencia_rls_provas.py:82-104` (glob só `provas_*.sql`).
- **Impacto.** Uma edição futura num lado (migration ou espelho) passa no CI em silêncio; numa recriação de tabela o operador reaplica o espelho desatualizado, podendo **enfraquecer a RLS** do log imutável (`movimentacoes`) ou das assinaturas. Manutenibilidade / profundidade de defesa.
- **Recomendação.** Estender o harness de equivalência para `movimentacoes_*`/`assinaturas_*`/`rate_limit_contadores_*` (mesmo padrão de `test_equivalencia_rls_provas.py`), **ou** fazer as migrations `op.execute` os `.sql` (fonte única) em vez de inline.

### ⚪ Baixos

- **L-01 · (Área A/F)** `ESTADOS_ESCOPO_MOTORISTA` (`rules.py:154-182`) é **route-blind**: une origens/destinos das transições do Motorista em todas as rotas. Resultado: um Motorista enxerga (leitura RLS) uma prova `lam_filial` em `laminacao_concluida` mesmo sem ser o ator ali (em `lam_filial`, `laminacao_concluida`→Vendedor). **Não move** nada (o motor responde 422/403). Visibilidade de leitura levemente ampla, **não-leaking**, decisão documentada (ADR-065). *Aceitar como está ou tornar a derivação ciente de rota.*
- **L-02 · (Área I3)** Literal de duração **hardcoded** `1600ms` no keyframe de pulso do timeline (`ProofTimeline.module.css:131`) em vez do token `var(--motion-pulse)` (usado corretamente em `:256`). Viola a regra "sem literais de duração fora de `motion/tokens`" (CLAUDE.md §5.5). `prefers-reduced-motion` **ainda é honrado** por um bloco `animation: none` separado (`:293-298`). Cosmético.
- **L-03 · (Área I3)** Botões Cancelar/Reiniciar fazem transição CSS de `background`/`color` (`prova-detalhe.module.css:206-208,228-230`), fora do allowlist `transform`/`opacity` (CLAUDE.md §3 pilar 4). É *paint-only* (não causa reflow/jank) e a duração é tokenizada; `prefers-reduced-motion` zera o token. Cosmético.
- **L-04 · (Área I1)** 2 *warnings* do ESLint (0 errors): `Unused eslint-disable directive` e `aria-invalid is not supported by the role button` (`jsx-a11y`). Dívida menor.
- **L-05 · (Área D)** Ator **em escopo** mas no perfil errado recebe **403** (`transicao_nao_autorizada`), distinguível do **404** de "inexistente". Divergência **deliberada e documentada** da letra do RN-014 (que pede resposta indistinguível). **Não explorável para enumeração**: o 403 só dispara para provas que o ator **já enxerga** pela RLS (e já pode listar) — não revela existência fora do escopo. A mensagem do 403 é genérica e **não nomeia o próximo ator** (RN-014 atendido nesse ponto — `test_perfil_nao_autorizado_e_403_generico`). Informacional.

---

## 3. Matriz de cobertura (Áreas A–I)

| Área | Verificação | Veredito | Evidência / Achado |
| --- | --- | --- | --- |
| **A1** | `transition_rules` == §6 nas 4 rotas (travessia ponta a ponta) | ✅ PASSA | `rules.py:82-127`; travessias reais `test_travessia_completa_rota_{matriz,lam_matriz,filial,lam_filial}` (200 a cada passo, terminal carimbado); cross-check manual §6 |
| **A2** | Nenhuma transição inválida aceita (→422) | ✅ PASSA | `test_transicao_nao_definida_e_422`; sem wildcard (`machine.py:74`) |
| **A3** | Terminais sem saída | ✅ PASSA | `rules.py:50-52,143-144`; `audit/run_audit.py` (recebida_clicheria/cancelada → 422) |
| **A4** | Regras em código imutável (não no banco) | ✅ PASSA | `TRANSITION_RULES: Final[MappingProxyType]` (`rules.py:149-151`); nenhuma tabela de regras |
| **A5** | 403 (perfil) vs 422 (indefinida) corretos | ✅ PASSA | `machine.py:160-167`; `test_perfil_nao_autorizado_e_403_generico` + `test_transicao_nao_definida_e_422` |
| **B1–B3** | Nenhum caminho de status fora do motor | ✅ PASSA | Único writer `provas_repository.py:100-129`, único call-site `transicoes.py:184,213`; sem PATCH/PUT; nenhum trigger muta status (grep + dim B) |
| **C1** | Assinatura+movimentação atômicas (falha no meio → rollback) | ✅ PASSA | `test_transicao_service.py::test_atomicidade_falha_ao_gravar_{assinatura,movimentacao}_nao_commita`; UoW `__aexit__`→rollback |
| **C2** | Reinício: status+ciclo juntos ou nenhum | ✅ PASSA | `transicoes.py:205-221` (mesma transação); `test_reiniciar_*` |
| **C3** | Idempotência (reenvio não duplica) | ✅ PASSA | `test_reenvio_com_mesma_chave_converge_uma_movimentacao`; mesma chave/op diferente → 409 |
| **C4** | Concorrência não corrompe | ✅ PASSA | `audit/run_audit.py`: chaves distintas → `[200,422]` 1 mov; mesma chave → `[200,200]` 1 mov+1 assinatura (lock `FOR UPDATE` `provas_repository.py:96`) |
| **D1** | Inválido vs fora-de-escopo → mesma resposta | ✅ PASSA | `test_fora_do_escopo_e_inexistente_mesmo_404` (corpo idêntico "Prova não encontrada.") |
| **D2** | Ator não autorizado → genérico, sem revelar próximo | ✅ PASSA | `test_perfil_nao_autorizado_e_403_generico` (`"setor" not in message`) · ver L-05 |
| **D3** | Rate limit (30/min) | ✅ PASSA | `test_acima_do_limite_responde_429` |
| **D4** | Vazamento por timing | ◻️ Não avaliado | Não há sinal observável de timing-channel no código (resolução por índice único); não medido empiricamente |
| **E1** | Cada movimentação carimba o `ciclo` | ✅ PASSA | `models.py:216`, `transicoes.py:195`; coluna `ciclo` NOT NULL |
| **E2/E3** | Reinício: ciclos separados, histórico preservado (RN-006) | ✅ PASSA | `transicoes.py:195` (pré-incremento) + append-only (`movimentacoes` sem UPDATE/DELETE); `test_reiniciar_incrementa_ciclo_*` |
| **E4** | Timeline agrupa por ciclo; canônico derivado do C11 | ✅ PASSA | `sequencia_canonica` derivada de `TRANSITION_RULES` (`machine.py:122-146`); `test_provas_timeline.py` |
| **F1** | RLS isola leitura por perfil | ✅ PASSA | `test_rls_{provas,movimentacoes,assinaturas}` (suíte verde) + `audit/run_audit.py` isolamento |
| **F2** | Role sem BYPASSRLS + RLS não-decorativa | ⚠️ PARCIAL | role `NOBYPASSRLS` ✅; **falta `FORCE`** → **M-01** (Médio; enforcement do request provado) |
| **F3** | Cancelar/Reiniciar como Vendedor/etc → 403 | ✅ PASSA | `test_cancelar_e_admin_com_motivo` (studio não-admin → 403); duas camadas (`dependencies.py:276,311` + motor `Autorizacao.ADMIN`) |
| **F4** | Claims chegam ao Postgres e a RLS os usa | ✅ PASSA | `database.py:195-199` (`set_config` + `SET LOCAL ROLE`); `test_claims_propagation` (suíte verde) |
| **G1** | Cancelar: motivo obrigatório, sem assinatura, irreversível, só ativo | ✅ PASSA | `test_cancelar_e_admin_com_motivo`; `audit/run_audit.py` (cancelar de terminal → 422; RN-005) |
| **G2** | Reiniciar: só reprovada, sem motivo/assinatura, rota+prova preservadas | ✅ PASSA | `rules.py:67,113,125`; `test_vendedor_admin_pode_cancelar_e_reiniciar` |
| **G3** | Reprovar: exige motivo **+** assinatura | ✅ PASSA | `rules.py:75` + `exige_assinatura` (`machine.py:96-102`); `test_reprovar_exige_motivo` |
| **H1** | Assinatura armazenada conforme ADR (bytea, sem URL pública) | ✅ PASSA | `models.py:252` (LargeBinary); append-only (introspecção: triggers BEFORE UPDATE/DELETE) |
| **H2** | Resiliência: traço+ação persistem + retry mesma chave | ✅ PASSA | `confirmar-view.tsx` (sessionStorage + `idemRef` reusado; dim frontend) |
| **H3** | identificar→assinar→confirmar ≤ 3 toques | ✅ PASSA | `escanear-view.tsx`/`confirmar-view.tsx` (desenho + 1 toque no caminho feliz) |
| **I1** | Lint/types/test/build/cobertura | ✅ PASSA | §1 (tudo verde; motor 100%) |
| **I2** | Migrations up/down limpas; RLS reaplicável | ✅ PASSA (com M-03) | 0014–0018 reversíveis (dim docs); espelhos idempotentes — drift-control → **M-03** |
| **I3** | Animações GPU-only + `prefers-reduced-motion` | ⚠️ PARCIAL | reduced-motion honrado; 2 desvios cosméticos → **L-02, L-03** |
| **I4** | Sem segredos versionados; stateless | ✅ PASSA | `.env.example` documenta chaves; segredos server-only; sem console/log crítico |
| **I5** | Docs refletem a realidade | ✅ PASSA | 14/14 afirmações verificadas TRUE (dim docs); CLAUDE.md/CHANGELOG até sinalizam drifts anteriores corrigidos |

Legenda: ✅ PASSA · ⚠️ PARCIAL (achado registrado) · ◻️ Não avaliado.

---

## 4. Apêndice — testes de auditoria descartáveis

Criados em **`apps/api/audit/`** (claramente **temporários**, fora da suíte; não tocam código de produção). Reproduzir com o Postgres de teste em pé (`alembic upgrade head` aplicado):

```bash
cd apps/api
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/rastreio_test"

# Concorrência (C4) + rejeição de estados terminais (A3) + cancelar de terminal (G1/RN-005)
uv run python -m audit.run_audit          # → 5/5 PASS

# Introspecção da camada de banco (F2): roles, FORCE RLS, triggers append-only, grants
uv run python -m audit.introspect_rls     # → relatório de catálogo
```

**`audit/run_audit.py`** — dirige os endpoints reais (`POST /provas/{id}/transicoes` e `/cancelar`) contra o Postgres:
- `C4a` duas transições concorrentes (chaves distintas) na mesma prova → exatamente uma aplica (`[200, 422]`), **1** movimentação, sem corrupção;
- `C4b` duplo-submit concorrente (mesma chave) → converge (`[200, 200]`), **1** movimentação + **1** assinatura;
- `A3` `recebida_clicheria` → `identificar` rejeitado (422);
- `G1` cancelar prova terminal → 422 (status inalterado);
- `RN-005` cancelar prova já `cancelada` → 422.

**`audit/introspect_rls.py`** — queries read-only do catálogo: `pg_roles.rolbypassrls`, `pg_class.relrowsecurity/relforcerowsecurity`, `pg_policies`, triggers append-only e grants de coluna.

> Reprodução das linhas de base: `TEST_DATABASE_URL=... REQUIRE_DB_TESTS=1 uv run pytest --cov=src --cov-report=term-missing` (736 passed, 94.02%, motor 100%); `uv run ruff check . && uv run mypy`; `cd ../web && pnpm lint && pnpm build && pnpm test`.

---

## 5. Conclusão e próximo passo

A Wave 3 está **sólida o suficiente para seguir**. O coração do domínio — a máquina de estados — é uma transcrição fiel, imutável e 100%-coberta da §6; o invariante de ouro ("um só caminho de status, sempre pelo motor") **se sustenta** sob varredura exaustiva; atomicidade, idempotência e concorrência foram **provadas empiricamente**; a RLS isola escopos no caminho de request e as ações administrativas têm defesa em duas camadas.

Os 3 Médios são **dívida de profundidade-de-defesa e manutenibilidade** (endurecimento operacional do role de runtime; drift de um resolvedor restritivo; lacuna de teste de equivalência de espelhos RLS), nenhum deles um vazamento ou corrupção demonstrável. Os 5 Baixos são cosméticos/informacionais.

**Recomendação de próximo passo:** **GO** para a sequência do roadmap (**W4-C16 Dashboard Realtime**). Encaminhar M-01, M-02 e M-03 para uma **remediação leve** quando conveniente (não bloqueante) — idealmente endurecer o role de runtime (M-01) antes do primeiro deploy de produção, por ser o item com maior valor de robustez operacional.
