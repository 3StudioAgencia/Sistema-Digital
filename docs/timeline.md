# Timeline Visual — `<ProofTimeline>` (W3-C13)

> A timeline é como o usuário **enxerga a verdade** do fluxo: ela espelha exatamente a
> máquina de estados (C11). Preenche a seção **"Histórico de movimentações"** do
> detalhe (C08), que vinha em empty state.

Referências: Backlog **C13** · Requisitos **RF-012, RF-026, RN-006, RN-012, RNF-010** ·
§6 (caminhos por rota) · §7 (mesmo escopo do detalhe) · C11 (regras + `movimentacoes`) ·
C07 (rótulos de status) · C08 (detalhe).

---

## 1. Visão geral

`<ProofTimeline provaId />` é um **client component** embutido no card preto do detalhe.
Ele busca **uma** vez `GET /provas/{id}/movimentacoes` e desenha, por **ciclo**, o caminho
da rota: etapas **percorridas** (responsável + data/hora), a **atual destacada** (anel
animado), as **futuras esmaecidas**; **laminação** e **travessias de motorista**
diferenciadas; **reprovação/cancelamento** com **motivo em destaque**; **múltiplos ciclos**
com **separador**.

A falha do histórico é **isolada** na própria `ProofTimeline` (estado de erro local + retry):
o detalhe (C08) **não cai** junto (pilar §3.6 / robustez).

## 2. Fonte do caminho canônico (DP-1) — derivado das regras do C11

O "esqueleto" da rota **não duplica a §6**: é **derivado** das `TRANSITION_RULES` do C11 por
**`sequencia_canonica(rota)`** (`apps/api/src/domain/state_machine/machine.py`), uma função
**pura** que caminha de `CRIADA` seguindo a única ação de **avanço** (`ACOES_AVANCO =
{identificar_e_assinar, aprovar}`) até o terminal `recebida_clicheria`. Determinística:
na §6 todo estado ativo tem **exatamente uma** transição de avanço (Reprovar/Cancelar/
Reiniciar são **desvios**, não entram no caminho linear).

Comprimentos (nós, incluindo o terminal): **Matriz 6 · Lam. Matriz 11 · Filial 4 ·
Lam. Filial 7**. Um teste (`test_state_machine.py`) confirma a sequência **célula a célula**
contra o oráculo independente das travessias — se a §6 mudar e a derivação driftar, falha.

O frontend recebe a sequência pronta (`etapas_canonicas`) e só aplica os **rótulos**
(`rotuloStatus` do C07; `rotuloRota` do C08). Nenhuma cópia da §6 vive no front.

## 3. Fetch das movimentações (DP-2)

**`GET /provas/{prova_id}/movimentacoes`** → `TimelineOut`:

```jsonc
{
  "rota": "lam_matriz",
  "estado_atual": "de_volta_studio",
  "ciclo_atual": 1,
  "criada_em": "2026-04-27T09:00:00Z",   // carimba o nó inicial "criada"
  "etapas_canonicas": ["criada", "...", "recebida_clicheria"],
  "movimentacoes": [                       // ordem cronológica (asc)
    { "id": "...", "estado_origem": "criada", "estado_destino": "retirada_vendedor",
      "acao": "identificar_e_assinar", "ator_id": "...", "ator_nome": "Regiane",
      "ciclo": 1, "motivo": null, "tem_assinatura": true, "created_at": "..." }
  ]
}
```

- Servido por **`ProvasConsultaService.obter_movimentacoes`** (gate universal `Recurso.PROVAS`
  via `get_provas_consulta_service` — **mesmo escopo do detalhe**, §7). A prova é resolvida
  ANTES; fora do escopo / inexistente → o **mesmo 404 genérico** do C08 (anti-enumeração §11).
- **RLS:** as `movimentacoes` são escopadas pela policy `movimentacoes_select_por_prova_visivel`
  (espelha `provas` via `EXISTS`). O backend não contorna o escopo.
