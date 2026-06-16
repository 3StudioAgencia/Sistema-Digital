# Máquina de Estados — 14 Estados, 4 Rotas (W3-C11)

> O **coração do domínio**. As regras de transição (a Requisitos v1.0 **§6**) vivem
> em **código versionado**, nunca no banco (CLAUDE.md §5.3 / DAT §4). Este módulo
> entrega o motor autoritativo, a tabela imutável `movimentacoes` e o endpoint de
> transição. As telas que **dirigem** o motor vêm depois: assinatura (C12),
> timeline (C13), cancelar/reiniciar (C14/C15).

## 1. Onde vivem as regras

`apps/api/src/domain/state_machine/`:

| Arquivo | Conteúdo |
| --- | --- |
| `enums.py` | `Acao` (5 ações, ↔ PG `acao_enum`) e `Autorizacao` (setor operacional **ou** flag `admin`). Reexporta `Rota`/`EstadoProva` (de `domain/provas.py`) e `Setor`. |
| `rules.py` | `TRANSITION_RULES`: a §6 inteira como `MappingProxyType` **imutável**, indexada por `(rota, estado_atual) → tupla de Transicao`. `ESTADOS_TERMINAIS` e `ESTADOS_ESCOPO_MOTORISTA` (derivado). |
| `machine.py` | `avaliar_transicao(...)` — função **pura** que valida e devolve a `Transicao`, ou levanta erro de domínio. Os erros `TransicaoInvalidaError`/`TransicaoNaoAutorizadaError`/`MotivoObrigatorioError`. |

**Sem wildcard nem fallback** (§11): `(rota, estado, ação)` não listada é rejeitada.
O `CANCELAR` transversal é materializado em **todo estado ativo** na construção do
dict (não é um curinga de runtime — a consulta é sempre exata).

### A matriz (§6, conferida célula a célula)

- **Matriz:** Criada →(Vendedor)→ Retirada →(Vendedor:Aprovar)→ Aprovada →(3Studio)→ De volta à 3Studio →(Motorista)→ Com Motorista (entrega final) →(Clicheria)→ Recebida.
- **Lam. Matriz (11):** + ida/volta de laminação pelo Motorista antes da retirada do Vendedor.
- **Filial:** Criada →(Vendedor)→ Encaminhada p/ Vendedor →(Vendedor:Aprovar)→ Aprovada →(Clicheria)→ Recebida.
- **Lam. Filial (7):** + ida de laminação; "Laminação Concluída" →(**Vendedor**)→ (≠ Lam. Matriz → Motorista).
- **Transversais:** Reprovar (Vendedor, +motivo) → Reprovada; Reiniciar Ciclo (admin) → Criada; Cancelar (admin, +motivo) de qualquer estado ativo → Cancelada.

**Desambiguação por rota** (a rota decide o ator/destino do MESMO estado):
"Aprovada pelo Vendedor" → 3Studio (Matriz/Lam.Matriz) **vs.** Clicheria
(Filial/Lam.Filial); "Laminação Concluída" → Motorista (Lam.Matriz) **vs.** Vendedor
(Lam.Filial). Por isso a chave é `(rota, estado)` — nunca uma regra global por estado.

### Autorização (ADR-023)

- **Normal-flow** (`IDENTIFICAR_E_ASSINAR`/`APROVAR`/`REPROVAR`): pelo **setor** (RN-004).
- **`CANCELAR`/`REINICIAR_CICLO`** ("Exclusivo 3Studio" na Matriz §7): pela **flag
  `administrador`** (qualquer setor admin) — consistente com `domain/rbac.py`. Um
  Vendedor-admin cancela; um 3Studio não-admin, não.

## 2. O motor de transição (`application/transicoes.py`)

`ProvasTransicaoService.executar(...)`, numa **única transação** (RNF-017):

1. **Lock pessimista** `SELECT ... FOR UPDATE` da prova (serializa transições
   concorrentes — DP-2). Fora do escopo / inexistente → **404** genérico (a RLS
   resolve o escopo; anti-enumeração).
2. **Idempotência** (RNF-015/DP-2): há `movimentacoes` com esta `idempotency_key`?
   - mesma operação (prova+ação) → **converge** (devolve a prova já no estado
     destino, sem reaplicar — **200**);
   - chave reusada p/ operação diferente → **409** (`idempotencia_conflito`).
3. **Validação pura** (`avaliar_transicao`): indefinida → **422**; perfil errado →
   **403** (genérico, sem revelar o próximo ator — RN-014); motivo obrigatório
   ausente → **422**.
4. **Aplica**: `provas.status` (+ `finalizada_em` nos terminais) e UMA linha em
   `movimentacoes`. **Commit atômico** — falha no meio → rollback completo.

Idempotência sob concorrência: o `FOR UPDATE` serializa; o segundo submit relê o
estado já atualizado e o vê na `idempotency_key` (replay) — **uma** movimentação,
**uma** transição.

## 3. `movimentacoes` — log de auditoria imutável (DP-3)

Migration **`0015`**. **É** o log de auditoria (RNF-006) — não há `audit_log`
separado (divergência DAT §2 / Backlog C05 registrada no DECISIONS — ADR). Colunas:
`prova_id` (FK), `estado_origem`, `estado_destino`, `acao` (`acao_enum`), `ator_id`,
`ciclo`, `motivo` (null), `assinatura_ref` (uuid null — o C12 fornece a real + FK),
`idempotency_key` (uuid **UNIQUE**), `created_at`.

