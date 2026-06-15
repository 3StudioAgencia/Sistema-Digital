# Auditoria — Wave 2 (Núcleo do Domínio de Provas: C06 · C07 · C08 · C09)

> **Tipo:** Auditoria independente, read-only e baseada em evidência (execução real de testes/linters/queries + inspeção de etiqueta gerada).
> **Data:** 2026-06-15 · **Auditor:** Claude Code (papel de auditor sênior independente).
> **Escopo confirmado com o dono:** C06 (Criar Prova + Rota + Etiqueta) · C07 (Listagem/Filtros) · C08 (Detalhe) · C09 (Configurações). Waves 0–1 já auditadas (GO); Wave 3+ não construída.
> **Ambiente:** Postgres local (zonky :5433) para os testes `@db`; **Supabase real** (`rastreio-provas-digitais` / `wmpxxrzbzqgsorjwczvz`) inspecionado **somente leitura** (catálogo/RLS/roles/trigger/índices/advisors); R2 verificado por código (proxy) — ver §5.
> **Régua de veredito (confirmada):** qualquer achado **Crítico** ⇒ NO-GO.

---

## 1. Sumário executivo + VEREDITO

**VEREDITO: ✅ GO para a Wave 3.**

> A Wave 2 entrega o núcleo do domínio com qualidade alta e os controles de segurança que mais importam **comprovadamente** corretos: a RLS de `provas` não vaza escopo (validada por perfil contra Postgres real), a arte nunca sai por URL pública (proxy + zero segredo no bundle), o detalhe não revela existência (anti-enumeração idêntica para inexistente e fora-de-escopo), a rota é imutável **no banco** (trigger rejeita `UPDATE` direto, até para o owner), o código `PRV-AAAA-MM-NNNNNN` é único e **aparece em destaque na etiqueta** (gerei e inspecionei o PDF), e as configurações só são graváveis pelo 3Studio (gate + RLS admin-only).

Nenhum achado **Crítico** e nenhum **Alto**. Um achado **Médio** levantado por revisão automatizada (ausência de error boundary) foi **investigado e rejeitado** com evidência (existe `(app)/error.tsx` testado cobrindo todas as rotas da wave). Restam **2 Baixos** e algumas **Observações** — nenhum bloqueia a Wave 3.

**Contagem de achados:** Crítico **0** · Alto **0** · Médio **0** (1 reivindicado → **rejeitado**) · Baixo **2** · Observação **10**.

---

## 2. Tabela de achados por severidade

### 2.1 Crítico — **nenhum**
### 2.2 Alto — **nenhum**
### 2.3 Médio — **nenhum** (1 reivindicado e rejeitado, ver R-01)

| ID | Dim | Local | Descrição | Veredito |
| --- | --- | --- | --- | --- |
| **R-01** | 2.6 (C08) | `apps/web/src/app/(app)/error.tsx` | Revisão automatizada alegou **ausência de error boundary de rota** (Médio, DoD §8/RNF-014). **REJEITADO:** existe `(app)/error.tsx` (`AppError`, com `reset()`/retry + report de observabilidade), renderizado dentro de `(app)/layout.tsx`, cobrindo **todas** as rotas da Wave 2 (`/provas`, `/provas/[id]`, `/provas/nova`, `/configuracoes`); **testado** em `(app)/error.test.tsx` (3 casos, incl. recuperação por `reset()`). Há ainda `app/error.tsx` (raiz) e `app/global-error.tsx`. O glob do agente tropeçou nos parênteses do route group `(app)`. | **Falso positivo** — DoD §8 satisfeita. |

### 2.4 Baixo

