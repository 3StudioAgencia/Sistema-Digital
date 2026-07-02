"use client";
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
import { useCallback, useEffect, useState } from "react";

import { AnimatedCounter } from "@/components/ui/animated-counter/AnimatedCounter";
import { type Dashboard, fetchDashboard } from "@/lib/api/dashboard";
import { assinarDashboard } from "@/lib/api/eventos";
import { useReducedMotion } from "@/lib/motion/hooks";
import { fadeRise, staggerContainer } from "@/lib/motion/variants";

import styles from "../dashboard.module.css";

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

  const refetch = useCallback(async (silencioso = true) => {
    try {
      const novo = await fetchDashboard();
      setDados(novo);
      setErro(false);
    } catch {
      if (!silencioso) setErro(true);
    }
  }, []);

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

  // Realtime (etapa 3): stream SSE (`/api/dashboard/stream`) → a cada sinal "mudou",
  // rebusca a agregação (debounce ~800 ms + jitter — colapsa rajadas e descorrelaciona
  // clientes, evitando thundering herd). O servidor fecha o stream pouco antes de o
  // token expirar (evento `expira`): renovamos o cookie (`/api/auth/refresh`) e
  // reabrimos — o EventSource não faz refresh sozinho. Queda do stream degrada
  // graciosamente (reabre ou fica no último valor; sem polling — RNF-021). O count-up
  // do <AnimatedCounter> reage sozinho às mudanças de `dados` via setDados.
  useEffect(() => {
    let ativo = true;
    let fechar: (() => void) | null = null;
    let debounceId: ReturnType<typeof setTimeout> | null = null;

    const agendarRefetch = () => {
      if (debounceId !== null) clearTimeout(debounceId);
      debounceId = setTimeout(() => void refetch(), 800 + Math.floor(Math.random() * 400));
    };

    function conectar() {
      if (!ativo) return;
      fechar = assinarDashboard({
        onMudou: agendarRefetch,
        onExpira: () => {
          // Fecha o stream corrente (cancela o auto-reconnect do EventSource),
          // renova o cookie httpOnly e reabre com o token fresco.
          fechar?.();
          fechar = null;
          void (async () => {
            try {
              await fetch("/api/auth/refresh", { method: "POST", cache: "no-store" });
            } catch {
              // Refresh falhou: reabrimos mesmo assim (o handshake do stream refaz a
              // auth; se falhar, degrada para SSR + refetch manual — sem loop).
            }
            conectar();
          })();
        },
      });
    }

    conectar();
    return () => {
      ativo = false;
      if (debounceId !== null) clearTimeout(debounceId);
      fechar?.();
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
