"use client";

/**
 * Aba Clicheria (W5-C17 · §0.2) — ótica de quem recebe a prova no fim do fluxo
 * (perspectiva "rumo à clicheria" — DP-3): tempo médio aguardando (envio →
 * recebimento), recebidas no período, em trânsito agora, origens (rotas distintas),
 * distribuição por rota de origem (com empty state) e o fluxo de ciclo.
 */
import { ROTA_LABELS } from "@/lib/provas/rota-labels";
import { fetchRelatorioClicheria, type FiltrosRelatorio } from "@/lib/api/relatorios";
import { fmtDec } from "@/lib/relatorios/format";

import styles from "../relatorios.module.css";
import { EstadoErro, GridSkeleton, useRelatorio } from "./use-relatorio";
import { ListaBarra, StatCard } from "./widgets";

export function ClicheriaTab({ filtros, chave }: { filtros: FiltrosRelatorio; chave: string }) {
  const { dados, carregando, erro, recarregar } = useRelatorio(
    (s) => fetchRelatorioClicheria(filtros, s),
    `clicheria|${chave}`,
  );

  if (erro) return <EstadoErro tipo={erro} onRetry={recarregar} />;
  if (carregando || dados === null) return <GridSkeleton cards={4} />;

  const totalRecebidas = dados.distribuicao_origem.reduce((s, f) => s + f.total, 0);

  return (
    <div className={styles.grid}>
      <StatCard
        rotulo="Tempo médio aguardando"
        valor={fmtDec(dados.tempo_medio_aguardando_horas)}
        unidade="h"
        sub="envio → recebimento"
        escuro
      />
      <StatCard rotulo="Recebidas no período" valor={dados.recebidas_no_periodo} />
      <StatCard rotulo="Em trânsito agora" valor={dados.em_transito_agora} />
      <StatCard rotulo="Origens" valor={dados.origens} sub="rotas distintas" />

      <div className={`${styles.card} ${styles.span2}`}>
        <span className={styles.cardRotulo}>
          Provas recebidas por rota de origem · distribuição
        </span>
        {totalRecebidas === 0 ? (
          <p className={styles.vazio}>
            Nenhuma prova recebida no período.
            <br />
            <span className={styles.vazioSub}>Sem dados para distribuir entre as rotas.</span>
          </p>
        ) : (
          <ListaBarra
            ariaLabel="Provas recebidas por rota de origem"
            itens={dados.distribuicao_origem.map((f) => ({
              chave: f.rota,
              rotulo: ROTA_LABELS[f.rota],
              valor: f.total,
            }))}
          />
        )}
      </div>

      <div className={`${styles.card} ${styles.span2}`}>
        <span className={styles.cardRotulo}>Fluxo de ciclo · estado atual</span>
        <ul className={styles.lista} aria-label="Fluxo de ciclo">
          <li className={styles.linhaLista}>
            <span className={styles.ordinal}>○</span>
            <span className={styles.linhaListaRotulo}>Recebidas</span>
            <span className={styles.linhaListaValor}>{dados.recebidas_no_periodo}</span>
          </li>
          <li className={styles.linhaLista}>
            <span className={styles.ordinal}>○</span>
            <span className={styles.linhaListaRotulo}>Em trânsito</span>
            <span className={styles.linhaListaValor}>{dados.em_transito_agora}</span>
          </li>
          <li className={styles.linhaLista}>
            <span className={styles.ordinal}>○</span>
            <span className={styles.linhaListaRotulo}>Total origens</span>
            <span className={styles.linhaListaValor}>{dados.origens}</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