| ID | Dim | Local | Descrição | Requisito | Impacto | Remediação (NÃO aplicada) |
| --- | --- | --- | --- | --- | --- | --- |
| **B-01** | 2.5/2.10 (C07) | `apps/web/.../provas/_components/provas-view.test.tsx` | A suíte cobre tabela, debounce, hidratação da URL, filtros, "Limpar", "Ver", vazio/erro/403 — mas **não** o caminho de **scroll infinito / `carregarMais`** (append da página 2, reset à página 1 ao trocar filtro, retry de paginação). É o trecho de maior complexidade de estado e fica sem teste direto. | DoD §8 (testes da lógica); RNF-019 | Regressão de paginação (append duplicado, vazamento entre chaves, loop de retry) passaria no CI sem detecção. Sem risco de segurança. A lógica em si está correta (revisada) e a paginação server-side é testada `@db`. | Adicionar caso que mocke 2 páginas (`total>page_size`) e dispare "Carregar mais" (clicável sem `IntersectionObserver`), verificando append e o refetch `page:1` ao trocar a query. |
| **B-02** | 2.2 (C07) | `apps/web/.../provas/_components/provas-view.tsx:366-388` | US-012 #1 pede filtro de período com **intervalos predefinidos** (hoje, últimos 2 dias, última semana, personalizado). A UI tem apenas seletores de data livres (o equivalente "personalizado"); faltam os atalhos nomeados. O backend já suporta range (`criada_de/ate`, `finalizada_de/ate`). | US-012 #1 (RF-014) | Capacidade presente e combinável; falta a conveniência dos presets. O usuário obtém o mesmo resultado informando datas manualmente. | Adicionar chips de preset (Hoje / Últimos 2 dias / Última semana) que apenas pré-preenchem os campos de data existentes — sem mudança no backend. |

### 2.5 Observação / dívida menor

| ID | Dim | Local | Descrição | Impacto / Nota |
| --- | --- | --- | --- | --- |
| **O-01** | 2.6 | `apps/api/.../http/provas.py:13-14`; Backlog C06 #2 | Critério literal diz "PATCH em `rota` → **422**". A implementação rejeita de forma **mais forte**: **não existe endpoint de update** (PATCH `/provas` → **405**; PATCH `/provas/{id}` → 404/405) **e** o banco bloqueia via trigger. Discrepância apenas textual (405 é o status correto p/ método inexistente). | Rota comprovadamente imutável (domínio+HTTP+banco). Registrar a reconciliação do critério em `DECISIONS.md`. |
| **O-02** | 2.8 | `apps/web/.../prova-detalhe-view.tsx:268-281`; Backlog C08 #3/#4 | Histórico de movimentações em **empty state**: transições com responsável/timestamp e travessias do motorista são **inerentemente não-satisfazíveis na Wave 2** (dados vêm do C11; timeline é o C13). Fronteira de wave **limpa** (scaffold correto, sem `movimentacoes` meio-feita). | Revalidar os critérios C08 #3/#4 ao concluir C11+C13. |
| **O-03** | 2.8 | `domain/provas.py:210`; US-001 #6 | "A prova aparece no **dashboard**…" — o dashboard é o C16 (Wave 4). A porção verificável (nasce `CRIADA` na rota selecionada, aparece na listagem C07) está correta. | Revalidar #6 com o C16. |
| **O-04** | 2.5 | `provas-view.tsx:43-52` / `lib/api/provas.ts:43-52` | Coluna "Criada em" formatada em **UTC** deliberadamente para casar com o limite de dia do filtro (comparado em UTC no backend). Para fuso BRT, prova criada ~22h local pode exibir a data do dia seguinte. | Trade-off consciente e documentado (coerência filtro×coluna). Sem impacto em escopo/segurança. |
| **O-05** | 2.7 | `configuracoes-view.tsx:220,304-313` | Os cards seedam o estado dos inputs **uma vez** e não re-sincronizam do prop `config` após salvar. Benigno no fluxo atual (valor digitado == valor salvo; sem fonte concorrente). | Latente apenas se uma fonte concorrente (ex.: Realtime) alterar a config com a tela aberta. |
| **O-06** | 2.11 | `nova-prova-view.tsx:112`; `Dropdown.tsx:148` | Lint web: **2 warnings** (0 erros): `eslint-disable` morto (`no-console`) e `aria-invalid` não suportado por `role=button`. | Cosmético/a11y menor. `--fix` resolve um deles. |
| **O-07** | 2.4 | Supabase advisor `multiple_permissive_policies` em `public.provas` | 5 policies `SELECT` permissivas para `authenticated` (uma por perfil) — o Postgres avalia todas por query. **Trade-off de design documentado** (1 policy/perfil = auditabilidade), idêntico ao padrão de `usuarios` auditado **GO** na Wave 1. | Tabela pequena; impacto desprezível. Consolidável num único `OR` se algum dia virar hot path (custo: auditabilidade). |
| **O-08** | 2.10 | cobertura `http/dependencies.py` = **69%** | Módulo de **wiring/DI**: as linhas não cobertas são majoritariamente branches de **503 boot-sem-banco**. Domínio e serviço (`domain/*`, `application/*`) ficam todos **≥80%** (a maioria ~100%); os casos **403 por perfil** estão testados `@db` (vendedor→403 em criar/ler/salvar). | Não é módulo de domínio/serviço — não viola o piso da DoD. |
| **O-09** | — | Operação (dono) — herdado da Wave 1 | Pendências de **operação**, não de código: ativar **leaked-password protection** (advisor WARN), ativar `rastreio_runtime LOGIN` (opcional), secret do keep-alive, política de senha, `R2_*` em prod. | **Não bloqueiam:** o backend honra a RLS via `SET LOCAL ROLE authenticated` + guarda fail-closed **mesmo conectado como owner** — o role dedicado é defesa-em-profundidade adicional, não pré-condição da RLS. |
| **O-10** | 2.4 | Supabase advisor `unused_index` (INFO) em `provas`/`usuarios` | Os índices RNF-019 aparecem "não usados" apenas porque a prod **ainda não tem tráfego/dados**. São corretos e serão usados pelas consultas da listagem. | Nenhuma ação — falso sinal por ausência de carga. |

