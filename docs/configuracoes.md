# Configurações do Sistema (W2-C09)

> Tela e backend das **configurações do sistema** — exclusivas do 3Studio (Matriz §7).
> Implementa o **RF-022**: tempo de atraso (RN-008/US-016) e template de etiqueta
> (RN-011). Fecha a **Wave 2**.

Referências: Backlog **C09** · Requisitos **RF-022, RN-008, RN-011, US-016, RNF-011,
RNF-020** · Matriz §7 · C06 (template parametrizável) · C05 (`access-matrix`, RLS,
propagação de claims — ADR-008).

---

## 1. Visão geral

A tela vive no shell do C04 (`/configuracoes`) e mostra uma sequência de **cards**,
cada um com **título**, **descrição** e os **campos** da configuração + um botão
**"Salvar" próprio** (save granular — fiel ao padrão do design). Esta sessão entrega
os settings **reais** do RF-022 (o design é um scaffold com cards placeholder):

- **Tempo de atraso** (`delay_horas_uteis`): inteiro em **horas úteis**, padrão **48**.
- **Template de etiqueta** (`etiqueta_template`): **padrão** ou **personalizado**
  (sobrescreve os 5 parâmetros que o C06 já expõe).

> **Fronteira de cálculo (DP-4):** o C09 só **armazena** o tempo de atraso. Quem
> computa "Atrasada" (tempo no mesmo status em **horas úteis**, RN-008) é o **C16
> (Dashboard)**; a janela comercial é **fixa** (RNF-011: seg-sex 07-18). O C09 **não**
> calcula atraso.

---

## 2. Modelo de dados — `system_settings` (chave-valor)

Migration **`0013_system_settings`** (DP-1). Modelo **chave-valor**: os **defaults**
e a **validação por chave** vivem no domínio (`apps/api/src/domain/settings.py`,
fonte única); a tabela guarda só as **sobrescritas**. A leitura efetiva **sobrepõe a
sobrescrita ao default** — uma chave sem linha usa o default do registro.

| Coluna | Tipo | Notas |
| --- | --- | --- |
| `key` | `varchar(80)` PK | chave conhecida (`delay_horas_uteis`, `etiqueta_template`) |
| `value` | `jsonb` NOT NULL | valor (escalar ou objeto), validado pelo registro de domínio |
| `updated_at` | `timestamptz` NOT NULL `default now()` | carimbo do upsert (RETURNING) |
| `updated_by` | `uuid` NULL | UUID do admin que salvou (auditoria leve; **sem FK** — `usuarios` nunca é deletado) |

**Sem seed**: as linhas nascem só quando o admin salva (read-through dos defaults).

### Chaves conhecidas (registro de domínio)

| Chave | Tipo/valor | Default | Validação (escrita) |
| --- | --- | --- | --- |
| `delay_horas_uteis` | inteiro | `48` | inteiro, `1..9999` (recusa `bool`, float fracionário, string) |
| `etiqueta_template` | objeto | `{modo:"padrao", largura:95, altura:55, margem:3, fonte:"helvetica", qr_zona_quieta_modulos:2}` | `modo ∈ {padrao, personalizado}`; `largura 40..300`; `altura 20..300`; `margem 0..20`; `fonte ∈ {helvetica, times, courier}`; `qr_zona_quieta_modulos` inteiro `0..10` |

Os defaults de `etiqueta_template` **espelham** o `EtiquetaTemplate` do C06 — um teste
(`test_config_default_espelha_o_template_padrao_do_c06`) trava o drift.

---

## 3. RLS — leitura `authenticated`, escrita admin-only (DP-2/DP-3)

Versionada em `apps/api/migrations/rls/system_settings_*.sql` (espelho 1:1 da migration
0013); `ENABLE ROW LEVEL SECURITY` na migration de criação (padrão do `provas`/0007).

- **Leitura (`SELECT`) = `authenticated` (`USING true`)** — o valor (tempo de atraso,
  template) **não é sigiloso** e alimenta features de **todos os perfis** lidas
  server-side na sessão RLS do request: o **dashboard C16** (todos os perfis) lê
  `delay_horas_uteis`; a **etiqueta C06** (universal-em-escopo — ADR-046) lê
  `etiqueta_template`. Liberar a leitura faz esses consumos "simplesmente funcionarem"
  na própria sessão do usuário, sem função `SECURITY DEFINER`.
