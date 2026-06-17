# Reinício de ciclo (W3-C15)

> A **ação administrativa de reiniciar o ciclo** de uma prova reprovada: disponível
> ao **3Studio** **somente** em **"Reprovada pelo Vendedor"**, **sem motivo e sem
> assinatura** (só confirmação). Volta o status a **"Criada"**, **preserva a rota
> original e o histórico integral do ciclo anterior**, e **incrementa
> `ciclo_atual`** — a **mesma prova** ganha um novo ciclo (mesmo código/QR/etiqueta).
> Passa pelo **motor de transição do C11** (fonte única de mudança de status) — não
> há um segundo caminho que altere `prova.status`.
>
> Referências: Backlog **C15** · Requisitos **RF-009, RN-006, RNF-006** · §6.6
> (transição de reinício) · §7 ("Reiniciar Ciclo" = Exclusivo 3Studio, ação no
> detalhe). Decisões: **ADR-076** (via o motor + incremento atômico de `ciclo_atual`
> + GRANT da 0018), **ADR-077** (sem assinatura nem motivo), **ADR-078** (carimbo de
> ciclo pré-incremento + UX/gating). Liga-se ao C08 (`ciclo_atual`/detalhe), C11
> (motor), C13 (timeline por ciclo), C14 (molde do cancelamento).

---

## 1. O que o C15 entrega

- **Botão "Reiniciar ciclo"** no detalhe (C08) — na **mesma linha das ações de
  etiqueta** (container `.acoes` em flex), **construtivo** (`.btnReiniciar`, contorno
  na cor da tinta — ≠ do perigo vermelho do cancelar), visível **só ao 3Studio**
  (flag `administrador` — Matriz §7/ADR-023) e **só em "Reprovada pelo Vendedor"**
  (o único estado de origem da transição de reinício — RN-006). Some sozinho assim
  que a prova sai desse estado.
- **Modal de confirmação** (reusa o `<MotionModal>` do C04): **sem campo de motivo**,
  explicando o que acontece (status volta a "Criada", **mesma rota**, **novo ciclo**,
  **histórico preservado**), confirmar / voltar; animação com `prefers-reduced-motion`
  (RF-024).
- **Endpoint dedicado `POST /provas/{id}/reiniciar`** que **invoca o motor do C11**
  (`acao=reiniciar_ciclo`) e, na **mesma transação atômica**, **incrementa
  `ciclo_atual`** — gravando a **movimentação** (ator + data/hora) no **log imutável**
  (`movimentacoes` — RNF-006), **sem assinatura desenhada e sem motivo**.
- **Migration 0018** — `GRANT UPDATE (ciclo_atual)` em `provas` ao `authenticated`,
  para o role de runtime (NOBYPASSRLS) poder escrever o incremento.

O C15 **não** modela a transição (é do C11 — `_REINICIAR` já existia em todas as 4
rotas) nem cria caminho de status próprio — apenas **dispara** o motor e adiciona o
**efeito de ciclo**.

---

## 2. Caminho do reinício (ADR-076) — uma única fonte de status + incremento atômico

```
detalhe (C08) ──"Reiniciar ciclo"──▶ ReiniciarCicloModal (só confirmação)
        │
        ▼  POST /provas/{id}/reiniciar  { idempotency_key }
get_reinicio_service  ── gate de BORDA: Recurso.REINICIAR_CICLO (admin) ──▶ 403 se não-admin
        │
        ▼
ProvasTransicaoService.executar(acao=REINICIAR_CICLO, assinatura_imagem=None, motivo=None)
        │   (o MESMO motor do C11 — lock FOR UPDATE → idempotência → avaliar_transicao
        │    → status=CRIADA + 1 movimentacao (ciclo PRÉ-incremento) → incrementar_ciclo
        │    → commit atômico)
        ▼
ProvaDetalheOut (status="criada", ciclo_atual=N+1)
```