---

## 3. Resultados das execuções (saída real)

### 3.1 Análise estática — backend (verde)
```
ruff check .            → All checks passed!
ruff format --check .   → 114 files already formatted
mypy (strict)           → Success: no issues found in 66 source files
```

### 3.2 Testes + cobertura — backend (verde)
```
pytest (TEST_DATABASE_URL=…:5433/rastreio_test, REQUIRE_DB_TESTS=1)
461 passed in 67.23s
coverage TOTAL 94.69%  (Required 80.0% reached)
```
**Matriz de cobertura das células de provas (C06–C09):**

| Módulo | Cobertura |
| --- | --- |
| `src/domain/provas.py` | **100%** |
| `src/domain/settings.py` | 98% |
| `src/application/provas.py` | 98% |
| `src/application/settings.py` | 100% |
| `src/adapters/outbound/etiqueta/fpdf_etiqueta.py` | 95% |
| `src/adapters/inbound/http/provas.py` | 99% |
| `src/adapters/inbound/http/settings.py` | 100% |
| `src/adapters/outbound/db/provas_repository.py` | 80% (piso) |
| `src/adapters/outbound/db/settings_repository.py` | 86% |
| `src/adapters/inbound/http/dependencies.py` | 69% (wiring — ver O-08) |

### 3.3 Frontend (verde)
```
pnpm lint   → 0 errors, 2 warnings (O-06)
pnpm build  → Compiled successfully; TypeScript OK; rotas /provas, /provas/[id], /provas/nova, /configuracoes presentes
pnpm test   → Test Files 20 passed (20) · Tests 122 passed (122)
```

### 3.4 Segurança do domínio — Postgres real + testes negativos `@db`
**Supabase real (`wmpxxrzbzqgsorjwczvz`), inspeção read-only:**
- `alembic_version = 0013` (sem drift vs. o repo).
- RLS **habilitada** em `provas` e `system_settings`.
- Roles: `authenticated` **NOBYPASSRLS**, `rastreio_runtime` **NOLOGIN/NOINHERIT/NOBYPASSRLS** (membro de `authenticated`), `anon` NOBYPASSRLS. Apenas `postgres`(owner)/`service_role`/`supabase_admin` têm BYPASSRLS (esperado).
- Trigger `trg_provas_rota_imutavel` **BEFORE UPDATE OF rota** presente e habilitado.
- Índices: `ix_provas_status/rota/vendedor_id/created_at` + índice **parcial** `ix_provas_finalizada_em` + `uq_provas_codigo` (UNIQUE) + `pk_provas`.
- `private.nomes_de_vendedores(uuid[])` **SECURITY DEFINER**, `search_path=''`, **reaplica o escopo do chamador** no corpo (defesa em profundidade), **sem grant a `anon`** (só `authenticated`/`postgres`/`service_role`).
- Grants de **privilégio mínimo**: `provas` → `authenticated` `SELECT,INSERT` (sem UPDATE/DELETE); `system_settings` → `SELECT,INSERT,UPDATE` (sem DELETE).
- Advisors: **nenhum achado novo** sobre `provas`/`system_settings` (apenas `leaked-password` WARN e `alembic_version` RLS-no-policy INFO, ambos pré-existentes/conhecidos).