- **Escrita (`INSERT`/`UPDATE`) = admin-only** (`app_is_admin()` — flag `administrador`,
  ADR-023). Cobre o upsert (`INSERT ... ON CONFLICT DO UPDATE` usa ambos os ramos).
- **Sem `DELETE`** (privilégio mínimo — a app nunca apaga config).
- **Gate é o flag `administrador`**, não `setor=STUDIO` (ADR-023): um STUDIO sem o flag
  é negado; um vendedor-admin é aceito.

> A página continua **3Studio-only** pelo **proxy (C05)** + **gate do endpoint**
> (`Recurso.CONFIGURACOES`); a RLS é a defesa em profundidade da **escrita**.

Nota de semântica: o `UPDATE` de um não-admin é **filtrado** pela RLS (USING) — 0
linhas, **sem erro** (diferente do `INSERT`/WITH CHECK, que levanta). O valor não muda
(coberto por `test_nao_admin_nao_atualiza`).

---

## 4. Backend (Ports & Adapters)

```
domain/settings.py            # registro de chaves: defaults + validação + ConfiguracaoEtiqueta + efetivar_*
application/ports/settings_repository.py   # SettingsRepositoryPort + RegistroConfiguracao
application/settings.py        # SettingsService.listar / salvar / obter_config_etiqueta
adapters/outbound/db/settings_repository.py # SqlAlchemySettingsRepository (upsert, sem commit)
adapters/outbound/db/models.py # SystemSettingRow (JSONB)
adapters/inbound/http/settings.py          # router /settings (GET, PUT)
adapters/inbound/http/dependencies.py      # get_settings_service (gate CONFIGURACOES + RLS)
```

**Endpoints** (prefixo real **`/settings`** — convenção do projeto, **sem `/api`**):

- `GET /settings` → `ConfiguracaoOut[]` (valor efetivo + default + metadados). 3Studio-only.
- `PUT /settings/{chave}` → body `{ "valor": <any> }` → `ConfiguracaoOut`. Validação por
  chave (422 em chave/valor inválidos); `updated_by` vem do **`user.sub`** (nunca do body).

**Imediatismo (US-016) × cache (RNF-020):** **não há cache** no backend (DP-4) — toda
leitura vai fresca ao Postgres (linha única indexada, RNF-020). Salvar reflete na
próxima leitura **por construção**, sem invalidação. No front, o `PUT` retorna o valor
salvo e a tela atualiza o estado local (sem valor velho). `PUT` é **idempotente**
(RNF-015): mesmo valor → mesmo resultado.

---

## 5. Integração com a etiqueta (C06) — RN-011/DP-5

O C06 entregou o `EtiquetaTemplate` parametrizável mas o gerador **não lia config**.
No C09:

- `EtiquetaPort.gerar_pdf(prova, vendedor_nome, config: ConfiguracaoEtiqueta | None)`
  ganhou o parâmetro `config` (tipo de **domínio** — respeita o hexagonal).
- `FpdfEtiquetaGenerator._template_efetivo(config)`: `personalizado` → constrói o
  `EtiquetaTemplate` a partir dos 5 campos; `None`/`padrao` → template padrão. **Nenhuma
  outra mudança no gerador.**
