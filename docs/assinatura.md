# Assinatura digital no fluxo de escaneamento (W3-C12)

> Componente que **fecha o laço do fluxo de movimentação**: torna *identificar → assinar → confirmar → transição* funcional de ponta a ponta pela primeira vez. A assinatura desenhada é o **comprovante de cada movimentação** (RN-003).

Referências: Backlog **C12** · Requisitos **RF-006/007/008/028, RN-003, RN-014, RNF-009/013/016** · §6 (motor) · C10 (identificar) · C11 (motor de transição) · C08 (detalhe/anti-enumeração).

---

## 1. Visão geral

Depois que o C10 identifica a prova (QR ou manual) e leva à tela de confirmação `/provas/[id]/confirmar`, o C12:

1. **Descobre as ações** que o ator logado pode executar na prova agora (`GET /provas/{id}/acoes-disponiveis`) — reusando as regras do C11 (`transicoes_de` + `autoriza`), **sem duplicar a §6**.
2. **Apresenta a branch** correta (DP-4):
   - **(a)** ator é o próximo → a **assinatura aparece automaticamente** (RF-028);
   - **(b)** estados de posse do Vendedor → **Aprovar / Reprovar** (Reprovar exige **motivo**);
   - **(c)** ator **não** é o próximo → **bloqueio genérico**, sem revelar quem é (RN-014).
3. **Captura a assinatura desenhada** (`react-signature-canvas` → PNG) e **invoca o motor de transição do C11** (`POST /provas/{id}/transicoes`), passando a imagem.
4. O backend grava **a assinatura e a movimentação na MESMA transação atômica** — nascem/falham juntas (RNF-017/DP-1) — e devolve a prova no novo estado.

O C12 **não reimplementa a transição** (é do C11, atômica/idempotente): ele captura a assinatura e **invoca** o motor.

---

## 2. Modelo de dados — tabela `assinaturas` (migration 0016)

| Coluna | Tipo | Notas |
| --- | --- | --- |
| `id` | `uuid` PK | `gen_random_uuid()` (app gera no INSERT) |
| `prova_id` | `uuid` NOT NULL → `provas.id` | **denormalizado** para a RLS se escopar sem depender da movimentação |
| `ator_id` | `uuid` NOT NULL | = `app_current_user_id()` (quem assinou); sem FK (`usuarios` nunca é deletado) |
| `imagem` | `bytea` NOT NULL | o PNG do canvas — **na própria transação** (DP-2) |
| `content_type` | `varchar(100)` NOT NULL | `image/png` (ou `image/jpeg`) — alimenta o futuro proxy de leitura (C13) |
| `created_at` | `timestamptz` NOT NULL | `now()` |

Índice `ix_assinaturas_prova_id` (leitura por prova / EXISTS da RLS). **Append-only** (RN-003/RNF-006): trigger `trg_assinaturas_append_only` bloqueia UPDATE/DELETE até para o *owner* + ausência de GRANT UPDATE/DELETE.

### Vínculo com `movimentacoes` (DP-1)

A coluna `movimentacoes.assinatura_ref` nasceu **nullable e sem FK** no C11 (0015), deixada para o C12 fechar. A migration 0016 adiciona a FK `fk_movimentacoes_assinatura_ref_assinaturas` (`assinatura_ref → assinaturas.id`), **mantida NULLABLE**: Cancelar/Reiniciar (C14/C15) podem não capturar um traço desenhado; só o fluxo de assinatura cria a linha.

> **Por que `bytea` e não R2 (DP-2):** a assinatura é o artefato mais crítico do sistema e **precisa nascer/falhar junto** com a movimentação. Um `bytea` participa da MESMA transação do Postgres; um PUT no R2 **não** participa — um rollback deixaria um objeto órfão (a exata falha que o C08 já loga como CRITICAL para a arte). Além disso, o repositório **não tem URL pré-assinada** (o C08 usa *proxy-streaming*), então o R2 seria superfície nova sem ganho. Imagens de assinatura têm poucos KB.