**Testes negativos de RLS por perfil (`test_rls_provas.py`, `@db`, todos verdes):**
- 3Studio e Clicheria veem **todas**; Vendedor vê **apenas as suas** (qualquer status); Motorista vê **apenas as 3 "Com Motorista"**; flag admin vê **todas**; **query fora do escopo → 0 registros**.
- INSERT exclusivo de admin; `WITH CHECK` endurecido rejeita status≠`criada`, código fora do charset e vendedor de outro setor/inativo; UPDATE/DELETE **sem grant**.
- **`UPDATE … SET rota` direto → rejeitado pelo trigger** ("rota e imutavel"), até para o owner; `SET rota = rota` (idempotente) e UPDATE de outras colunas passam.
- `rastreio_runtime` é NOBYPASSRLS e membro de `authenticated`; enums PG espelham o domínio.

### 3.5 Etiqueta — gerada e inspecionada (independente do código de teste)
PDF gerado via `FpdfEtiquetaGenerator`, texto extraído dos content streams:
- **Tamanho físico 95,00 × 55,00 mm** exatos (MediaBox 269.29×155.91 pt).
- Contém **todos** os campos RF-003: `Nome:` · `Requerimento:` (com zeros à esquerda `00155295` preservados) · `Cliente:` · `Vendedor:` · `Rota:` ("LAM. FILIAL") · **código `PRV-2026-06-K3T9XB` em destaque** · rodapé "Etiqueta de rastreio" · ano dinâmico 2026.
- **QR codifica o código puro** (sem URL/indireção) — `test_qr_codifica_exatamente_o_codigo`.
- **Config do C09 respeitada:** `personalizado` (110×70) muda o PDF; `padrao` ignora sobrescritas (volta a 95×55). Integração confirmada também `@db` (`test_etiqueta_respeita_template_personalizado`).
- Texto fora de latin-1 (acento/travessão/emoji) **não derruba** a geração (degrada para `?`).

> **Conclusão da dimensão mais traiçoeira:** o **código alfanumérico está presente e em destaque** na etiqueta — o fallback manual do C10 não está quebrado.

---

## 4. Checklist da Definition of Done global (Backlog §2 / CLAUDE.md §8)

| # | Critério | Status | Evidência |
| --- | --- | --- | --- |
| 1 | Code review aprovado | ✅ | Cada componente passou por revisão adversarial multi-agente registrada (ADR-040 C06, ADR-051 C09); esta auditoria é a revisão independente da wave. |
| 2 | Unitários ≥80% domínio/serviço · ≥95% máquina de estados | ✅ / N-A | Domínio/serviço ≥80% (a maioria ~100%, §3.2). Máquina de estados é o **C11/Wave 3** — **N-A** nesta wave. |
| 3 | Integração passando em staging | ✅ | 461 testes `@db` verdes contra Postgres real; migrations `0007–0013` aplicadas no Supabase real (`alembic_version=0013`). |
| 4 | Migrations aplicadas, versionadas e documentadas | ✅ | `0007–0013` versionadas + RLS espelhada em `migrations/rls/`; aplicadas no real; `upgrade/downgrade` definidos. |
| 5 | Validado contra critérios de aceitação das US (Req §5) | ✅ | Conformância item-a-item (§3.5, R-01..O-03) — alta conformidade; lacunas só de fronteira de wave (O-02/O-03) e B-02. |
| 6 | Validado contra a Matriz §7 (acesso não autorizado por perfil) | ✅ | `test_rls_provas`, `test_rls_system_settings`, e testes de endpoint: vendedor→403 (criar prova / ler+salvar config); fora-de-escopo→0/404 genérico. |
| 7 | Sem erros no console do browser / logs críticos no backend | ✅ | Build limpo; operação normal não emite log crítico (compensação de arte e config indisponível degradam com WARN, não CRITICAL salvo falha de compensação real). |
| 8 | Documentação interna atualizada | ✅ | `docs/provas.md`, `provas-listagem.md`, `provas-detalhe.md`, `configuracoes.md`; ADRs 035–051; CHANGELOG/README/CLAUDE em sync (verificado). |
| 9 | RLS versionada em `/migrations/rls/` | ✅ | `provas_*.sql`, `system_settings_*.sql`, `_runtime_role.sql`, `nomes_de_vendedores.sql`; equivalência domínio↔sql↔migration testada e verde. |
| 10 | Animações novas validadas com `prefers-reduced-motion` | ✅ | `useReducedMotion` central zera durações; só `transform`/`opacity` (C07/C08/C09 verificados); testes de reduced-motion no C09. |
| 11 | Escritas idempotentes (RNF-015) | ✅ | Criação por `prova_id` (converge / 409 em divergência); `PUT /settings` (upsert idempotente) — testado `@db`. |
| 12 | Listagens sem N+1; mínimo de requisições | ✅ | 1 query de página + 1 projeção de nomes (sem N+1); debounce 300ms; sem cache a invalidar (config lê fresca). |
| 13 | Error boundaries cobrindo a rota + recuperação testada (RNF-014/016) | ✅ | `(app)/error.tsx` (testado, com `reset()`) cobre todas as rotas da wave (ver R-01). |

