# Cancelamento de prova (W3-C14)

> A **ação administrativa de cancelar** uma prova: disponível ao **3Studio** em
> **qualquer estado ativo**, com **motivo obrigatório**, **terminal e irreversível**
> (RN-005). Passa pelo **motor de transição do C11** (fonte única de mudança de
> status) — não há um segundo caminho que altere `prova.status`.
>
> Referências: Backlog **C14** · Requisitos **RF-011, RN-005, RNF-006** · §6.6
> (transição de cancelamento) · §7 ("Cancelar Prova" = Exclusivo 3Studio, ação no
> detalhe). Decisões: **ADR-073** (via o motor + endpoint dedicado/2 camadas),
> **ADR-074** (sem assinatura desenhada), **ADR-075** (UX/gating). Liga-se ao C08
> (detalhe), C11 (motor), C13 (timeline).

---

## 1. O que o C14 entrega

- **Botão "Cancelar prova"** no detalhe (C08) — na **mesma linha das ações de
  etiqueta** (container `.acoes` repartido em **3 botões**: Visualizar · Baixar ·
  Cancelar), visível **só ao 3Studio** (flag `administrador` — Matriz §7/ADR-023) e
  **só em estados ATIVOS** (≠ `cancelada`, ≠ `recebida_clicheria`). A
  irreversibilidade se manifesta na própria UI: assim que a prova vira `Cancelada`
  (estado terminal), o botão some (e a linha volta a 2 botões).
- **Modal de confirmação destrutiva** (reusa o `<MotionModal>` do C04): **motivo
  obrigatório**, **aviso explícito de irreversibilidade** (RN-005), confirmar /
  voltar; animação de entrada/saída com `prefers-reduced-motion` (RF-024).
- **Endpoint dedicado `POST /provas/{id}/cancelar`** que **invoca o motor do C11**
  (`acao=cancelar`) com **motivo + ator** — atômico, idempotente, gravando a
  **movimentação** (ator + data/hora + motivo) no **log imutável** (`movimentacoes`
  — RNF-006), **sem assinatura desenhada**.

O C14 **não** modela a transição (é do C11) nem cria caminho de status próprio —
apenas **dispara** o motor.

---

## 2. Caminho do cancelamento (ADR-073) — uma única fonte de status

```
detalhe (C08) ──"Cancelar prova"──▶ CancelarProvaModal (motivo)
        │
        ▼  POST /provas/{id}/cancelar  { motivo, idempotency_key }
get_cancelamento_service  ── gate de BORDA: Recurso.CANCELAR_PROVA (admin) ──▶ 403 se não-admin
        │
        ▼
ProvasTransicaoService.executar(acao=CANCELAR, assinatura_imagem=None, motivo)
        │   (o MESMO motor do C11 — lock FOR UPDATE → idempotência → avaliar_transicao
        │    → status=CANCELADA (+ finalizada_em) + 1 movimentacao → commit atômico)
        ▼
ProvaDetalheOut (status="cancelada")
```

**Por que um endpoint dedicado e não reusar `POST /provas/{id}/transicoes`?**
O endpoint de transição é gateado por `Recurso.ESCANEAR` (**universal** — o fluxo
de escaneamento é de qualquer perfil), então a sua única barreira ao não-admin é o
**motor** (`Autorizacao.ADMIN`). Cancelar é "Exclusivo 3Studio": o endpoint
dedicado gateia na **borda** por `Recurso.CANCELAR_PROVA`, entregando a **defesa em
duas camadas** que a §7 pede (borda **+** motor). Ambos chamam o **mesmo**
`ProvasTransicaoService.executar` — a fonte de status continua **única** (ADR-062).

`GET /provas/{id}/acoes-disponiveis` (C12) **exclui** Cancelar (`ACOES_FLUXO_
ESCANEAMENTO`) de propósito — senão todo admin escaneando qualquer prova ativa
seria "o próximo ator". Por isso o C14 **dispara o cancelamento direto**, não via
descoberta de ações.