- `ProvasConsultaService.gerar_etiqueta` lê a config (`settings_repo.obter("etiqueta_template")`)
  na **mesma sessão RLS** do request (leitura `authenticated` — DP-2) e a passa ao
  gerador. Falha na leitura → **template padrão** (degradação graciosa — "uma etiqueta
  sempre sai", mesma filosofia do cp1252 do C06).

Resultado: salvar o template em `/settings` muda **de fato** a etiqueta gerada em
`GET /provas/{id}/etiqueta.pdf` (provado em `test_etiqueta_respeita_template_personalizado`).

---

## 6. Frontend

```
app/(app)/configuracoes/page.tsx                     # wrapper fino (server)
app/(app)/configuracoes/_components/configuracoes-view.tsx  # client: cards + save granular
app/(app)/configuracoes/configuracoes.module.css     # estilos (tokens --app-*, --u)
lib/api/configuracoes.ts                             # listarConfiguracoes / salvarConfiguracao
```

- Cards **Tempo de atraso** e **Template de etiqueta**, cada um com **"Salvar" próprio**.
- Validação em tempo real (delay inteiro > 0; campos do template nos intervalos); erro
  inline por campo, limpa ao corrigir; o botão valida no clique e mostra o erro (o botão
  não fica desabilitado por invalidez — o usuário sempre vê o motivo).
- Estados: `carregando` (skeleton), `pronto`, `erro` (retry) e **`restrito`** (403 →
  defesa em profundidade; o proxy já redireciona não-admin).
- O `Modo` é um segmented control (pílula deslizante por `layoutId` — GPU); os campos do
  personalizado entram/saem por `opacity`/`y` (`AnimatePresence`). Tudo respeita
  `prefers-reduced-motion` (durações → `instant`). Sem literais de duração/easing.
- A nav (`nav-items.ts`) deixou de marcar a Configurações como placeholder (`componente`
  removido); a visibilidade por perfil já era do C05 (auto-oculta para não-admin).

---

## 7. Testes

Backend (`apps/api`, @db usam `TEST_DATABASE_URL`):

```
uv run pytest tests/unit/test_settings_dominio.py \
  tests/unit/test_settings_service.py \
  tests/unit/test_equivalencia_rls_system_settings.py \
  tests/unit/test_etiqueta_pdf.py \
  tests/integration/test_settings_endpoints.py \
  tests/integration/test_rls_system_settings.py
```

- domínio: validação por chave (bool/0/negativo/float/desconhecida), defaults, sync com
  o `EtiquetaTemplate`, `efetivar_config_etiqueta` tolerante;
- serviço: merge default×sobrescrita, salvar valida + commita, idempotência;
- endpoints @db: admin lê defaults; salva delay e a leitura reflete (US-016); 422 em
  inválido/chave desconhecida; **não-3Studio → 403** (guard); 401 sem token; a etiqueta
  reflete `padrao` vs `personalizado` (integração C06);
- RLS @db: admin insere; **não-admin bloqueado** (INSERT/UPDATE); leitura authenticated;
  sem `DELETE`;
- equivalência: as policies das `.sql` == migration 0013; leitura authenticated / escrita
  admin / sem DELETE.

Frontend (`apps/web`): `pnpm test` — `configuracoes-view.test.tsx` (render dos 2 cards,
salvar delay + toast, validação sem chamar API, personalizado revela campos e salva o
objeto, 403→restrito, erro→retry). E2E: `e2e/configuracoes.spec.ts` (proteção sem sessão;
`E2E_LIVE` para o fluxo admin/não-admin).

---

## 8. Critérios de aceitação (§6) — checklist

- [x] **Acesso negado a não-3Studio** em **duas** camadas: guard do endpoint
  (`get_settings_service` → 403) **e** RLS (escrita admin-only; query direta de não-admin
  bloqueada). Proxy (C05) redireciona a rota.
- [x] **Tempo de atraso** salvo (inteiro, horas úteis, default 48) e **aplicado
  imediatamente** (US-016) — sem cache (DP-4), nada a invalidar.
- [x] **Template de etiqueta** configurável (padrão/personalizado) e a **geração da
  etiqueta (C06) respeita** a config salva.
- [x] **`system_settings`** criada com **RLS versionada**; leitura `authenticated` mantém
  as features compartilhadas (C16/C06) funcionando server-side.
- [x] **UI** com save granular + feedback (toast), validação em tempo real, fidelidade ao
  padrão do design, animações com `prefers-reduced-motion`, responsivo.
- [x] **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/
  `pytest`/`pnpm lint`/`build` verdes; migration `upgrade`/`downgrade` limpa; RLS
  reaplicável.

---

## 9. Operação

A migration 0013 é aplicada por `uv run alembic upgrade head` (usa
`MIGRATIONS_DATABASE_URL`). No Supabase real foi aplicada no fechamento da sessão
(tabela + RLS + bump do `alembic_version` para `0013`); os advisors de segurança não
apontaram nada novo (o `rls_enabled_no_policy` em `alembic_version` é o lockdown
intencional da 0003).