### RLS (espelhos em `migrations/rls/assinaturas_*.sql`)

- **SELECT** (`assinaturas_select_por_prova_visivel`): espelha o escopo de `provas` via `EXISTS` sobre `prova_id` — você vê a assinatura de uma prova SE vê a prova. Habilita a leitura na Timeline (C13).
- **INSERT** (`assinaturas_insert_ator_em_escopo`): `WITH CHECK (ator_id = app_current_user_id() AND EXISTS(prova visível))` — ninguém forja assinatura de outro nem assina prova fora de escopo.
- **GRANT**: só `SELECT, INSERT` a `authenticated` (sem UPDATE/DELETE). Role de runtime `rastreio_runtime` (NOBYPASSRLS) herda o existente.

---

## 3. Endpoints

### `GET /provas/{id}/acoes-disponiveis` (W3-C12/DP-3)

Devolve as **ações do fluxo de escaneamento** (`identificar_e_assinar` / `aprovar` / `reprovar`) que o ator logado pode executar **agora** — `[{acao, exige_motivo, estado_destino}]`. Reusa `transicoes_de` + `autoriza` (`ProvasTransicaoService.acoes_disponiveis`). **Cancelar/Reiniciar NÃO entram** (ações administrativas com UI própria — C14/C15; senão todo admin escaneando qualquer prova ativa seria "o próximo ator", pois Cancelar existe em todo estado). **Lista vazia = não é a vez do ator** → a UI mostra o bloqueio genérico, sem revelar quem é (RN-014). Prova fora do escopo/inexistente → **404 genérico** (anti-enumeração). Gate `Recurso.ESCANEAR` (universal); escopo pela RLS.

### `POST /provas/{id}/transicoes` (W3-C11 estendido pelo C12)

`TransicaoIn` passou a carregar **`assinatura`** (imagem PNG em base64, com ou sem prefixo data-URL) no lugar do antigo `assinatura_ref` stub. O endpoint **decodifica** o base64 (malformado → 422 `assinatura_invalida`) e passa os bytes ao serviço, que:

1. trava a prova (`FOR UPDATE`) — fora do escopo/inexistente → 404 genérico;
2. checa idempotência (`idempotency_key`): reenvio da MESMA operação **converge** (200) sem recriar a assinatura; chave reusada p/ outra → 409;
3. valida a transição (`avaliar_transicao`): indefinida → 422; perfil errado → **403 genérico** (não revela o próximo ator); motivo ausente → 422;
4. **valida a imagem** (`validar_assinatura`, magic bytes/ tamanho ≤ 1 MB) e **insere `assinaturas`** → obtém o id;
5. atualiza `status` (+ `finalizada_em` nos terminais) e insere **`movimentacoes`** com `assinatura_ref` = o id da assinatura;
6. **um único commit** — falha em qualquer passo → rollback total (assinatura + movimentação + status). Idempotente (RNF-015) e atômico (RNF-017).

---

## 4. Frontend — `/provas/[id]/confirmar`

- **`AssinaturaPad`** (`react-signature-canvas@1.1.0-alpha.2` — a linha 1.1 dropou `findDOMNode`, removido no React 19) — "papel" branco com traço escuro: o PNG exportado fica legível em qualquer fundo. `touch-action: none` (desenhar não rola a página no mobile); `clearOnResize=false` + altura fixa (o teclado do motivo não apaga o traço).
- **Branches (DP-4):** decididas pelas `acoes-disponiveis` — assinar (Confirmar), Aprovar/Reprovar (+ motivo), ou bloqueio genérico.
- **Resiliência (RNF-016/DP-5):**
  - a `idempotency_key` é gerada uma vez (client) e **reusada nas retentativas** → converge;
  - antes de ir à rede, o traço (data-URL) + a ação + a chave vão a **`sessionStorage`** → um reload/queda **não perde** a operação (restaurada no `fromDataURL` quando o pad remonta);
  - falha de rede/5xx **preserva o canvas** (não limpa) e mostra **"Tentar novamente"**; 422/403/404 dão toast específico/genérico conforme o caso;
  - sucesso → toast com o novo estado + navega ao detalhe (`/provas/[id]`), que reflete o status atualizado.