**Imutabilidade (append-only)** em duas camadas: trigger
`trg_movimentacoes_append_only` (bloqueia UPDATE/DELETE **até para o owner**) +
ausência de GRANT UPDATE/DELETE. **RLS** (`migrations/rls/movimentacoes_*.sql`):
- **SELECT** espelha o escopo de `provas` via `EXISTS (SELECT 1 FROM provas …)` —
  você vê as movimentações de uma prova **se vê a prova** (habilita a Timeline do
  C13 para perfis em escopo; o log completo só é visível a quem vê todas as provas);
- **INSERT** `WITH CHECK`: `ator_id = app_current_user_id()` (não forja autor) **E**
  prova no escopo. A **validade** da transição é do motor no app (§11).

## 4. RLS de `provas` — superfície de UPDATE (W3-C11)

- `GRANT UPDATE (status, finalizada_em, updated_at)` — **só** estas 3 colunas
  (privilégio mínimo; nunca codigo/nome/rota/vendedor_id). O trigger de rota
  imutável (0007) barra mudança de rota.
- 5 policies `provas_update_<perfil>` espelhando o escopo de SELECT (USING=origem,
  WITH CHECK=destino).
- **`provas_select_motorista` AMPLIADA**: o Motorista atua a partir de
  `encaminhada_para_laminacao`/`laminacao_concluida`/`de_volta_studio` (origens),
  que **não** são "Em Trânsito". Sem a ampliação ele receberia 404 ao escanear a
  prova que precisa pegar e nunca iniciaria a travessia. O escopo operacional =
  `ESTADOS_ESCOPO_MOTORISTA` (origens das transições do Motorista + Em Trânsito),
  **derivado da §6** — fonte única travada pelo harness de equivalência. Divergência
  da Matriz §7 (a listagem do Motorista passa a mostrar "aguardando coleta")
  registrada no DECISIONS (ADR).

## 5. Endpoint de transição

`POST /provas/{prova_id}/transicoes` → `ProvaDetalheOut` (prefixo real `/provas`,
sem `/api`). Body `TransicaoIn`: `acao`, `assinatura_ref` (uuid — C12 fornece;
stub no C11), `idempotency_key` (uuid), `motivo` (opcional). Gate de página
`Recurso.ESCANEAR` (universal — o fluxo identificar→assinar→confirmar é de qualquer
perfil ativo); a autorização **fina** por ação é do motor. Fábrica
`get_transicao_service` (sessão RLS única; o `ator` carregado para o gate alimenta
o motor).

| Caso | HTTP | code |
| --- | --- | --- |
| Transição executada | 200 | — |
| Reenvio idempotente (mesma chave) | 200 | — |
| Transição não definida (terminal/ação inválida) | 422 | `transicao_invalida` |
| Motivo obrigatório ausente | 422 | `motivo_obrigatorio` |
| Perfil não autorizado (em escopo) | 403 | `transicao_nao_autorizada` |
| Prova fora do escopo / inexistente | 404 | `prova_nao_encontrada` |
| Chave de idempotência reusada p/ outra operação | 409 | `idempotencia_conflito` |
| Sem token / não provisionado | 401 / 403 | — |

## 6. Fronteiras (quem INVOCA o motor)

- **C12 — Assinatura:** captura a assinatura (`react-signature-canvas`), cria a
  tabela `signatures` + a FK de `assinatura_ref`, e chama este endpoint.
- **C13 — Timeline:** LÊ `movimentacoes` (o C11 gera os dados).
- **C14 — Cancelar / C15 — Reiniciar:** a UI/gatilho e o **incremento de
  `ciclo_atual`** (C15); a transição é **modelada e executada** aqui.

## 7. Critérios de aceitação (§6 do prompt) — evidência

- ✅ Toda transição da §6.2–6.6 executável; não definida → 422
  (`test_state_machine`, `test_transicoes_endpoints`).
- ✅ Perfil não autorizado → 403, mesmo com rota+estado válidos.
- ✅ Travessia completa de Matriz/Lam.Matriz/Lam.Filial/Filial até o terminal.
- ✅ Reprovar/Cancelar exigem motivo; Reiniciar volta a "Criada" (rota preservada).
- ✅ Atomicidade (rollback na falha) e idempotência (reenvio não duplica) —
  `test_transicao_service` + `test_transicoes_endpoints`.
- ✅ `movimentacoes` imutável (trigger) + RLS por perfil (`test_rls_movimentacoes`);
  `finalizada_em` nos terminais.
- ✅ Roteamento lido de `prova.rota`; rota imutável; terminais sem saída.
- ✅ Cobertura da máquina de estados **100%** (`enums`/`rules`/`machine`); serviço 98%.

## 8. Testes

```bash
cd apps/api
# máquina pura (offline) + serviço (offline, atomicidade/idempotência)
uv run pytest tests/unit/test_state_machine.py tests/unit/test_transicao_service.py
# integração (@db) — travessias, 422/403/404/409, idempotência, RLS, imutabilidade
uv run pytest tests/integration/test_transicoes_endpoints.py \
              tests/integration/test_rls_movimentacoes.py \
              tests/unit/test_equivalencia_rls_provas.py
```
