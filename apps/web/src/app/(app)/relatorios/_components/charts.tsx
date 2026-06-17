"use client";

/**
 * Gráficos dos Relatórios (W5-C17) — Recharts (DP-8). Só barras e donut, fiéis ao
 * design. Animações desligadas sob prefers-reduced-motion (RNF-010); cores via
 * tokens do globals.css. Os contêineres são responsivos (ResponsiveContainer).
 */
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { useReducedMotion } from "@/lib/motion/hooks";

import styles from "../relatorios.module.css";

/** Barras de volume (card "Total geral" e "Vendedor com mais artes"). Bare — sem
 * eixos, fiel ao design; a última barra em destaque. */
export function VolumeBars({
  dados,
  className,
  cor = "var(--app-accent)",
}: {
  dados: { dia: string; total: number }[];
  className?: string;
  cor?: string;
}) {
  const reduced = useReducedMotion();
  if (dados.length === 0) return null;
  return (
    <div className={className ?? styles.chart}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={dados}
          margin={{ top: 4, right: 0, bottom: 0, left: 0 }}
          barCategoryGap="22%"
        >
          <Bar dataKey="total" radius={[3, 3, 0, 0]} isAnimationActive={!reduced}>
            {dados.map((_, i) => (
              <Cell key={i} fill={cor} fillOpacity={i === dados.length - 1 ? 1 : 0.5} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Donut "Provas Ativas" (Geral) — 2 segmentos (Aguardando vendedor / Reprovada,
 * DP-3), com o total no centro. */
export function ProvasAtivasDonut({
  aguardando,
  reprovadas,
}: {
  aguardando: number;
  reprovadas: number;
}) {
  const reduced = useReducedMotion();
  const total = aguardando + reprovadas;
  const COR_AGUARDANDO = "var(--app-ink)";
  const COR_REPROVADA = "var(--app-accent)";
  const dados =
    total === 0
      ? [{ nome: "vazio", valor: 1, cor: "#ededed" }]
      : [
          { nome: "Aguardando vendedor", valor: aguardando, cor: COR_AGUARDANDO },
          { nome: "Reprovada", valor: reprovadas, cor: COR_REPROVADA },
        ];
  return (
    <div className={styles.donutWrap}>
      <div className={styles.donut}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={dados}
              dataKey="valor"
              innerRadius="68%"
              outerRadius="100%"
              startAngle={90}
              endAngle={-270}
              stroke="none"
              isAnimationActive={!reduced}
            >
              {dados.map((d, i) => (
                <Cell key={i} fill={d.cor} />
              ))}
            </Pie>
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
