# Auditoria dedicada — C17 · Relatórios gerenciais (núcleo / métricas)

> **Data:** 2026-06-19 · **Contexto:** insumo principal do fechamento da Wave 5 (`AUDITORIA-WAVE-5.md` F-01 — relatório ausente ⇒ NO-GO automático). Produzida na **remediação da Wave 5**.
> **Método:** *executar, não confiar* — **recomputação independente** de cada fórmula (DP-3/ADR-088) contra a fixture conhecida `ctx` de `tests/integration/test_relatorios_endpoints.py`, lendo o SQL linha a linha, com **dois passes independentes** (workflow adversarial de 12 áreas + crítico de completude) **mais** a recomputação do auditor humano e a suíte @db verde. Read-only sobre o código de produção (nenhuma fórmula foi alterada).
> **Escopo:** as 4 abas (Geral/3Studio/Vendedores/Clicheria), a base temporal (horas úteis), a população base/filtros, o CSV, o acesso (403/401), a segurança de SQL e o N+1. **Não** cobre a fidelidade visual (ADR-094, validada com o dono).

---

## 1. Sumário executivo

# ✅ VEREDITO DO C17: **GO** (após a correção do achado M-1, fechada nesta remediação)

| Severidade | Qtd. | Bloqueia GO? |
| --- | --- | --- |
| 🔴 Crítico | 0 | — |
| 🟠 Alto | 0 | — |
| 🟡 Médio | **1** (M-1, **RESOLVIDO**) | Sim, até resolver |
| ⚪ Baixo | 3 (B-1/B-2/B-3, informativos) | Não |

**As fórmulas estão corretas.** A recomputação independente, métrica por métrica, contra o cenário seedado da fixture `ctx` confere com a especificação confirmada (DP-3/ADR-088) e com o que o código produz. Nenhum erro de métrica, de acesso ou de segurança de SQL sobreviveu ao escrutínio adversarial. O reuso da regra de "Atrasada" do C16 é **verbatim** (mesmo módulo `atraso_sql.py`), então o número compartilhado bate nos dois lados (provado também por teste — ver `test_integracao_atrasadas_c16_c17.py`).

**O único bloqueador era um defeito de TESTE, não de métrica (M-1):** a fixture `ctx` datava as movimentações das provas **ativas** (aprovada/reprovada) em **data fixa** (`2026-06-15`), enquanto a regra de "Atrasada" usa `now()`. Cerca de 48 horas úteis depois (≈ sexta 19/06 15:00), essas provas ativas passariam a contar como "atrasadas" e quebrariam três asserções — um **time-bomb** de relógio que não aparecia nas execuções anteriores (todas antes do limiar). **Corrigido nesta remediação** (âncora de tempo recente e robusta) + **guard de regressão determinístico**.

---

## 2. Achados

### 🟡 M-1 (Médio) — *time-bomb* de relógio na fixture `ctx` → suíte fica vermelha por avanço do tempo · **RESOLVIDO**

- **Evidência (reproduzível):** consulta direta ao banco em 2026-06-19 10:21 (-03):
  ```
  private.horas_uteis_entre('2026-06-15 11:00-03', now())  = 43.36   # limiar = 48
  private.instante_limite_atraso(now(), 48)                = 2026-06-12 17:21 (-03)
  ```
  As provas `P_aprov` (`aprovada_vendedor`) e `P_reprov` (`reprovada_vendedor`) tinham **último evento em 2026-06-15 11:00** (datas fixas `_brt(15,·)`). Ambas são **ativas** (não terminais — `atraso_sql.ESTADOS_TERMINAIS` = só `recebida_clicheria`/`cancelada`). Faltavam ~4,6 h úteis para cruzar o limiar de 48h → a partir de **≈ sexta 19/06 15:00** elas passariam a ser "atrasadas".