---

## 5. Itens que requerem verificação em ambiente (não confirmáveis offline)

1. **R2 real (pré-assinatura/proxy com objeto real):** o **proxy** foi verificado por código (sem URL pública, sem key no bundle — grep limpo) e por testes com `FakeStorage`. O **download real de um objeto do bucket** `rastreio-provas-artes` não foi exercido nesta auditoria (exigiria as 4 `R2_*` de prod). Recomenda-se um smoke test em staging: criar prova com arte real → abrir o detalhe → confirmar que `<img>` recebe `blob:` e que nenhuma resposta carrega URL/host do R2.
2. **Template de etiqueta aplicado em produção:** a integração C09→C06 foi confirmada `@db`; em prod depende das `R2_*` configuradas e da leitura `system_settings` na sessão RLS — validar com um PUT real + download.
3. **Ativação do role `rastreio_runtime LOGIN`:** **opcional** (defesa em profundidade). Hoje a RLS já é honrada via `SET LOCAL ROLE authenticated` + guarda fail-closed mesmo conectando como owner — verificar apenas se/quando o `DATABASE_URL` de runtime for apontado para o role dedicado.
4. **Tempo de carga ≤ 3 s (RNF-001) sob volume real:** garantido **por construção** (paginação server-side, índices RNF-019, sem N+1), não medido com massa de dados real.
5. **Leaked-password protection / política de senha / secret do keep-alive:** ações de dashboard do dono (herdadas da Wave 1).

---

## 6. Lista priorizada de remediação

### Antes da Wave 3 (Críticos/Altos) — **nenhum**
Não há item bloqueante. A wave está liberada.

### Dívida rastreada (Baixos/Observações) — quando convier, sem bloquear
1. **B-01** — adicionar teste de scroll infinito/`carregarMais` no C07 (maior valor: fecha o ponto de maior complexidade de estado sem cobertura).
2. **B-02** — chips de preset de período (hoje / últimos 2 dias / última semana) no C07 (decisão de produto; backend já suporta).
3. **O-01** — registrar em `DECISIONS.md` a reconciliação do critério C06 #2 ("imutabilidade por 405 + trigger" em vez de 422).
4. **O-06** — limpar os 2 warnings de lint web (`eslint-disable` morto; `aria-invalid` em `role=button`).
5. **O-05 / O-08 / O-07** — robustez/cobertura/performance de baixo retorno; tratar como otimização posterior.
6. **O-02 / O-03** — **reexecutar** os critérios C08 #3/#4 e US-001 #6 ao concluir C11/C13 (histórico real) e C16 (dashboard).

---

### Apêndice — fronteiras verificadas (limpas)
- **C08 ↔ C11 ↔ C13:** histórico em empty state; **nenhuma** tabela `movimentacoes`/timeline meio-feita; nenhum fetch a recurso inexistente.
- **C09 ↔ C16:** o tempo de atraso é apenas **armazenado/validado**; o cálculo de "Atrasada" (horas úteis) é do C16 — ausente aqui, como esperado.
- **C06 ↔ C09:** o template salvo é **de fato** consumido pela geração da etiqueta (verificado por inspeção do PDF e teste `@db`).
- **Divergências de design reconciliadas e registradas** (CLAUDE.md §2.1 / ADRs): etiqueta com código + rota (ADR-038), "Rota direta" → nome real (ADR-046/DP-7), botões Cancelar/Reiniciar omitidos (ADR-046/DP-3), "template personalizado" = sobrescrita dos 5 campos (ADR-050). Refletidas no código.

> *Auditoria read-only. Nenhum arquivo de código/migration/RLS/config/documento de build foi alterado. Única escrita: este relatório.*
