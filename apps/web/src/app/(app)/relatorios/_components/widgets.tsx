"use client";

/**
 * Widgets presentacionais reutilizáveis dos Relatórios (W5-C17).
 *
 * `StatCard` — card de métrica (rótulo + número grande + sub). Números inteiros
 * sobem com count-up (`AnimatedCounter`, reduced-motion aware); decimais/horas vêm
 * pré-formatados como texto. `ListaBarra` — lista ranqueada com barra proporcional
 * (largura via transform scaleX — GPU, DP-8/RNF-010), usada em distribuição por
 * rota, ranking por volume e top motivos.
 */
import type { ReactNode } from "react";

import { AnimatedCounter } from "@/components/ui/animated-counter/AnimatedCounter";

import styles from "../relatorios.module.css";
import { fracao } from "@/lib/relatorios/format";

export function StatCard({
  rotulo,
  valor,
  unidade,
  sub,
  escuro = false,
  vermelho = false,
  onClick,
  ariaLabel,
  children,
}: {
  rotulo: string;
  valor: number | string;
  unidade?: string;
  sub?: ReactNode;
  escuro?: boolean;
  vermelho?: boolean;
  onClick?: () => void;
  ariaLabel?: string;
  children?: ReactNode;
}) {
  const classeNumero = `${styles.cardNumero} ${vermelho ? styles.cardNumeroVermelho : ""}`;
  const conteudo = (
    <>
      <span className={styles.cardRotulo}>{rotulo}</span>
      <span>
        {typeof valor === "number" ? (
          <AnimatedCounter value={valor} className={classeNumero} />
        ) : (
          <span className={classeNumero}>{valor}</span>
        )}
        {unidade ? <span className={styles.cardUnidade}>{unidade}</span> : null}
      </span>
      {sub ? <span className={styles.cardSub}>{sub}</span> : null}
      {children}
    </>
  );
  const classe = `${styles.card} ${escuro ? styles.cardEscuro : ""}`;
  if (onClick) {
    return (
      <button
        type="button"
        className={`${classe} ${styles.clicavel}`}
        onClick={onClick}
        aria-label={ariaLabel}
      >
        {conteudo}
      </button>
    );
  }
  return <div className={classe}>{conteudo}</div>;
}

export type ItemBarra = {
  chave: string;
  rotulo: string;
  valor: number;
  /** Texto exibido à direita (default: o valor). */
  valorTexto?: string;
  cor?: "ink" | "amarela" | "vermelha";
  onClick?: () => void;
};

export function ListaBarra({
  itens,
  ordinal = false,
  ariaLabel,
}: {
  itens: ItemBarra[];
  ordinal?: boolean;
  ariaLabel?: string;
}) {
  const maximo = Math.max(1, ...itens.map((i) => i.valor));
  const corClasse = (cor: ItemBarra["cor"]) =>
    cor === "amarela"
      ? styles.barraFillAmarela
      : cor === "vermelha"
        ? styles.barraFillVermelha
        : "";
  return (
    <ul className={styles.lista} aria-label={ariaLabel}>
      {itens.map((item, i) => {
        const linha = (
          <div className={styles.linhaLista}>
            {ordinal ? (
              <span className={styles.ordinal}>{String(i + 1).padStart(2, "0")}</span>
            ) : null}
            <span className={styles.linhaListaRotulo}>{item.rotulo}</span>
            <span className={styles.linhaListaValor}>{item.valorTexto ?? item.valor}</span>
          </div>
        );
        return (
          <li key={item.chave}>
            {item.onClick ? (
              <button
                type="button"
                onClick={item.onClick}
                className={styles.clicavel}
                style={{ width: "100%", background: "none" }}
              >
                {linha}
              </button>
            ) : (
              linha
            )}
            <div className={styles.barraTrilha} aria-hidden>
              <div
                className={`${styles.barraFill} ${corClasse(item.cor)}`}
                style={{ transform: `scaleX(${fracao(item.valor, maximo)})` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
