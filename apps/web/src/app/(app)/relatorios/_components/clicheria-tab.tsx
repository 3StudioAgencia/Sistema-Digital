"use client";

import { AnimatedCounter } from "@/components/ui/animated-counter/AnimatedCounter";
import { fetchRelatorioClicheria, type FiltrosRelatorio } from "@/lib/api/relatorios";
import { ROTA_LABELS } from "@/lib/provas/rota-labels";
import { fracao } from "@/lib/relatorios/format";

import styles from "../relatorios.module.css";
import { VolumeBars } from "./charts";
import { EstadoErro, GridSkeleton, useRelatorio } from "./use-relatorio";

export function ClicheriaTab({ filtros, chave }: { filtros: FiltrosRelatorio; chave: string }) {
  const { dados, carregando, erro, recarregar } = useRelatorio(
    (s) => fetchRelatorioClicheria(filtros, s),
    `clicheria|${chave}`,
  );

  if (erro) return <EstadoErro tipo={erro} onRetry={recarregar} />;
  if (carregando || dados === null) return <GridSkeleton cards={4} />;

  const totalRecebidas = dados.distribuicao_origem.reduce((s, f) => s + f.total, 0);
  const rotas = [...dados.distribuicao_origem].sort((a, b) => b.total - a.total);
  const maxRota = Math.max(1, ...rotas.map((f) => f.total));

  const fluxo = [
    { rotulo: "Recebidas", valor: dados.recebidas_no_periodo },
    { rotulo: "Em trânsito", valor: dados.em_transito_agora },
    { rotulo: "Total origens", valor: dados.origens },
  ];
  const maxFluxo = Math.max(1, ...fluxo.map((f) => f.valor));

  return (
    <div className={styles.gridClicheria}>
      <div className={`${styles.card} ${styles.cardEscuro} ${styles.sSpan4} ${styles.cTempo}`}>
        <span className={styles.cardRotulo}>Tempo Médio Aguardando</span>
        <div className={styles.cTempoCorpo}>
          <span className={styles.totalNumero}>
            {dados.tempo_medio_aguardando_horas === null ? (
              "—"
            ) : (
              <AnimatedCounter value={Math.round(dados.tempo_medio_aguardando_horas)} />
            )}
            {dados.tempo_medio_aguardando_horas !== null && (
              <span className={styles.totalUnidade}>horas</span>
            )}
          </span>
          <VolumeBars dados={dados.volume} className={styles.cTempoBars} />
        </div>
      </div>

      <div className={`${styles.card} ${styles.sSpan3} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Recebidas no período</span>
        <span className={styles.metricValor}>{dados.recebidas_no_periodo}</span>
      </div>

      <div className={`${styles.card} ${styles.sSpan3} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Em trânsito</span>
        <span className={styles.metricValor}>{dados.em_transito_agora}</span>
      </div>

      <div className={`${styles.card} ${styles.sSpan2} ${styles.cMetric}`}>
        <span className={styles.cardRotulo}>Origens</span>
        <span className={styles.metricValor}>{dados.origens}</span>
      </div>

      <div className={`${styles.card} ${styles.sSpan6}`}>
        <span className={styles.cardRotulo}>Provas recebidas por rota de origem</span>
        {totalRecebidas === 0 ? (
          <p className={styles.vazio}>
            Nenhuma prova recebida no período.
            <br />
            <span className={styles.vazioSub}>Sem dados para distribuir entre as rotas.</span>
          </p>
        ) : (
          <ol className={styles.rankLista}>
            {rotas.map((f, i) => (
              <li key={f.rota} className={styles.rankItem}>
                <span className={styles.rankNum}>{String(i + 1).padStart(2, "0")}</span>
                <span className={styles.rankNome}>{ROTA_LABELS[f.rota]}</span>
                <span className={styles.rankBar} aria-hidden>
                  <span
                    className={styles.rankBarFill}
                    style={{ transform: `scaleX(${fracao(f.total, maxRota)})` }}
                  />
                </span>
                <span className={styles.rankValor}>{f.total}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className={`${styles.card} ${styles.sSpan6}`}>
        <span className={styles.cardRotulo}>Fluxo de ciclo</span>
        <ol className={styles.rankLista}>
          {fluxo.map((f, i) => (
            <li key={f.rotulo} className={styles.rankItem}>
              <span className={styles.rankNum}>{String(i + 1).padStart(2, "0")}</span>
              <span className={styles.rankNome}>{f.rotulo}</span>
              <span className={styles.rankBar} aria-hidden>
                <span
                  className={styles.rankBarFill}
                  style={{ transform: `scaleX(${fracao(f.valor, maxFluxo)})` }}
                />
              </span>
              <span className={styles.rankValor}>{f.valor}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