- **Impacto:** quebraria `test_geral_atrasadas_consistente_com_c16` (`len==1`→3), `test_vendedores_contagens` (`atrasadas_total==1`→3) e `test_geral_metricas_por_vendedor` (Mário `atrasadas==0`→2) — **suíte vermelha determinística por relógio** (viola a DoD §8 "suíte verde" e o critério de GO). **Não** é erro de fórmula: o predicado de atraso está correto; a *fixture* é que era frágil.
- **Causa raiz:** datas de evento FIXAS (`2026-06-15`) em provas ativas, combinadas com a regra de atraso ancorada em `now()`.
- **Correção (causa raiz):** `tests/integration/test_relatorios_endpoints.py` — nova âncora `_ancora_comercial(now)` devolve um **dia útil recente** (corrente após as 14h locais, senão o anterior, recuando sobre o fim de semana); os eventos passam a `_em(base, 9/11/13)`. Preserva os *gaps* exatos em horas úteis (09→11 = 2h; 09→13 = 4h) e garante que as provas ativas fiquem a **< 48h úteis** de `now()` — **nunca** "atrasadas" por relógio. As datas fixas `_brt(·)` seguem só nos testes da função pura `horas_uteis_entre` (que não dependem de `now()`).
- **Regressão (prova do fechamento):** `test_ancora_comercial_mantem_eventos_recentes_e_no_passado` (parametrizado seg/sex/sáb/dom) — determinístico, **não** depende do relógio; falha se as datas fixas reaparecerem.
- **Status:** **RESOLVIDO** (suíte verde re-rodada; ver §5).

### ⚪ B-1 (Baixo, informativo) — `tempo_ate_primeira_mov_horas` não é validado pela fixture

- **Evidência:** no `ctx`, as provas com movimentação têm `created_at = now()` (padrão do seed), mas a 1ª movimentação é datada no passado (âncora) → `horas_uteis_entre(created_at, min(mov))` com `fim <= inicio` cai na guarda defensiva → **0**. `test_studio_eventos_e_motivos` só checa `is not None`, então a **fórmula** (`created_at → 1ª mov`) não é exercida com um valor significativo.
- **Impacto:** cobertura, não correção. A fórmula está correta por recomputação (ver §3). Recomendação: um seed dedicado com `created_at` anterior à 1ª mov (não feito aqui para não mexer no `created_at` da fixture, do qual `test_filtro_periodo_exclui_provas_antigas` depende).

### ⚪ B-2 (Baixo, por design — confirmado em ADR-091) — eventos recortados por `created_at` da prova, não pela data do evento

- **Evidência:** em 3Studio, `devolvidas`/`cancelamentos`/`reinicios` contam `movimentacoes m JOIN provas WHERE (where_base) AND m.acao=…`; o `where_base` filtra `provas.created_at` no período, **não** a data da própria movimentação. Uma reprovação/cancelamento conta no período se a **prova** nasceu na janela, independentemente de **quando** o evento ocorreu.
- **Impacto:** **é a decisão documentada e confirmada pelo dono (ADR-091):** "TODA métrica da aba usa a MESMA população (provas criadas na janela); eventos são contados sobre as movimentações DAS provas da base." Consistente e intencional — **não é defeito**. Registrado para evitar releitura como bug numa auditoria futura.

### ⚪ B-3 (Baixo, informativo) — `media_diaria` e a série `volume` sem asserção @db

- **Evidência:** `dias_no_periodo` é testado isolado (unit), mas a divisão `provas_criadas / dias` + arredondamento (2 casas) e a estrutura da série `volume` não têm asserção end-to-end. Recomputação manual confere (§3). Recomendação: asserção @db opcional (sem período → `dias=30`).

---

## 3. Recomputação métrica por métrica (à mão, vs. a fixture `ctx`)

Cenário `ctx` (após M-1): admin (Monica, 3Studio) + Mário (vendedor/filial) + André (vendedor/matriz). 6 provas criadas hoje (P_atrasada criada há 30 dias). Eventos no dia útil-âncora: chegada 09:00, aprovação/reprovação 11:00, recebimento 13:00.

