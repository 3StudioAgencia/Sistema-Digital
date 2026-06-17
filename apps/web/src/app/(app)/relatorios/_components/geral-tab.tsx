"use client";

/**
 * Aba Geral (W5-C17 · §0.2) — o piso do RF-016 (total, tempo médio, taxa,
 * distribuição por rota, atrasadas, por vendedor) + os extras do design. Os cards
 * de ranking ("Tempo médio por vendedor", "Vendedor com mais artes") DERIVAM da
 * mesma lista `metricas_por_vendedor` (sem ida extra ao banco — DP-3).
 */
import { ROTA_LABELS } from "@/lib/provas/rota-labels";
import { rotuloStatus } from "@/lib/provas/status-labels";
import { fetchRelatorioGeral, type FiltrosRelatorio } from "@/lib/api/relatorios";
import { fmtDec, fmtHoras, fmtInt, fmtPct, iniciais } from "@/lib/relatorios/format";

import styles from "../relatorios.module.css";
import { ProvasAtivasDonut, VolumeBars } from "./charts";
import { EstadoErro, GridSkeleton, useRelatorio } from "./use-relatorio";
import { ListaBarra, StatCard } from "./widgets";

export function GeralTab({ filtros, chave }: { filtros: FiltrosRelatorio; chave: string }) {
  const { dados, carregando, erro, recarregar } = useRelatorio(
    (s) => fetchRelatorioGeral(filtros, s),
    `geral|${chave}`,
  );

  if (erro) return <EstadoErro tipo={erro} onRetry={recarregar} />;
  if (carregando || dados === null) return <GridSkeleton cards={6} />;

  const tempoPorVendedor = dados.metricas_por_vendedor
    .filter((m) => m.tempo_medio_horas !== null)
    .sort((a, b) => (b.tempo_medio_horas ?? 0) - (a.tempo_medio_horas ?? 0))
    .map((m) => ({
      chave: m.vendedor_id,
      rotulo: m.vendedor_nome ?? "—",
      valor: m.tempo_medio_horas ?? 0,
      valorTexto: fmtHoras(m.tempo_medio_horas),
    }));

  const top = dados.metricas_por_vendedor[0]; // já vem ordenado por volume desc

  return (
    <div className={styles.grid}>
      <StatCard rotulo="Total geral" valor={dados.total_geral} escuro>
        <VolumeBars dados={dados.volume} className={styles.chartMini} />
      </StatCard>

      <StatCard
        rotulo="Tempo médio aprov."
        valor={fmtDec(dados.tempo_medio_aprovacao_horas)}
        unidade="horas"
      />
      <StatCard rotulo="Taxa reprovação" valor={fmtPct(dados.taxa_reprovacao)} vermelho />

      <div className={`${styles.card} ${styles.span2}`}>
        <span className={styles.cardRotulo}>Provas ativas</span>
        <ProvasAtivasDonut
          aguardando={dados.ativas_aguardando_vendedor}
          reprovadas={dados.ativas_reprovadas}
        />
      </div>

      <div className={`${styles.card} ${styles.span2}`}>
        <span className={styles.cardRotulo}>Tempo médio de aprovação por vendedor</span>
        {tempoPorVendedor.length === 0 ? (
          <p className={styles.vazio}>Nenhuma aprovação no período.</p>
        ) : (
          <ListaBarra itens={tempoPorVendedor} ordinal ariaLabel="Tempo médio por vendedor" />
        )}
      </div>

      <div className={`${styles.card} ${styles.span2}`}>
        <span className={styles.cardRotulo}>Rota</span>
        <ListaBarra
          ariaLabel="Distribuição por rota"
          itens={dados.distribuicao_rota.map((f) => ({
            chave: f.rota,
            rotulo: ROTA_LABELS[f.rota],
            valor: f.total,
            valorTexto: `${f.total} · ${fmtPct(dados.total_geral ? (100 * f.total) / dados.total_geral : 0)}`,
          }))}
        />
      </div>

      <StatCard
        rotulo="Vendedor com mais artes"
        valor={top ? top.volume : 0}
        sub={top?.vendedor_nome ?? "—"}
        escuro
      >
        <VolumeBars dados={dados.volume} className={styles.chartMini} />
      </StatCard>

      {/* Métricas por Vendedor (ranking detalhado) */}
      <div className={`${styles.card} ${styles.span4}`}>
        <span className={styles.cardRotulo}>Métricas por vendedor</span>
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
                  <th className={styles.num}>Volume</th>
                  <th className={styles.num}>Aprov.</th>
                  <th className={styles.num}>Reprov.</th>
                  <th className={styles.num}>Taxa</th>
                  <th className={styles.num}>Tempo</th>
                  <th className={styles.num}>Atras.</th>
                </tr>
              </thead>
              <tbody>
                {dados.metricas_por_vendedor.map((m, i) => (
                  <tr key={m.vendedor_id}>
                    <td className={styles.ordinal}>{String(i + 1).padStart(2, "0")}</td>
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
                    <td className={styles.num}>{fmtInt(m.volume)}</td>
                    <td className={styles.num}>{fmtInt(m.aprovadas)}</td>
                    <td className={styles.num}>{fmtInt(m.reprovadas)}</td>
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

      {/* Provas Atrasadas (aguardando ação) */}
      <div className={`${styles.card} ${styles.span4}`}>
        <span className={styles.cardRotulo}>Provas atrasadas · aguardando ação</span>
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
                    <td>{p.vendedor_nome ?? "—"}</td>
                    <td>{rotuloStatus(p.status)}</td>
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
