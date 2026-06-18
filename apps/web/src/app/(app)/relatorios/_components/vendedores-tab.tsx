"use client";

/**
 * Aba Vendedores (W5-C17 · §0.2) — fiel ao design (bento):
 * - Linha 1: Provas Criadas (preto, com gráfico de volume) · Ranking por volume
 *   (lista ranqueada, larga).
 * - Abaixo: Detalhamento (tabela: Vendedor · Local · Aprovação · Reprovação ·
 *   Tempo · Atrasadas).
 * Ranking e Detalhamento derivam de `por_vendedor` (sem ida extra — DP-3). Aprov.%
 * = 100 − taxa de reprovação (ambas sobre as decisões do vendedor).
 */
import { AnimatedCounter } from "@/components/ui/animated-counter/AnimatedCounter";
import { fetchRelatorioVendedores, type FiltrosRelatorio } from "@/lib/api/relatorios";
import { fmtHoras, fmtInt, fmtPct, fracao, iniciais } from "@/lib/relatorios/format";

import styles from "../relatorios.module.css";
import { VolumeBars } from "./charts";
import { EstadoErro, GridSkeleton, useRelatorio } from "./use-relatorio";

const rotuloLocal = (l: string | null) =>
  l === "filial" ? "Filial" : l === "matriz" ? "Matriz" : "—";

/** Taxa de aprovação = 100 − taxa de reprovação (ambas sobre as decisões). */
function taxaAprovacao(taxaReprovacao: number | null): number | null {
  return taxaReprovacao === null ? null : Math.round((100 - taxaReprovacao) * 10) / 10;
}

export function VendedoresTab({ filtros, chave }: { filtros: FiltrosRelatorio; chave: string }) {
  const { dados, carregando, erro, recarregar } = useRelatorio(
    (s) => fetchRelatorioVendedores(filtros, s),
    `vendedores|${chave}`,
  );

  if (erro) return <EstadoErro tipo={erro} onRetry={recarregar} />;
  if (carregando || dados === null) return <GridSkeleton cards={3} />;

  const ranking = [...dados.por_vendedor].sort((a, b) => b.volume - a.volume);
  const maxVolume = Math.max(1, ...ranking.map((m) => m.volume));

  return (
    <div className={styles.gridVendedores}>
      {/* Provas Criadas (preto, com gráfico de volume) */}
      <div className={`${styles.card} ${styles.cardEscuro} ${styles.sSpan4} ${styles.cTotal}`}>
        <div className={styles.totalTopo}>
          <AnimatedCounter value={dados.provas_criadas} className={styles.totalNumero} />
          <span className={styles.totalRotulo}>Provas Criadas</span>
        </div>
        <VolumeBars dados={dados.volume} className={styles.totalBars} />
      </div>

      {/* Ranking por volume (lista ranqueada com linha conectora) */}
      <div className={`${styles.card} ${styles.sSpan8}`}>
        <span className={styles.cardRotulo}>Ranking por volume</span>
        {ranking.length === 0 ? (
          <p className={styles.vazio}>Nenhum vendedor com provas no período.</p>
        ) : (
          <ol className={styles.rankLista}>
            {ranking.map((m, i) => (
              <li key={m.vendedor_id} className={styles.rankItem}>
                <span className={styles.rankNum}>{String(i + 1).padStart(2, "0")}</span>
                <span className={styles.rankNome}>{m.vendedor_nome ?? "—"}</span>
                <span className={styles.rankBar} aria-hidden>
                  <span
                    className={styles.rankBarFill}
                    style={{ transform: `scaleX(${fracao(m.volume, maxVolume)})` }}
                  />
                </span>
                <span className={styles.rankValor}>{fmtInt(m.volume)}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      {/* Detalhamento (tabela completa) */}
      <div className={`${styles.card} ${styles.sSpan12}`}>
        <span className={styles.cardRotulo}>Detalhamento</span>
        {dados.por_vendedor.length === 0 ? (
          <p className={styles.vazio}>Nenhum vendedor com provas no período.</p>
        ) : (
          <div className={styles.scrollTabela}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th>Vendedor</th>
                  <th>Local</th>
                  <th>Aprovação</th>
                  <th>Reprovação</th>
                  <th>Tempo</th>
                  <th>Atrasadas</th>
                </tr>
              </thead>
              <tbody>
                {dados.por_vendedor.map((m) => (
                  <tr key={m.vendedor_id}>
                    <td>
                      <span className={styles.avatarNome}>
                        <span className={styles.avatar} aria-hidden>
                          {iniciais(m.vendedor_nome)}
                        </span>
                        {m.vendedor_nome ?? "—"}
                      </span>
                    </td>
                    <td>{rotuloLocal(m.localizacao)}</td>
                    <td className={styles.verde}>{fmtPct(taxaAprovacao(m.taxa_reprovacao))}</td>
                    <td className={styles.vermelho}>{fmtPct(m.taxa_reprovacao)}</td>
                    <td>{fmtHoras(m.tempo_medio_horas)}</td>
                    <td>{m.atrasadas}</td>
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
