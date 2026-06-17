"use client";

/**
 * Aba 3Studio (W5-C17 · §0.2) — diagnóstico da operação do studio no período:
 * provas criadas (+ média diária), reinícios, devolvidas (=reprovações — DP-3),
 * cancelamentos, reprovadas aguardando, tempo até 1ª mov, e top motivos de
 * cancelamento (`movimentacoes.motivo` — DP-3).
 */
import { fetchRelatorioStudio, type FiltrosRelatorio } from "@/lib/api/relatorios";
import { fmtDec } from "@/lib/relatorios/format";

import styles from "../relatorios.module.css";
import { EstadoErro, GridSkeleton, useRelatorio } from "./use-relatorio";
import { ListaBarra, StatCard } from "./widgets";

export function StudioTab({ filtros, chave }: { filtros: FiltrosRelatorio; chave: string }) {
  const { dados, carregando, erro, recarregar } = useRelatorio(
    (s) => fetchRelatorioStudio(filtros, s),
    `studio|${chave}`,
  );

  if (erro) return <EstadoErro tipo={erro} onRetry={recarregar} />;
  if (carregando || dados === null) return <GridSkeleton cards={6} />;

  return (
    <div className={styles.grid}>
      <StatCard
        rotulo="Provas criadas"
        valor={dados.provas_criadas}
        sub={`${fmtDec(dados.media_diaria)} / dia (média)`}
        escuro
      />
      <StatCard rotulo="Reinícios ciclo" valor={dados.reinicios_ciclo} />
      <StatCard rotulo="Devolvidas" valor={dados.devolvidas} />

      <StatCard rotulo="Cancelamentos" valor={dados.cancelamentos} vermelho />
      <StatCard rotulo="Reprov. aguardando" valor={dados.reprovadas_aguardando} vermelho />
      <div className={styles.span2}>
        <StatCard
          rotulo="Tempo até 1ª mov."
          valor={fmtDec(dados.tempo_ate_primeira_mov_horas)}
          unidade="h"
        />
      </div>

      <div className={`${styles.card} ${styles.span4}`}>
        <span className={styles.cardRotulo}>
          Top motivos de cancelamento · diagnóstico do período
        </span>
        {dados.top_motivos_cancelamento.length === 0 ? (
          <p className={styles.vazio}>Nenhum cancelamento no período.</p>
        ) : (
          <ListaBarra
            ariaLabel="Top motivos de cancelamento"
            itens={dados.top_motivos_cancelamento.map((m, i) => ({
              chave: `${i}-${m.motivo}`,
              rotulo: m.motivo,
              valor: m.total,
              cor: "vermelha" as const,
            }))}
          />
        )}
      </div>
    </div>
  );
}