**O incremento é o "efeito especial" do reinício.** O motor do C11 já é a fonte única
de status e **já carimbava** cada movimentação com `ciclo=prova.ciclo_atual`
(`transicoes.py`). O C15 adiciona uma só coisa ao `executar`: **se a ação reinicia o
ciclo** (`incrementa_ciclo(acao)` — fonte única em `machine.py`, parelha de
`exige_assinatura`), chama **`repo.incrementar_ciclo(prova_id)`** (`UPDATE ... SET
ciclo_atual = ciclo_atual + 1 RETURNING ciclo_atual`) **na MESMA transação**, **depois**
de registrar a movimentação. Transição (status→`criada`) e incremento (ciclo→N+1)
**nascem/falham juntos** (RNF-017): falha no meio → rollback de ambos.

**Idempotência (RNF-015):** o incremento vive no ramo "ainda não processado" do
`executar`, **depois** da checagem de `idempotency_key`. Um reenvio com a mesma chave
cai no ramo `existente` (converge, devolve a prova relida — já em `criada`, ciclo N+1)
e **NÃO reincrementa**. Resultado: reenviar 2× deixa `ciclo_atual = 2`, **nunca 3**.

**Por que um endpoint dedicado?** Idêntico ao C14: o `/transicoes` é gateado por
`Recurso.ESCANEAR` (**universal**), então a única barreira ao não-admin seria o motor.
Reiniciar é "Exclusivo 3Studio": o endpoint dedicado gateia na **borda** por
`Recurso.REINICIAR_CICLO`, entregando a **defesa em duas camadas** que a §7 pede
(borda **+** motor). Ambos chamam o **mesmo** `executar` — status continua **único**
(ADR-062). `acoes-disponiveis` (C12) **exclui** Reiniciar (`ACOES_FLUXO_ESCANEAMENTO`),
então o C15 dispara direto.

---

## 3. Carimbo de ciclo: pré-incremento (ADR-078) — a timeline separa os ciclos

A movimentação de reinício é carimbada com o **ciclo que se ENCERRA** (o
`prova.ciclo_atual` **antes** do incremento — é o valor lido do snapshot travado no
`FOR UPDATE`, e o incremento só acontece **depois** do `registrar(mov)`). Assim:

- O evento **"Ciclo reiniciado"** pertence ao **ciclo N** (o que terminou em reprovação)
  — a timeline (C13) o encaixa ao **fim** do ciclo N (a origem `reprovada_vendedor` não
  está na sequência canônica linear → cai no último índice).
- O **ciclo N+1** nasce **vazio**: a `<ProofTimeline>` agrupa por `movimentacoes.ciclo`
  e **sempre** inclui `ciclo_atual` no conjunto (`timeline.ts`), então o novo ciclo
  aparece como o ciclo **corrente**, fresco em "Criada", com o separador **"Ciclo N+1"**.

Nenhuma mudança foi necessária no C13 — ele já tratava o evento `reinicio` e o
agrupamento por ciclo (testado com fixture reiniciada). O **único** requisito do lado
da timeline era carimbar `movimentacoes.ciclo` corretamente, o que o motor já faz.

> **Naming:** `movimentacoes.ciclo` (por-movimentação, migration 0015) ≠
> `provas.ciclo_atual` (contador da prova, migration 0012). O reinício incrementa o
> **segundo** e estampa o **primeiro** com o valor antigo.

---

## 4. Sem assinatura e sem motivo (ADR-077) — §6.6 "Ação administrativa"

A **§6.6** define o reinício como *"Ação administrativa: Reiniciar Ciclo"* — **sem** o
passo "Assinar" e **sem** "Motivo obrigatório" (diferente de **Reprovar**, que assina,
e de **Cancelar**, que exige motivo). **US-010 pede só confirmação.** No código:

- **Sem assinatura:** `REINICIAR_CICLO ∈ ACOES_ADMINISTRATIVAS`, então
  `exige_assinatura(REINICIAR_CICLO)` é `False` — o endpoint passa
  `assinatura_imagem=None` e a movimentação nasce com `assinatura_ref` NULL (ADR-066,
  coluna já nullable — **sem migration**).
