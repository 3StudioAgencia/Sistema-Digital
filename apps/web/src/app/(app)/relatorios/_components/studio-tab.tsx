"use client";

import { AnimatedCounter } from "@/components/ui/animated-counter/AnimatedCounter";
import { fetchRelatorioStudio, type FiltrosRelatorio } from "@/lib/api/relatorios";
import { fmtDec, fracao } from "@/lib/relatorios/format";

import styles from "../relatorios.module.css";
import { VolumeBars } from "./charts";
import { EstadoErro, GridSkeleton, useRelatorio } from "./use-relatorio";

export function StudioTab({ filtros, chave }: { filtros: FiltrosRelatorio; chave: string }) {
  const { dados, carregando, erro, recarregar } = useRelatorio(
    (s) => fetchRelatorioStudio(filtros, s),
    `studio|${chave}`,
  );

  if (erro) return <EstadoErro tipo={erro} onRetry={recarregar} />;
  if (carregando || dados === null) return <GridSkeleton cards={6} />;

  const maxMotivo = Math.max(1, ...dados.top_motivos_cancelamento.map((m) => m.total));

  return (
    <div className={styles.gridStudio}>
      <div className={`${styles.card} ${styles.cardEscuro} ${styles.sSpan4} ${styles.cTotal}`}>
        <div className={styles.totalTopo}>
          <AnimatedCounter value={dados.provas_criadas} className={styles.totalNumero} />
          <span className={styles.totalRotulo}>Provas Criadas</span>
        </div>
        <VolumeBars dados={dados.volume} className={styles.totalBars} />
      </div>

      <div className={`${styles.card} ${styles.sSpan3} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Reinícios de ciclo</span>
        <span className={styles.metricValor}>{dados.reinicios_ciclo}</span>
      </div>

      <div className={`${styles.card} ${styles.sSpan3} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Devolvidas</span>
        <span className={styles.metricValor}>{dados.devolvidas}</span>
      </div>

      <div className={`${styles.card} ${styles.sSpan2} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Canceladas</span>
        <span className={`${styles.metricValor} ${styles.metricVermelho}`}>
          {dados.cancelamentos}
        </span>
      </div>

      <div className={`${styles.card} ${styles.sSpan4} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Reprov. aguardando</span>
        <span className={`${styles.metricValor} ${styles.metricVermelho}`}>
          {dados.reprovadas_aguardando}
        </span>
      </div>

      <div className={`${styles.card} ${styles.sSpan3} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Tempo até 1ª movimentação</span>
        <span className={styles.metricValor}>
          {fmtDec(dados.tempo_ate_primeira_mov_horas)}
          <span className={styles.metricUnidade}>horas</span>
        </span>
      </div>

      <div className={`${styles.card} ${styles.sSpan5}`}>
        <span className={styles.cardRotulo}>Top motivos de cancelamento</span>
        {dados.top_motivos_cancelamento.length === 0 ? (
          <p className={styles.vazio}>Nenhum cancelamento no período.</p>
        ) : (
          <ul className={styles.motivosLista} aria-label="Top motivos de cancelamento">
            {dados.top_motivos_cancelamento.map((m, i) => (
              <li key={`${i}-${m.motivo}`} className={styles.motivoItem}>
                <span className={styles.motivoNome}>{m.motivo}</span>
                <span className={styles.rankBar} aria-hidden>
                  <span
                    className={`${styles.rankBarFill} ${styles.rankBarFillVermelha}`}
                    style={{ transform: `scaleX(${fracao(m.total, maxMotivo)})` }}
                  />
                </span>
                <span className={styles.rankValor}>{m.total}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