---

## 3. Sem assinatura desenhada (ADR-074) — resolução de RN-003 × §6.6

RN-003 diz "toda movimentação exige assinatura"; a **§6.6/RF-011** definem o
cancelamento como *"Ação administrativa: Cancelar Prova. Motivo obrigatório."* —
**sem** o passo "Assinar" (ao contrário de Reprovar, que tem "motivo → Assinar →
Confirmar"). **Vale a §6.6**: o cancelamento é administrativo, comprovado por
**motivo + ator autenticado + data/hora**, **sem** traço desenhado.

No código isso é a fonte única `exige_assinatura(acao)` em
`domain/state_machine/machine.py`: as **ações administrativas** (`CANCELAR`,
`REINICIAR_CICLO` = `ACOES_ADMINISTRATIVAS`, derivadas das transições gated por
`Autorizacao.ADMIN`) **não** capturam assinatura. `ProvasTransicaoService.executar`
aceita `assinatura_imagem: bytes | None`: nas ações operacionais valida e insere a
`assinaturas` (FK); nas administrativas grava a movimentação com **`assinatura_ref`
NULL** — a coluna nasceu **nullable** exatamente por isto (ADR-066). **Sem
migration nova.** O endpoint dedicado nem aceita campo de assinatura (`CancelarIn`
tem só `motivo` + `idempotency_key`).

---

## 4. Acesso em duas camadas (ADR-073) — e o que a RLS faz

| Camada | Onde | Regra |
| --- | --- | --- |
| **UI** | `page.tsx` (servidor) → `can(perfil, "cancelar_prova")` | esconde o botão de quem não é admin (flag) — sem ida extra ao backend (`fetchUsuarioAtual` memoizado) |
| **Borda** | `get_cancelamento_service` → `autorizar(ator, Recurso.CANCELAR_PROVA)` | **403** para não-admin **antes** do motor |
| **Motor** | `machine.autoriza(Autorizacao.ADMIN, …)` | revalida pela flag — negar em qualquer camada basta (§5.4) |
| **RLS (dado)** | `provas_select_*`/`provas_update_*` | **escopo de visibilidade**, não autoriza a ação |

> A flag `administrador` é **ortogonal ao setor** (ADR-023/ADR-064): um
> **Vendedor-admin** pode cancelar. E como a RLS de `provas` dá **visibilidade
> total ao admin** (`app_is_admin()` — ADR-039), qualquer admin enxerga e cancela
> qualquer prova; não existe caso "admin em-escopo → 404" (o 404 cobre só a prova
> **inexistente**). Prova inexistente / fora do escopo → **mesmo 404 genérico**
> (anti-enumeração — §11).

---

## 5. Erros (semântica herdada do C11)

| Situação | Status | Código |
| --- | --- | --- |
| Cancelado com sucesso (ou reenvio convergente) | **200** | — |
| Perfil não-admin (borda) | **403** | `Acesso negado.` |
| Motivo ausente (schema) / em branco (domínio) | **422** | (validação) / `motivo_obrigatorio` |
| Prova já `Cancelada`/`Recebida pela Clicheria` (terminal) | **422** | `transicao_invalida` |
| Prova inexistente / fora do escopo | **404** | `prova_nao_encontrada` |
| `idempotency_key` reusada para outra operação | **409** | `idempotencia_conflito` |

**Irreversibilidade (RN-005):** `Cancelada` é **terminal** (sem transição de
saída no C11) — recancelar (com chave nova) dá **422**; o histórico permanece
intacto. Para "refazer", cria-se uma **nova** prova (fluxo do C06, fora daqui).

---

## 6. Frontend

- **`page.tsx`** (servidor) resolve `podeCancelar = can({setor, administrador},
  "cancelar_prova")` e o passa ao view (sem request extra).
- **`prova-detalhe-view.tsx`**: botão de perigo (`.btnPerigo`, contorno
  `--app-danger`) na **mesma linha (flex, larguras iguais)** das ações de etiqueta,
  só quando `podeCancelar && estaAtiva(prova.status)`; ao sucesso,
  reflete `Cancelada` a partir da **resposta** (sem refetch — §3.3) e **recarrega a
  timeline** (a nova movimentação aparece — `recarregar` da `<ProofTimeline>`).
- **`cancelar-prova-modal.tsx`**: aviso de irreversibilidade + `textarea` de motivo
  (obrigatório — confirmar desabilitado sem motivo); `enviando` trava `onClose`
  (ESC/overlay) para o resultado chegar; **idempotência** — a chave nasce no
  inicializador de `useState` e o pai **remonta o modal via `key`** a cada
  abertura, então a chave é reusada nas retentativas (timeout/5xx mantêm o modal
  aberto — ADR-068). 404 → toast genérico + volta à listagem.
- Helper `cancelarProva` em `lib/api/transicoes.ts`; `estaAtiva`/`ESTADOS_TERMINAIS`
  em `lib/provas/status-labels.ts`.

---

## 7. Testes

**Backend** (`@db` usa o Postgres local; mesma `TEST_DATABASE_URL`):

```bash
uv run pytest \
  tests/unit/test_state_machine.py \
  tests/unit/test_transicao_service.py \
  tests/integration/test_cancelamento_endpoints.py \
  tests/integration/test_transicoes_endpoints.py
```

- `test_state_machine.py`: `ACOES_ADMINISTRATIVAS` == as ações gated por `ADMIN`
  (derivação travada); `exige_assinatura` (operacional True, administrativa False);
  Cancelar exige admin + motivo; terminal → 422.
- `test_transicao_service.py`: cancelar com `assinatura_imagem=None` →
  `assinatura_ref` NULL, sem `assinaturas`, `finalizada_em` carimbado; ação
  operacional sem assinatura → 422.
- `test_cancelamento_endpoints.py` (@db): admin cancela ativa → 200 + movimentação
  (ator + data/hora + motivo) **sem assinatura**; sem motivo / em branco → 422;
  terminal → 422; **não-admin → 403 na borda**; irreversibilidade (recancelar →
  422); idempotência (reenvio → 1 movimentação); admin vê/cancela prova de qualquer
  vendedor; inexistente → 404.

**Frontend**: `prova-detalhe-view.test.tsx` (botão escondido a não-admin e em
estado terminal; modal exige motivo; cancelar reflete "Cancelada" + recarrega a
timeline; erro de regra vira toast sem redirecionar). E2E `e2e/cancelamento.spec.ts`
(gated por `E2E_LIVE`; confirmar destrutivo atrás de `E2E_CANCELAR=1`).

---

## 8. Checklist de aceitação (§6 do prompt)

- [x] **Cancelar sem motivo é bloqueado** (front: confirmar desabilitado; back:
  422 schema/`motivo_obrigatorio`).
- [x] Cancelar **invoca o motor do C11** (→ Cancelada), gravando a **movimentação**
  (ator + data/hora + motivo) no **log imutável**; **nenhum** caminho altera
  `status` por fora do motor.
- [x] **Prova cancelada não reativa** (terminal); **histórico preservado**.
- [x] **Indisponível a perfis não-3Studio** (UI escondida **+** 403 na borda **+**
  motor); botão só em **estados ativos** para o 3Studio.
- [x] **Modal destrutivo** com aviso de irreversibilidade; **animação** (RF-024)
  com `prefers-reduced-motion`; ao sucesso, detalhe + timeline refletem "Cancelada".
- [x] **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy
  --strict`/`pytest`/`pnpm lint`/`build` verdes.

---

## 9. Fronteiras (o que NÃO é do C14)

- A **transição/regra** "ativo → Cancelada" é do **C11** (o C14 só invoca).
- **Reinício de ciclo** (reprovação) é o **C15**.
- **Criar nova prova** após cancelar é o fluxo de criação do **C06**.
- **Assinatura desenhada** é do **C12** — e o cancelamento, por decisão (ADR-074),
  não a usa.