- **Sem motivo:** a regra `_REINICIAR = Transicao(REINICIAR_CICLO, ADMIN, CRIADA)` em
  `rules.py` **não** tem `exige_motivo=True` (≠ `_CANCELAR`), então `avaliar_transicao`
  **não** exige motivo; o endpoint passa `motivo=None` e o `ReiniciarIn` nem expõe o
  campo (só `idempotency_key`).

O comprovante do reinício é **ator autenticado + data/hora**, gravados na movimentação.

---

## 5. Acesso em duas camadas (ADR-076) — e o que a RLS faz

| Camada | Onde | Regra |
| --- | --- | --- |
| **UI** | `page.tsx` (servidor) → `can(perfil, "reiniciar_ciclo")` | esconde o botão de quem não é admin (flag) — sem ida extra ao backend (`fetchUsuarioAtual` memoizado) |
| **Borda** | `get_reinicio_service` → `autorizar(ator, Recurso.REINICIAR_CICLO)` | **403** para não-admin **antes** do motor |
| **Motor** | `machine.autoriza(Autorizacao.ADMIN, …)` | revalida pela flag — negar em qualquer camada basta (§5.4) |
| **RLS (dado)** | `provas_update_admin` (`app_is_admin()`) | escopa a **linha** do UPDATE (status + `ciclo_atual`); o GRANT de **coluna** (0018) habilita escrever `ciclo_atual` |

> `Recurso.REINICIAR_CICLO` **já existia** em `rbac.py` + `access-matrix.ts` +
> `access-matrix.cells.json` (admin-only, provisionado no C11/C14) — **nenhuma**
> mudança de Matriz/RLS de policy foi necessária; o C15 só **ligou** o recurso ao
> endpoint e à UI. A flag `administrador` é **ortogonal ao setor** (ADR-064): um
> Vendedor-admin pode reiniciar. Prova inexistente / fora do escopo → **mesmo 404
> genérico** (anti-enumeração — §11).

> **Coluna `ciclo_atual` no GRANT (migration 0018):** o grant de UPDATE em `provas` a
> `authenticated` é de **coluna** (privilégio mínimo — C11 deu só
> `status/finalizada_em/updated_at`). A 0018 **adiciona `ciclo_atual`** ao grant
> (espelho em `migrations/rls/provas_grants.sql` — as 4 colunas). Como o grant é do
> **role**, é o **motor** (`Autorizacao.ADMIN`) que garante que só o reinício (admin)
> toca `ciclo_atual` — nenhum fluxo operacional o atualiza.

---

## 6. Erros (semântica herdada do C11)

| Situação | Status | Código |
| --- | --- | --- |
| Reiniciado com sucesso (ou reenvio convergente) | **200** | — |
| Perfil não-admin (borda) | **403** | `Acesso negado.` |
| Prova **não** em "Reprovada pelo Vendedor" (incl. terminais) | **422** | `transicao_invalida` |
| Prova inexistente / fora do escopo | **404** | `prova_nao_encontrada` |
| `idempotency_key` reusada para outra operação | **409** | `idempotencia_conflito` |

**Só de "Reprovada pelo Vendedor" (RN-006):** qualquer outro estado de origem é uma
transição não modelada → **422** (sem incremento, sem movimentação). Depois de
reiniciar, a prova está em "Criada" (ciclo N+1) — um novo reinício é **422** até que
ela seja reprovada de novo.

---

## 7. Frontend

- **`page.tsx`** (servidor) resolve `podeReiniciar = can({setor, administrador},
  "reiniciar_ciclo")` via o **mesmo** `fetchUsuarioAtual` que já resolve `podeCancelar`
  (sem request extra) e passa o booleano ao view.
- **`prova-detalhe-view.tsx`**: botão construtivo (`.btnReiniciar`, contorno
  `--app-ink`) na **mesma linha (flex)** das ações de etiqueta, só quando
  `podeReiniciar && prova.status === "reprovada_vendedor"`; ao sucesso, reflete
  "Criada" + `ciclo_atual` da **resposta** (sem refetch) e **recarrega a timeline**
  (a movimentação de reinício e o novo ciclo separado aparecem).