- **Sem N+1 (RNF-022):** uma consulta pelo histórico (índice `ix_movimentacoes_prova_id_created_at`)
  + **uma** ida ao projetor de nomes para todos os atores distintos.
- **Mínimo de requisições:** o detalhe já carregou o card; a timeline faz **1** chamada extra.

### 3.1 Responsável de cada etapa (DP-2b) — `private.nomes_de_usuarios`

O ator de uma movimentação pode ser de **qualquer setor** (3Studio encaminha, Motorista
transporta, Clicheria recebe, Vendedor aprova). A RLS de `usuarios` (C05) só deixa admin/self
lerem outras linhas — então um Vendedor não resolveria, por JOIN, o nome do 3Studio que moveu
a prova dele. A migration **`0017`** cria **`private.nomes_de_usuarios(uuid[]) → (id, nome)`**,
generalizando `nomes_de_vendedores` (0010/0011) para qualquer setor:

- **SECURITY DEFINER** no schema **`private`** (não exposto pela Data API — sem vetor de RPC),
  `SET search_path = ''` + corpo schema-qualificado (blindagem W1-A-004);
- **defesa em profundidade:** o corpo **re-aplica o escopo do chamador** — só resolve nomes de
  atores em provas **visíveis** a ele (espelha `provas_select_*` via os helpers `app_*`; o
  conjunto do Motorista espelha o ampliado da 0015). Drift: este predicado acompanha a RLS de
  `provas`.
- `authenticated` recebe USAGE no schema + EXECUTE; `anon`, nada. Espelho em
  `migrations/rls/nomes_de_usuarios.sql`.

### 3.2 Assinatura (DP-2c) — só o selo, sem a imagem

`tem_assinatura = assinatura_ref IS NOT NULL` é o **selo** "✓ Assinada" exibido na etapa.
**Não há proxy de imagem nesta entrega** (decisão do dono): a imagem `bytea` (C12) **nunca
trafega** na timeline. Um visualizador de assinatura pode ser adicionado depois reusando o
padrão de proxy-streaming do C08.

## 4. Agrupamento por ciclo (DP-3) — sem retroação

A coluna **`movimentacoes.ciclo`** **já existe** (migration `0015`, carimbada com
`prova.ciclo_atual` no instante da transição — `transicoes.py`): **nenhuma retroação** foi
necessária (o prompt previa o caso "se o C11 ainda não carimba" — não é o caso).

`construirTimeline` (`apps/web/src/lib/provas/timeline.ts`, **pura**) agrupa por `ciclo`
(distintos no histórico ∪ `ciclo_atual`, crescente). Cada ciclo renderiza o **esqueleto** com
o histórico daquele ciclo sobreposto; havendo **mais de um**, a UI mostra um **separador
"Ciclo N"**. Como o C15 (reinício) ainda não existe, os dados atuais são todos `ciclo=1`; o
componente já está pronto para múltiplos ciclos (testado com fixture reiniciada).

> **Nota para o C15:** ao reiniciar, carimbe a movimentação `reiniciar_ciclo` com o
> `ciclo_atual` **pré-incremento** (o reinício pertence ao ciclo que se encerra) e só então
> incremente `provas.ciclo_atual`. Assim o evento de reinício cai no fim do ciclo anterior na
> timeline (a posição mais legível). O componente tolera o contrário, mas esta é a leitura ideal.

## 5. Modelo de renderização (`construirTimeline`)

Para cada ciclo, produz uma lista de **nós**:

- **`etapa`** — um estado do esqueleto, com `status`:
  - `percorrido` (alcançado por uma movimentação de avanço, ou `criada`);
  - `atual` (no ciclo corrente, `estado === estado_atual`) — recebe o destaque animado;
  - `futuro` (no ciclo corrente, ainda não alcançado);
  - `nao_percorrido` (ciclo passado que reprovou antes de chegar aqui).
  - Flags `laminacao` (`ESTADOS_LAMINACAO`) e `motorista` (`ESTADOS_MOTORISTA`) para a
    indicação visual diferenciada; o **contexto da travessia** (ida/volta/entrega) já vem no
    **rótulo** do estado (C07: "Com motorista — ida laminação" etc.).
