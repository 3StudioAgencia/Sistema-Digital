"use client";

/**
 * Aba Geral (W5-C17 · §0.2) — fiel ao design (bento):
 * - Linha 1: Total geral (preto, largo, com barras de volume) · Tempo médio aprov.
 *   · Taxa reprovação · Rota (lista simples).
 * - Linha 2: Provas Ativas (donut) · Tempo médio por vendedor (ranking) · Vendedor
 *   com mais artes (preto, com barras).
 * - Abaixo: tabelas Métricas por Vendedor e Provas Atrasadas.
 * Os cards de ranking derivam de `metricas_por_vendedor` (sem ida extra — DP-3).
 */
import { AnimatedCounter } from "@/components/ui/animated-counter/AnimatedCounter";
import { fetchRelatorioGeral, type FiltrosRelatorio } from "@/lib/api/relatorios";
import { ROTA_LABELS } from "@/lib/provas/rota-labels";
import { rotuloStatus } from "@/lib/provas/status-labels";
import { fmtDec, fmtHoras, fmtInt, fmtPct, fracao, iniciais } from "@/lib/relatorios/format";

import styles from "../relatorios.module.css";
import { ProvasAtivasDonut, VolumeBars } from "./charts";
import { EstadoErro, GridSkeleton, useRelatorio } from "./use-relatorio";

const rotuloLocal = (l: string | null) =>
  l === "filial" ? "Filial" : l === "matriz" ? "Matriz" : "—";

