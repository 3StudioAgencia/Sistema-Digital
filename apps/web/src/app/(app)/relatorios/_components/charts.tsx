"use client";

/**
 * Gráficos dos Relatórios (W5-C17) — Recharts (DP-8). Só barras e donut, fiéis ao
 * design. Animações desligadas sob prefers-reduced-motion (RNF-010); cores via
 * tokens do globals.css. Os contêineres são responsivos (ResponsiveContainer).
 */
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { useReducedMotion } from "@/lib/motion/hooks";

import styles from "../relatorios.module.css";

/** Distribui os pontos de volume (por dia) em N faixas fixas — assim o gráfico
 * tem sempre uma quantidade densa de barras (look do design), mesmo com poucos
 * dados; faixas sem volume aparecem como uma barrinha mínima (minPointSize). */
function emFaixas(pontos: { dia: string; total: number }[], n: number): number[] {
  if (pontos.length === 0) return [];
  const tempos = pontos.map((p) => new Date(p.dia).getTime());
  const min = Math.min(...tempos);
  const max = Math.max(...tempos);
  const faixas = Array.from({ length: n }, () => 0);
  pontos.forEach((p, i) => {
    const frac = max === min ? 0.5 : (tempos[i] - min) / (max - min);
    faixas[Math.min(n - 1, Math.max(0, Math.floor(frac * (n - 1))))] += p.total;
  });
  return faixas;
}

/** Barras de volume (cards "Total geral" e "Vendedor com mais artes"). Bare — sem
 * eixos, fiel ao design; densas (binning + barra mínima); a última em destaque. */
export function VolumeBars({
  dados,
  className,
  cor = "var(--app-accent)",
  faixas = 18,
}: {
  dados: { dia: string; total: number }[];
  className?: string;
  cor?: string;
  faixas?: number;
}) {
  const reduced = useReducedMotion();
  const series = emFaixas(dados, faixas).map((total, i) => ({ i, total }));
  if (series.length === 0) return null;
  return (
    <div className={className ?? styles.chart}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={series}
          margin={{ top: 4, right: 0, bottom: 0, left: 0 }}
          barCategoryGap="16%"
        >
          <Bar
            dataKey="total"
            radius={[2, 2, 0, 0]}
            maxBarSize={14}
            minPointSize={4}
            isAnimationActive={!reduced}
          >
            {series.map((_, i) => (
              <Cell key={i} fill={cor} fillOpacity={i === series.length - 1 ? 1 : 0.55} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Donut "Provas Ativas" (Geral) — 2 segmentos (DP-3): Aguardando vendedor =
 * AMARELO (anel grosso, maior); Reprovada = PRETO (anel mais FINO, menor). Renderiza
 * dois `Pie` com raios diferentes para o preto ser radialmente mais estreito. */
export function ProvasAtivasDonut({
  aguardando,
  reprovadas,
}: {
  aguardando: number;
  reprovadas: number;
}) {
  const reduced = useReducedMotion();
  const total = aguardando + reprovadas;
  const COR_AGUARDANDO = "var(--app-accent)";
  const COR_REPROVADA = "var(--app-ink)";
  const inicio = 90;
  const fim = -270;
  // Ângulo onde o amarelo termina e o preto começa (sentido horário a partir do topo).
  const divisao = total === 0 ? inicio : inicio - (aguardando / total) * 360;
  return (
    <div className={styles.donutWrap}>
      <div className={styles.donut}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            {total === 0 ? (
              <Pie
                data={[{ valor: 1 }]}
                dataKey="valor"
                innerRadius="66%"
                outerRadius="100%"
                startAngle={inicio}
                endAngle={fim}
                stroke="none"
                isAnimationActive={false}
              >
                <Cell fill="#ededed" />
              </Pie>
            ) : null}
            {total > 0 ? (
              <Pie
                data={[{ valor: 1 }]}
                dataKey="valor"
                innerRadius="66%"
                outerRadius="100%"
                startAngle={inicio}
                endAngle={divisao}
                stroke="none"
                isAnimationActive={!reduced}
              >
                <Cell fill={COR_AGUARDANDO} />
              </Pie>
            ) : null}
            {total > 0 ? (
              <Pie
                data={[{ valor: 1 }]}
                dataKey="valor"
                innerRadius="73%"
                outerRadius="92%"
                startAngle={divisao}
                endAngle={fim}
                stroke="none"
                isAnimationActive={!reduced}
              >
                <Cell fill={COR_REPROVADA} />
              </Pie>
            ) : null}
          </PieChart>
        </ResponsiveContainer>
        <span className={styles.donutCentro} aria-hidden>
          {total}
        </span>
      </div>
      <ul className={styles.legenda} aria-label="Provas ativas por situação">
        <li className={styles.legendaItem}>
          <span className={styles.legendaPonto} style={{ background: COR_REPROVADA }} aria-hidden />
          Reprovada <b>{reprovadas}</b>
        </li>
        <li className={styles.legendaItem}>
          <span
            className={styles.legendaPonto}
            style={{ background: COR_AGUARDANDO }}
            aria-hidden
          />
          Aguardando vendedor <b>{aguardando}</b>
        </li>
      </ul>
    </div>
  );
}
