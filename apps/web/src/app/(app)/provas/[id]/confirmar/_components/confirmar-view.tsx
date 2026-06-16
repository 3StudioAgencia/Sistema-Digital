"use client";

/**
 * Confirmação da movimentação (W3-C10/DP-2) — destino após identificar a prova.
 *
 * Busca o detalhe (`GET /provas/{id}`, universal-em-escopo, mesmo padrão do C08)
 * e mostra o NOME e o REQUERIMENTO da prova + um PLACEHOLDER de assinatura. O C10
 * só IDENTIFICA: quem valida a próxima transição (perfil+estado) é o C11 e quem
 * captura a assinatura é o C12 — eles plugam exatamente neste cartão.
 *
 * 404 (inexistente OU fora do escopo — anti-enumeração §11) → toast genérico +
 * volta ao escaneamento, sem revelar se a prova existe. Animações sobre os tokens
 * (GPU — transform/opacity), instantâneas sob `prefers-reduced-motion`.
 */
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useToast } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import { obterProva, type ProvaDetalhe } from "@/lib/api/provas";
import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";
import { rotuloRota } from "@/lib/provas/rota-labels";
import { rotuloStatus } from "@/lib/provas/status-labels";

import styles from "../confirmar.module.css";

/** Mensagem ÚNICA p/ inexistente E fora-de-escopo (anti-enumeração — §11). */
const MSG_NAO_ENCONTRADA = "Prova não encontrada.";

export function ConfirmarView({ provaId }: { provaId: string }) {
  const reduced = useReducedMotion();
  const router = useRouter();
  const toast = useToast();

  const [estado, setEstado] = useState<"carregando" | "pronto" | "erro">("carregando");
  const [prova, setProva] = useState<ProvaDetalhe | null>(null);
  const [tentativa, setTentativa] = useState(0);

  const acoesRef = useRef({ router, toast });
  useEffect(() => {
    acoesRef.current = { router, toast };
  });

  useEffect(() => {
    const controller = new AbortController();
    obterProva(provaId, controller.signal)
      .then((p) => {
        setProva(p);
        setEstado("pronto");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (error instanceof ApiError && error.status === 404) {
          acoesRef.current.toast.error(MSG_NAO_ENCONTRADA);
          acoesRef.current.router.replace("/escanear");
          return;
        }
        setEstado("erro");
      });
    return () => controller.abort();
  }, [provaId, tentativa]);

  function voltar() {
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else router.push("/escanear");
  }

  const duracao = reduced ? DURATION.instant : DURATION.medium;
  const entrada = (delay: number) => ({
    initial: { opacity: 0, y: reduced ? 0 : 8 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: duracao, ease: EASING.emphasized, delay: reduced ? 0 : delay },
  });
  const toque = reduced ? {} : { whileTap: { scale: 0.97 }, transition: SPRING.interactive };

  return (
    <section className={styles.pagina} aria-label="Confirmar movimentação">
      <motion.button type="button" className={styles.voltar} onClick={voltar} {...toque}>
        <span aria-hidden>←</span> Voltar
      </motion.button>

      {estado === "carregando" ? (
        <div className={`${styles.card} ${styles.skeleton}`} aria-hidden />
      ) : estado === "erro" ? (
        <p className={styles.erro} role="alert">
          Não foi possível carregar a prova.{" "}
          <button
            type="button"
            className={styles.linkRetry}
            onClick={() => {
              setEstado("carregando");
              setTentativa((t) => t + 1);
            }}
          >
            Tentar novamente
          </button>
        </p>
      ) : prova ? (
        <>
          <motion.article className={styles.card} {...entrada(0)}>
            <p className={styles.codigo}>{prova.codigo}</p>
            <p className={styles.requerimento}>Requerimento: {prova.requerimento}</p>
            <h1 className={styles.nome}>{prova.nome}</h1>

            <hr className={styles.divisor} />

            <dl className={styles.grid}>
              <Campo rotulo="Cliente:" valor={prova.cliente} />
              <Campo rotulo="Rota:" valor={rotuloRota(prova.rota)} />
              <Campo rotulo="Status atual:" valor={rotuloStatus(prova.status)} />
            </dl>
          </motion.article>

          {/* Placeholder de assinatura (C12) + confirmação da transição (C11). */}
          <motion.section
            className={styles.assinatura}
            aria-label="Assinatura e confirmação"
            {...entrada(0.07)}
          >
            <h2 className={styles.assinaturaTitulo}>Assinatura digital</h2>
            <div className={styles.assinaturaPad} role="img" aria-label="Área de assinatura">
              <span className={styles.assinaturaDica}>
                A captura de assinatura chega com o componente de assinatura (C12).
              </span>
            </div>
            <motion.button
              type="button"
              className={styles.botaoConfirmar}
              disabled
              title="A confirmação da movimentação chega com a máquina de estados (C11)"
              {...toque}
            >
              Confirmar movimentação
            </motion.button>
            <p className={styles.assinaturaNota}>
              A validação da próxima movimentação (perfil + estado) é da máquina de estados (C11);
              este passo é apenas a identificação da prova.
            </p>
          </motion.section>
        </>
      ) : null}
    </section>
  );
}

function Campo({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className={styles.campo}>
      <dt className={styles.campoRotulo}>{rotulo}</dt>
      <dd className={styles.campoValor}>{valor}</dd>
    </div>
  );
}