- **`reiniciar-ciclo-modal.tsx`**: confirmação **sem motivo** (explica o reinício);
  `enviando` trava `onClose` (ESC/overlay) para o resultado chegar; **idempotência** —
  a chave nasce no inicializador de `useState` e o pai **remonta o modal via `key`** a
  cada abertura (timeout/5xx mantêm o modal aberto; converge sem reincrementar). 404 →
  toast genérico + volta à listagem.
- Helper `reiniciarCiclo` em `lib/api/transicoes.ts` (corpo `{ idempotency_key }`).

---

## 8. Testes

**Backend** (`@db` usa o Postgres local; mesma `TEST_DATABASE_URL`):

```bash
uv run pytest \
  tests/unit/test_state_machine.py \
  tests/unit/test_transicao_service.py \
  tests/integration/test_reinicio_endpoints.py \
  tests/integration/test_transicoes_endpoints.py
```

- `test_state_machine.py`: `incrementa_ciclo` True só para `REINICIAR_CICLO`
  (`ACOES_REINICIO`); a aresta que incrementa é **exatamente** `reprovada_vendedor →
  criada` em toda rota e todo destino do reinício é `CRIADA` (derivação travada).
- `test_transicao_service.py`: reiniciar incrementa `ciclo_atual` (1→2), grava 1
  movimentação **sem assinatura nem motivo** carimbada com o ciclo **pré-incremento**
  (1); reenvio idempotente **não** reincrementa; ação normal **não** toca o ciclo;
  reiniciar de estado não-reprovado → 422 sem efeito.
- `test_reinicio_endpoints.py` (@db): admin reinicia reprovada → 200, status `criada`,
  `ciclo_atual` 2 (response **e** banco — prova do GRANT 0018), **rota preservada**,
  **histórico anterior preservado**, movimentação `reiniciar_ciclo` (ator + data/hora,
  ciclo 1, sem motivo/assinatura); estados inválidos → 422; **não-admin → 403 na
  borda**; sem token → 401; idempotência (reenvio → 1 movimentação, ciclo = 2 não 3);
  Vendedor-admin reinicia (ortogonalidade); inexistente → 404.

**Frontend**: `prova-detalhe-view.test.tsx` (botão escondido a não-admin e fora de
"Reprovada pelo Vendedor"; modal **sem motivo**; reiniciar reflete "Criada" + ciclo 2 +
recarrega a timeline; erro de regra vira toast sem redirecionar).

---

## 9. Checklist de aceitação (§6 do prompt)

- [x] **Só reinicia provas em "Reprovada pelo Vendedor"** (outros estados → 422).
- [x] Reiniciar **invoca o motor do C11** (→ Criada) **e incrementa `ciclo_atual`** na
  **mesma transação atômica**; a movimentação é gravada no **log imutável**; **nenhum**
  caminho altera `status`/`ciclo_atual` por fora do motor.
- [x] **Status volta a "Criada"** e a **rota original é mantida** (imutável).
- [x] **Histórico do ciclo anterior preservado**; cada movimentação carrega o `ciclo`
  correto e a **timeline mostra os ciclos separados**.
- [x] **Sem motivo e sem assinatura** (só confirmação do 3Studio autenticado).
- [x] **Indisponível a não-3Studio** (UI escondida **+** 403 na borda **+** motor);
  botão só em "Reprovada pelo Vendedor" para o 3Studio; **animação** (RF-024) com
  `prefers-reduced-motion`.
- [x] **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy
  --strict`/`pytest`/`pnpm lint`/`build` verdes; migration 0018 `upgrade`/`downgrade`
  limpa.

---

## 10. Fronteiras (o que NÃO é do C15)

- A **transição/regra** "Reprovada pelo Vendedor → Criada" é do **C11** (o C15 só
  invoca e adiciona o efeito de ciclo).
- **Cancelamento** é o **C14** — o reinício é a alternativa ao cancelar, mas é fluxo
  distinto (Cancelar é terminal; Reiniciar reabre).
- A **reprovação** (que leva a "Reprovada pelo Vendedor") é do fluxo de assinatura
  (C11/C12) — o C15 atua **depois** dela.
- **Criar uma nova prova com rota diferente** (RF-009 cita como alternativa) é
  cancelar + criar (C14/C06), fora daqui.
