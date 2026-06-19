"use client";

/**
 * Dashboard em tempo real (W4-C16) — fiel ao design (layout bento).
 *
 * Cards de contador (clicáveis → listagem pré-filtrada do C07 — DP-6), o card
 * "Atrasadas" como LISTA por vendedor + total, e os atalhos Escanear/Nova Prova
 * (role-aware — DP-3). Os números sobem com count-up (RF-025, respeitando
 * prefers-reduced-motion).
 *
 * Eficiência (RNF-021/022): UMA única subscription do Realtime às mudanças de
 * `provas`; cada evento dispara um REFETCH único da agregação (debounced) — sem
 * polling, sem refetch por card. A queda do Realtime degrada graciosamente
 * (mantém o último valor); a carga inicial vem SSR (sem waterfall).
 */
import { motion } from "framer-motion";
import {
  Clock,
  FileCheck2,
  FilePlus2,
  Plus,
  Printer,
  QrCode,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { AnimatedCounter } from "@/components/ui/animated-counter/AnimatedCounter";
import { type Dashboard, fetchDashboard } from "@/lib/api/dashboard";
import { useReducedMotion } from "@/lib/motion/hooks";
import { fadeRise, staggerContainer } from "@/lib/motion/variants";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

import styles from "../dashboard.module.css";

// Coalesce rajadas de eventos numa só ida ao backend (mínimo de requisições).
const REFETCH_DEBOUNCE_MS = 800;

/** Dia de HOJE no fuso comercial (America/Sao_Paulo) como YYYY-MM-DD — casa com a
 * regra de "Criadas hoje" do backend (que usa o mesmo fuso). */
function hojeSaoPaulo(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
}

export function DashboardView({
  inicial,
  podeCriarProva,
}: {
  inicial: Dashboard | null;
  podeCriarProva: boolean;
}) {
  const router = useRouter();
  const reduced = useReducedMotion();
  const [dados, setDados] = useState<Dashboard | null>(inicial);
  const [erro, setErro] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refetch = useCallback(async (silencioso = true) => {
    try {
      const novo = await fetchDashboard();
      setDados(novo);
      setErro(false);
    } catch {
      // Realtime/transitório: mantém o último valor (degradação graciosa). Só a
      // carga/retry explícito sinaliza erro na tela.
      if (!silencioso) setErro(true);
    }
  }, []);

  // Carga no cliente só se o SSR não trouxe os dados (API fora no 1º byte).
  // setState no callback do .then (não no corpo do efeito) — mesmo padrão do C07.
  useEffect(() => {
    if (inicial !== null) return;
    const controller = new AbortController();
    fetchDashboard(controller.signal)
      .then((novo) => {
        setDados(novo);
        setErro(false);
      })
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setErro(true);
      });
    return () => controller.abort();
  }, [inicial]);

  // UMA subscription Realtime às mudanças de `provas` → refetch único debounced
  // (RNF-021: sem polling, sem refetch por card). Escopo dos números: a RLS no
  // backend (o refetch passa pelo endpoint escopado).
  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    const agendarRefetch = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => void refetch(), REFETCH_DEBOUNCE_MS);
    };
    const channel = supabase
      .channel("dashboard-provas")
      .on("postgres_changes", { event: "*", schema: "public", table: "provas" }, agendarRefetch)
      .subscribe();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      void supabase.removeChannel(channel);
    };
  }, [refetch]);

  const irPara = useCallback(
    (params: [string, string][]) => {
      const qs = new URLSearchParams(params).toString();
      router.push(`/provas?${qs}`);
    },
    [router],
  );

  if (dados === null) {
    return (
      <section className={styles.pagina} aria-label="Dashboard">
        {erro ? (
          <p className={styles.estadoErro} role="alert">
            Não foi possível carregar o painel.{" "}
            <button
              type="button"
              className={styles.tentarNovamente}
              onClick={() => void refetch(false)}
            >
              Tentar novamente
            </button>
          </p>
        ) : (
          <div className={styles.bento} aria-hidden>
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className={`${styles.card} ${styles.skeleton}`} />
            ))}
          </div>
        )}
      </section>
    );
  }

  // Cascata de entrada dos cards do bento (W6-C19): o container orquestra; cada
  // card é um motion-node que herda o disparo (variante "item"). Aplicado nos
  // PRÓPRIOS nós do grid (sem wrapper extra) p/ não quebrar o grid-area do bento.
  const containerVar = staggerContainer(reduced);
  const itemVar = fadeRise(reduced);

  const cardContador = (
    rotulo: string,
    valor: number,
    area: string,
    Icone: LucideIcon,
    onClick: () => void,
    largo = false,
  ) => (
    <motion.button
      type="button"
      variants={itemVar}
      className={`${styles.card} ${styles.cardContador} ${area} ${largo ? styles.largo : ""}`}
      onClick={onClick}
    >
      <span className={styles.cardTopo}>
        <span className={styles.cardTitulo}>{rotulo}</span>
        <span className={styles.cardIcone} aria-hidden>
          <Icone strokeWidth={1.5} />
        </span>
      </span>
      <AnimatedCounter value={valor} className={styles.cardNumero} />
    </motion.button>
  );

  return (
    <section className={styles.pagina} aria-label="Dashboard">
      <motion.div className={styles.bento} variants={containerVar} initial="hidden" animate="show">
        {cardContador("Criadas hoje", dados.criadas_hoje, styles.criadas, FilePlus2, () =>
          irPara([["criada", hojeSaoPaulo()]]),
        )}
        {cardContador("Com Vendedor", dados.com_vendedor, styles.comVendedor, UserRound, () =>
          irPara([
            ["status", "retirada_vendedor"],
            ["status", "encaminhada_para_vendedor"],
          ]),
        )}
        {cardContador(
          "Aprovadas",
          dados.aprovadas,
          styles.aprovadas,
          FileCheck2,
          () => irPara([["status", "aprovada_vendedor"]]),
          true,
        )}
        {cardContador("Na clicheria", dados.na_clicheria, styles.naClicheria, Printer, () =>
          irPara([["status", "recebida_clicheria"]]),
        )}

        {/* Atrasadas: lista por vendedor + total (≠ dos demais cards) */}
        <motion.div
          variants={itemVar}
          className={`${styles.card} ${styles.atrasadasCard} ${styles.atrasadas}`}
        >
          <span className={styles.cardTopo}>
            <span className={styles.cardTitulo}>Atrasadas</span>
            <span className={styles.cardIcone} aria-hidden>
              <Clock strokeWidth={1.5} />
            </span>
          </span>
          <ul className={styles.atrasadasLista} aria-label="Atrasadas por vendedor">
            {dados.atrasadas_por_vendedor.length === 0 ? (
              <li className={styles.atrasadasVazio}>Nenhuma prova atrasada.</li>
            ) : (
              dados.atrasadas_por_vendedor.map((v) => (
                <li key={v.vendedor_id}>
                  <button
                    type="button"
                    className={styles.atrasadaLinha}
                    onClick={() =>
                      irPara([
                        ["atrasada", "true"],
                        ["vendedor", v.vendedor_id],
                      ])
                    }
                  >
                    <span className={styles.atrasadaNome}>{v.vendedor_nome ?? "—"}</span>
                    <span className={styles.atrasadaTotal}>{v.total}</span>
                  </button>
                </li>
              ))
            )}
          </ul>
          <button
            type="button"
            className={styles.atrasadasRodape}
            onClick={() => irPara([["atrasada", "true"]])}
            aria-label={`Ver todas as ${dados.atrasadas_total} provas atrasadas`}
          >
            <AnimatedCounter value={dados.atrasadas_total} className={styles.atrasadasTotal} />
          </button>
        </motion.div>

        {/* Atalhos (role-aware — DP-3) */}
        <motion.button
          type="button"
          variants={itemVar}
          className={`${styles.atalho} ${styles.atalhoEscanear} ${styles.escanear}`}
          onClick={() => router.push("/escanear")}
        >
          <span className={styles.atalhoRotulo}>Escanear QR Code</span>
          <span className={styles.atalhoIcone} aria-hidden>
            <QrCode strokeWidth={1.5} />
          </span>
        </motion.button>
        {podeCriarProva ? (
          <motion.button
            type="button"
            variants={itemVar}
            className={`${styles.atalho} ${styles.atalhoNova} ${styles.novaProva}`}
            onClick={() => router.push("/provas/nova")}
          >
            <span className={styles.atalhoRotulo}>Nova Prova</span>
            <span className={styles.atalhoIcone} aria-hidden>
              <Plus strokeWidth={2} />
            </span>
          </motion.button>
        ) : null}
      </motion.div>
    </section>
  );
}