- **≤ 3 toques** no caminho feliz (escanear → desenhar → Confirmar). **Mobile-first**; animações só `transform`/`opacity`, instantâneas sob `prefers-reduced-motion`. **Error boundary** em `error.tsx` (recuperação: recarregar / voltar ao escaneamento).

---

## 5. Anti-enumeração (RN-014)

- `acoes-disponiveis` e `transicoes` devolvem o **mesmo 404 genérico** para inexistente e fora-de-escopo;
- não-autorizado no motor → **403 genérico** que NÃO nomeia o próximo ator;
- lista de ações vazia → a UI mostra "Esta prova não está aguardando uma ação sua no momento." (sem revelar quem é);
- a imagem da assinatura nunca vaza por URL pública (fica em `bytea` sob RLS).

---

## 6. Testes

**Backend** (`uv run pytest ... ` — @db usa a mesma `TEST_DATABASE_URL`):
- `tests/unit/test_assinaturas_dominio.py` — `validar_assinatura` (PNG/JPEG/vazia/não-imagem/tamanho).
- `tests/unit/test_transicao_service.py` — vínculo assinatura↔movimentação; **atomicidade** (falha na assinatura OU na movimentação → nada commitado); idempotência não recria assinatura; `acoes_disponiveis` (assinar / aprovar-reprovar / não-ator vazio / admin sem cancelar / 404).
- `tests/integration/test_transicoes_endpoints.py` — assinatura nasce vinculada; assinatura inválida / base64 malformado → 422 sem efeito; reenvio não duplica assinatura; `acoes-disponiveis` (4 branches + 404).
- `tests/integration/test_rls_assinaturas.py` — SELECT por perfil (espelha provas), INSERT WITH CHECK, append-only (trigger + sem GRANT).
- `tests/integration/test_migrations.py` — 0016 cria a tabela/trigger/2 policies/FK; downgrade limpo; head = 0016.

**Frontend** (`pnpm test` / `pnpm test:e2e`):
- `confirmar-view.test.tsx` — 3 branches; canvas vazio bloqueia; Aprovar/Reprovar (motivo obrigatório); **resiliência** (falha preserva o traço + retry com a MESMA chave); 404 na carga → genérico.
- `e2e/confirmar.spec.ts` — guard de sessão; (E2E_LIVE) identificar → assinatura automática (RF-028).

---

## 7. Checklist de aceitação (§6 do prompt)

- [x] Identificada a prova, se o usuário é o próximo ator → **assinatura automática** (RF-028).
- [x] Se **não** é o próximo → **bloqueio genérico** sem revelar quem é; assinatura não habilitada.
- [x] Assinatura submetida **movimenta a prova** (motor do C11; atômica/idempotente).
- [x] **Aprovar/Reprovar** nos estados de posse do Vendedor; **Reprovar exige motivo**.
- [x] Falha na submissão **preserva os dados localmente e oferece retry** — o traço não se perde.
- [x] Fluxo **≤ 3 toques**; **mobile-first**; animações com `prefers-reduced-motion`.
- [x] `assinaturas` com **RLS**; vínculo correto com `movimentacoes`; **sem** URL pública.
- [x] Stateless; sem segredos versionados; R$ 0; `ruff`/`mypy`/`pytest`/`pnpm lint`/`build` verdes; migration `upgrade`/`downgrade` limpa; RLS reaplicável.

---

## 8. Fronteiras (fora do C12)

- **Timeline visual** (histórico das movimentações + exibição da assinatura) — **C13**. A RLS de SELECT de `assinaturas` já está pronta para ela; o endpoint de leitura/proxy da imagem é do C13 (que define a forma de exibição).
- **Cancelar / Reiniciar Ciclo** (e o incremento de `ciclo_atual`) — **C14/C15** (invocam o mesmo motor; têm UI própria, fora do fluxo de escaneamento).
