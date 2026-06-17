"use client";

/**
 * Aba Vendedores (W5-C17 · §0.2) — contagem de vendedores por localização, ranking
 * por volume e detalhamento (aprovação · reprovação · tempo · atrasadas) por
 * vendedor. Aprov.% deriva da taxa de reprovação (100 − taxa) quando há decisões.
 */
import { fetchRelatorioVendedores, type FiltrosRelatorio } from "@/lib/api/relatorios";
import { fmtHoras, fmtPct, iniciais } from "@/lib/relatorios/format";

import styles from "../relatorios.module.css";
import { EstadoErro, GridSkeleton, useRelatorio } from "./use-relatorio";
import { ListaBarra } from "./widgets";

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
  if (carregando || dados === null) return <GridSkeleton cards={4} />;

  const ranking = [...dados.por_vendedor]
    .sort((a, b) => b.volume - a.volume)
    .map((m) => ({ chave: m.vendedor_id, rotulo: m.vendedor_nome ?? "—", valor: m.volume }));

  return (
    <div className={styles.grid}>
      <div className={`${styles.card} ${styles.cardEscuro} ${styles.span2}`}>
        <span className={styles.cardRotulo}>Vendedores Filial</span>
        <span className={styles.cardNumero}>{dados.vendedores_filial}</span>
        <span className={styles.cardSub}>operando rota direta</span>
        <div className={styles.subStats}>
          <span className={styles.subStat}>
            <span className={styles.subStatRotulo}>Matriz</span>
            <span className={styles.subStatValor}>{dados.vendedores_matriz}</span>
          </span>
          <span className={styles.subStat}>
            <span className={styles.subStatRotulo}>Ativos</span>
            <span className={styles.subStatValor}>{dados.vendedores_ativos}</span>
          </span>
          <span className={styles.subStat}>
            <span className={styles.subStatRotulo}>Atrasadas</span>
            <span className={styles.subStatValor}>{dados.atrasadas_total}</span>
          </span>
        </div>
      </div>

      <div className={`${styles.card} ${styles.span2}`}>
        <span className={styles.cardRotulo}>Ranking por volume · quem mais movimentou</span>
        {ranking.length === 0 ? (
          <p className={styles.vazio}>Nenhum vendedor com provas no período.</p>
        ) : (
          <ListaBarra itens={ranking} ordinal ariaLabel="Ranking por volume" />
        )}
      </div>

      <div className={`${styles.card} ${styles.span4}`}>
        <span className={styles.cardRotulo}>Detalhamento · aprovação · reprovação · tempo</span>
        {dados.por_vendedor.length === 0 ? (
          <p className={styles.vazio}>Nenhum vendedor com provas no período.</p>
        ) : (
          <div className={styles.scrollTabela}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th>Vendedor</th>
                  <th>Local</th>
                  <th className={styles.num}>Aprov.</th>
                  <th className={styles.num}>Reprov.</th>
                  <th className={styles.num}>Tempo</th>
                  <th className={styles.num}>Atras.</th>
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
                    <td>
                      <span className={styles.localPill}>
                        {m.localizacao === "filial"
                          ? "Filial"
                          : m.localizacao === "matriz"
                            ? "Matriz"
                            : "—"}
                      </span>
                    </td>
                    <td className={`${styles.num} ${styles.verde}`}>
                      {fmtPct(taxaAprovacao(m.taxa_reprovacao))}
                    </td>
                    <td className={styles.num}>{fmtPct(m.taxa_reprovacao)}</td>
                    <td className={styles.num}>{fmtHoras(m.tempo_medio_horas)}</td>
                    <td className={`${styles.num} ${m.atrasadas > 0 ? styles.vermelho : ""}`}>
                      {m.atrasadas}
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