export function GeralTab({ filtros, chave }: { filtros: FiltrosRelatorio; chave: string }) {
  const { dados, carregando, erro, recarregar } = useRelatorio(
    (s) => fetchRelatorioGeral(filtros, s),
    `geral|${chave}`,
  );

  if (erro) return <EstadoErro tipo={erro} onRetry={recarregar} />;
  if (carregando || dados === null) return <GridSkeleton cards={7} />;

  const tempoPorVendedor = dados.metricas_por_vendedor
    .filter((m) => m.tempo_medio_horas !== null)
    .sort((a, b) => (b.tempo_medio_horas ?? 0) - (a.tempo_medio_horas ?? 0));
  const top = dados.metricas_por_vendedor[0]; // já vem ordenado por volume desc
  // Máximos para as progress bars (tempo por vendedor; volume na tabela).
  const maxTempo = Math.max(1, ...tempoPorVendedor.map((m) => m.tempo_medio_horas ?? 0));
  const maxVolume = Math.max(1, ...dados.metricas_por_vendedor.map((m) => m.volume));
  const plural = (n: number, s: string, p: string) => `${n} ${n === 1 ? s : p}`;

  return (
    <div className={styles.gridGeral}>
      {/* Total geral (preto, largo, com barras de volume) */}
      <div className={`${styles.card} ${styles.cardEscuro} ${styles.aTotal} ${styles.cTotal}`}>
        <div className={styles.totalTopo}>
          <AnimatedCounter value={dados.total_geral} className={styles.totalNumero} />
          <span className={styles.totalRotulo}>Total geral</span>
        </div>
        <VolumeBars dados={dados.volume} className={styles.totalBars} />
      </div>

      {/* Tempo médio aprov. */}
      <div className={`${styles.card} ${styles.aTempo} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Tempo médio aprov.</span>
        <span className={styles.metricValor}>
          {fmtDec(dados.tempo_medio_aprovacao_horas)}
          <span className={styles.metricUnidade}>horas</span>
        </span>
      </div>

      {/* Taxa reprovação */}
      <div className={`${styles.card} ${styles.aTaxa} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Taxa reprovação</span>
        <span className={`${styles.metricValor} ${styles.metricVermelho}`}>
          {fmtDec(dados.taxa_reprovacao)}
          <span className={styles.metricUnidade}>%</span>
        </span>
      </div>

      {/* Rota (lista simples, sem barras) */}
      <div className={`${styles.card} ${styles.aRota} ${styles.cRota}`}>
        <span className={styles.cardRotulo}>Rota</span>
        <ul className={styles.rotaLista}>
          {dados.distribuicao_rota.map((f) => (
            <li key={f.rota} className={styles.rotaItem}>
              <span>{ROTA_LABELS[f.rota]}</span>
              <span className={styles.rotaValor}>{f.total}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Provas Ativas (donut + legenda) */}
      <div className={`${styles.card} ${styles.aAtivas} ${styles.cAtivas}`}>
        <span className={styles.cardRotulo}>Provas Ativas</span>
        <ProvasAtivasDonut
          aguardando={dados.ativas_aguardando_vendedor}
          reprovadas={dados.ativas_reprovadas}
        />
      </div>

      {/* Tempo médio de aprovação por vendedor (ranking com linha conectora) */}
      <div className={`${styles.card} ${styles.aVend}`}>
        <span className={styles.cardRotulo}>Tempo médio de aprovação por vendedor</span>
        {tempoPorVendedor.length === 0 ? (
          <p className={styles.vazio}>Nenhuma aprovação no período.</p>
        ) : (
          <ol className={styles.rankLista}>
            {tempoPorVendedor.map((m, i) => (
              <li key={m.vendedor_id} className={styles.rankItem}>
                <span className={styles.rankNum}>{String(i + 1).padStart(2, "0")}</span>
                <span className={styles.rankNome}>{m.vendedor_nome ?? "—"}</span>
                <span className={styles.rankBar} aria-hidden>
                  <span
                    className={styles.rankBarFill}
                    style={{ transform: `scaleX(${fracao(m.tempo_medio_horas ?? 0, maxTempo)})` }}
                  />
                </span>
                <span className={styles.rankValor}>{fmtHoras(m.tempo_medio_horas)}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      {/* Vendedor com mais artes (preto, com barras) */}
      <div className={`${styles.card} ${styles.cardEscuro} ${styles.aMais} ${styles.cMais}`}>
        <span className={styles.cardRotulo}>Vendedor com mais artes</span>
        <span className={styles.maisNome}>{top?.vendedor_nome ?? "—"}</span>
        <AnimatedCounter value={top ? top.volume : 0} className={styles.maisNumero} />
        <VolumeBars dados={dados.volume} className={styles.maisBars} />
      </div>

      {/* Métricas por Vendedor (ranking detalhado) */}
      <div className={`${styles.card} ${styles.aMetricas}`}>
        <div className={styles.tabelaCabecalho}>
          <div>
            <span className={styles.tabelaTitulo}>Métricas por Vendedor</span>
            <span className={styles.tabelaSub}>Ranking detalhado</span>
          </div>
          <span className={styles.tabelaCount}>
            {plural(dados.metricas_por_vendedor.length, "vendedor", "vendedores")}
          </span>
        </div>
        {dados.metricas_por_vendedor.length === 0 ? (
          <p className={styles.vazio}>Nenhuma prova no período.</p>
        ) : (
          <div className={styles.scrollTabela}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Vendedor</th>
                  <th>Local</th>
                  <th>Volume</th>
                  <th className={styles.num}>Aprov.</th>
                  <th className={styles.num}>Reprov.</th>
                  <th className={styles.num}>Tempo</th>
                </tr>
              </thead>
              <tbody>
                {dados.metricas_por_vendedor.map((m, i) => (
                  <tr key={m.vendedor_id}>
                    <td>
                      <span className={styles.rankCelula}>
                        {i === 0 ? <span className={styles.marcador} aria-hidden /> : null}
                        <span className={styles.ordinal}>{String(i + 1).padStart(2, "0")}</span>
                      </span>
                    </td>
                    <td>
                      <span className={styles.avatarNome}>
                        <span className={styles.avatar} aria-hidden>
                          {iniciais(m.vendedor_nome)}
                        </span>
                        {m.vendedor_nome ?? "—"}
                      </span>
                    </td>
                    <td>
                      <span className={styles.localPill}>{rotuloLocal(m.localizacao)}</span>
                    </td>
                    <td>
                      <span className={styles.volCell}>
                        <span className={styles.volBar} aria-hidden>
                          <span
                            className={styles.volFill}
                            style={{ transform: `scaleX(${fracao(m.volume, maxVolume)})` }}
                          />
                        </span>
                        <span className={styles.volNum}>{fmtInt(m.volume)}</span>
                      </span>
                    </td>
                    <td className={styles.num}>{fmtInt(m.aprovadas)}</td>
                    <td className={styles.num}>{fmtPct(m.taxa_reprovacao)}</td>
                    <td className={styles.num}>{fmtHoras(m.tempo_medio_horas)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Provas Atrasadas (aguardando ação) */}
      <div className={`${styles.card} ${styles.aAtrasadas}`}>
        <div className={styles.tabelaCabecalho}>
          <div>
            <span className={styles.tabelaTitulo}>Provas Atrasadas</span>
            <span className={styles.tabelaSub}>Aguardando ação</span>
          </div>
          <span className={styles.tabelaCount}>
            {plural(dados.provas_atrasadas.length, "prova", "provas")}
          </span>
        </div>
        {dados.provas_atrasadas.length === 0 ? (
          <p className={styles.vazio}>Nenhuma prova atrasada no período.</p>
        ) : (
          <div className={styles.scrollTabela}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Prova</th>
                  <th>Vendedor</th>
                  <th>Status</th>
                  <th className={styles.num}>Atraso</th>
                </tr>
              </thead>
              <tbody>
                {dados.provas_atrasadas.map((p, i) => (
                  <tr key={p.id}>
                    <td className={styles.ordinal}>{String(i + 1).padStart(2, "0")}</td>
                    <td>
                      {p.nome}
                      <br />
                      <span className={styles.cardSub}>
                        {p.requerimento} · {p.cliente}
                      </span>
                    </td>
                    <td>
                      <span className={styles.avatarNome}>
                        <span className={styles.avatar} aria-hidden>
                          {iniciais(p.vendedor_nome)}
                        </span>
                        {p.vendedor_nome ?? "—"}
                      </span>
                    </td>
                    <td>
                      <span className={styles.statusPill}>{rotuloStatus(p.status)}</span>
                    </td>
                    <td className={`${styles.num} ${styles.vermelho}`}>
                      {fmtHoras(p.atraso_horas)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