- **`reprovacao` / `cancelamento` / `reinicio`** — eventos especiais, encaixados pela
  **origem** (a reprovação aparece logo após a etapa de decisão do Vendedor; reinício/
  cancelamento de origem fora do caminho vão ao fim do ciclo). Carregam `motivo` (em destaque)
  e o flag `atual` quando são o estado corrente da prova.

A função é **pura e testada** (`timeline.test.ts`): a UI só pinta o resultado.

## 6. Animação (RF-026 / RNF-010) — contida

- **Revelação progressiva:** cada nó entra com `opacity` + `x` (translate), com `delay`
  escalonado (teto em ~14 nós para rotas longas não arrastarem) — **só transform/opacity** (GPU).
- **Etapa atual:** anel pulsante em CSS (`transform`/`opacity`).
- **`prefers-reduced-motion`:** `useReducedMotion` zera as durações/atrasos (revelação
  **instantânea**) e a media-query desliga o anel/skeleton.

Estilo em CSS Modules (`ProofTimeline.module.css`), na linguagem da plataforma (escala `--u`,
tokens `--app-*`/`--auth-*`); **responsivo** (vertical, recomposto no mobile ≤ 767px).

## 7. Acesso (§7)

A timeline é **embutida no detalhe** e segue **as mesmas regras**: 3Studio/Clicheria/Admin
veem todas, Vendedor as suas, Motorista as do seu escopo operacional — garantido pela **RLS de
`movimentacoes`** (C11). A borda usa o gate universal `Recurso.PROVAS`.

## 8. Arquivos

**Backend** — `domain/state_machine/machine.py` (`sequencia_canonica`, `ACOES_AVANCO`);
`application/provas.py` (`ProvasConsultaService.obter_movimentacoes`, `TimelineProva`,
`MovimentacaoComAtor`); `application/ports/movimentacoes_repository.py` +
`adapters/outbound/db/movimentacoes_repository.py` (`listar_por_prova`, `nomes_de_atores`);
`adapters/inbound/http/provas.py` (`TimelineOut`/`MovimentacaoOut` + endpoint);
migration `0017` + `migrations/rls/nomes_de_usuarios.sql`.

**Frontend** — `lib/api/timeline.ts` (tipos + fetch); `lib/provas/timeline.ts`
(`construirTimeline` + helpers); `app/(app)/provas/[id]/_components/ProofTimeline.tsx` +
`ProofTimeline.module.css`; integração em `prova-detalhe-view.tsx`.

## 9. Testes

```bash
# Backend (@db usa a mesma TEST_DATABASE_URL das demais waves)
uv run pytest tests/unit/test_state_machine.py tests/unit/test_provas_timeline.py \
  tests/integration/test_provas_timeline_endpoints.py \
  tests/integration/test_rls_nomes_de_usuarios.py

# Frontend
pnpm test   # inclui lib/provas/timeline.test.ts e ProofTimeline.test.tsx
```

## 10. Checklist dos critérios de aceitação (§6)

- [x] Renderiza as **4 rotas** com o número correto de etapas; **badge da rota** no topo.
- [x] Cada etapa percorrida mostra **responsável + data/hora**; a **atual é destacada** (animada).
- [x] **Laminação** diferenciada; **travessias de motorista** com o **contexto** (ida/volta/entrega).
- [x] **Reprovação** com **motivo em destaque**; **múltiplos ciclos** com **separador** (DP-3).
- [x] Acesso respeita a **Matriz §7** (mesmo escopo do detalhe; RLS de `movimentacoes`).
- [x] Revelação respeita **`prefers-reduced-motion`**; caminho canônico **não duplica** a §6 (DP-1); responsivo.
- [x] Estados de **loading/erro/vazio**; a falha do histórico **não derruba** o detalhe.
- [x] **Stateless**; sem segredos versionados; **R$ 0**; `ruff`/`mypy`/`pytest`/`pnpm lint`/`build` verdes; migration `0017` up/down limpa.