| # | Métrica | Cálculo à mão (fixture) | Esperado | Código produz | Bate |
| --- | --- | --- | --- | --- | --- |
| 1 | Tempo médio de aprovação | única aprovação: chegada 09:00 → aprov 11:00 = **2h úteis**; `max(chegada)<=aprov` cobre reinícios | 2.0 | `avg(horas_uteis_entre(...))` (`relatorios_repository.py:53,193`) | ✅ |
| 2 | Taxa de reprovação | 1 aprov + 1 reprov → 1/2 = **50%**; denom 0 → `None`; `_taxa(10,0)=0.0` | 50.0 | `_taxa` (`:369`) | ✅ |
| 3 | Distribuição por rota | matriz 3, lam_matriz 1, filial 2, lam_filial 0 → soma **6 = total** | 100% | `_zerar_rotas` + 4 subqueries no mesmo `where` (`:219`) | ✅ |
| 4 | Atrasadas (Geral/Vendedores) | só P_atrasada (ativa, parada 30d); terminais e ativas-recentes excluídas → **1** | 1 | `SQL_PREDICADO_ATRASADA` **verbatim** do C16 (`:28,145,208`) | ✅ |
| 5 | Ativas: aguardando vendedor / reprovada | retirada(P_atrasada) → 1 / reprovada(P_reprov) → 1 | 1 / 1 | `:180,182` | ✅ |
| 6 | 3Studio — provas_criadas / devolvidas / cancelamentos / reinícios / reprov.aguardando | 6 / 1 (reprovar) / 1 (cancelar) / 0 / 1 | 6/1/1/0/1 | `:247-261` | ✅ |
| 7 | 3Studio — top motivos | 1× "Apenas Teste" (`acao=cancelar`, motivo não-vazio, LIMIT 10) | [{Apenas Teste,1}] | `:264` | ✅ |
| 8 | Clicheria — tempo médio aguardando | envio 09:00 → recebimento 13:00 = **4h úteis** (max destino→max destino) | 4.0 | `:334` | ✅ |
| 9 | Clicheria — recebidas / em_transito / origens | 1 / 1 / 1 (só lam_matriz entre recebidas) | 1/1/1 | `:327-333` | ✅ |
| 10 | Vendedores — filial/matriz/ativos | cadastro: Mário(filial)=1, André(matriz)=1; ativos=2 (ambos com prova) | 1/1/2 | `:295,303` | ✅ |
| 11 | Filtros | rota multi (matriz+lam_matriz→4); vendedor; status; período (`created_at`) | conforme | `_clausula_base` (`:84`) | ✅ |
| 12 | CSV | BOM (`utf-8-sig`) + `;` + `\r\n`; vírgula decimal; "—" p/ None; rótulos de UI | conforme | `application/relatorios.py:228` | ✅ |
| 13 | Acesso | não-admin → 403 nas 4 abas E no `/exportar`; sem token → 401 | 403/401 | gate `Recurso.RELATORIOS` no service | ✅ |
| 14 | Segurança SQL | só enum validado interpolado; busca/datas/uuid como bind | sem injeção | `_enum_in`/`:94,105,108`; `# noqa: S608` justificado | ✅ |
| 15 | N+1 | cada aba = poucas consultas SET-BASED; por-vendedor = 1 query (CTEs vol/ev/atr) | sem N+1 | `_metricas_por_vendedor` (`:127`) | ✅ |

---

## 4. Cobertura e método (transparência sobre a execução)

- **Dois passes independentes + síntese.** Um workflow adversarial cobriu 12 áreas (auditor + cross-check independente por área) e um crítico de completude. **Limitação honesta:** os 24 agentes por-área **falharam ao emitir a saída estruturada** (retornaram `null` por erro de tooling), mas a recomputação **foi feita** — registrada nas transcrições (ex.: o auditor da área "Atrasadas" foi quem primeiro levantou o *time-bomb* do M-1) e **sintetizada pelo crítico**, que recomputou cada métrica do zero e concluiu **GO sem Crítico/Alto**. O auditor humano refez a recomputação (tabela §3) e **confirmou empiricamente** o M-1 (consulta ao banco) antes de corrigir.
- **Reuso do C16 (dois lados).** `relatorios_repository.py` e `dashboard_repository.py` importam o MESMO `SQL_PREDICADO_ATRASADA`/`SQL_ULTIMO_EVENTO` de `atraso_sql.py` (verbatim); `private.instante_limite_atraso` (0020) e `private.horas_uteis_entre` (0021) são a mesma janela comercial. Provado por `test_integracao_atrasadas_c16_c17.py` (mesma fixture → mesmo número nos dois lados).

---

## 5. Evidência de execução

| Comando | Resultado |
| --- | --- |
| `pytest tests/unit/test_relatorios.py tests/integration/test_relatorios_endpoints.py` (@db) | verde (inclui o novo guard determinístico do M-1 + as 2h/4h preservadas) |
| `pytest tests/integration/test_integracao_atrasadas_c16_c17.py` (@db) | verde — "Atrasadas" bate em `/dashboard`, `/relatorios/geral` e `/relatorios/vendedores` |
| `ruff check .` · `ruff format --check .` · `mypy` | verdes |
| suíte `api` completa (`REQUIRE_DB_TESTS=1`) | verde (ver `AUDITORIA-WAVE-5.md` §5 atualizado) |

---

## 6. Encaminhamento

**GO** para o núcleo do C17. O bloqueador (M-1) foi corrigido na causa raiz e blindado por teste. Os Baixos (B-1/B-3) são melhorias de profundidade de teste (opcionais); B-2 é decisão de design confirmada (ADR-091). Com este relatório existente e GO, o item F-01 do `AUDITORIA-WAVE-5.md` está sanado.
