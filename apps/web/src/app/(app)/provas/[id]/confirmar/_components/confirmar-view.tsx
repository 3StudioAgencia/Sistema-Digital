"use client";

/**
 * Confirmação da movimentação (W3-C10/DP-2) — destino após identificar a prova.
 *
 * Layout fiel ao design (Figma), mesma linguagem do detalhe (C08): card BRANCO com
 * nome + "Requerimento:" + uma linha de metadados (Cliente · Vendedor · Rota ·
 * Ciclo Atual · Criada em · Status) e, dentro dele, um card PRETO "Assinatura
 * Digital" com a área de assinatura (placeholder do C12) e o botão "Confirmar"
 * (gancho do C11). O C10 só IDENTIFICA: validar a próxima transição é o C11 e
 * capturar a assinatura é o C12.
 *
 * Busca o detalhe (`GET /provas/{id}`, universal-em-escopo). 404 (inexistente OU
 * fora do escopo — anti-enumeração §11) → toast genérico + volta ao escaneamento.
 * Mobile-first; animações sobre os tokens (GPU), instantâneas sob
 * `prefers-reduced-motion`.
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

function formatarData(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getUTCFullYear()}`;
}

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

  function confirmar() {
    // Placeholder do C11: a transição (perfil+estado) e a assinatura (C12) plugam
    // aqui depois. Por ora, feedback claro de que o passo chega na máquina de estados.
    toast.success("A confirmação da movimentação chega com a máquina de estados (C11).");
  }

  const duracao = reduced ? DURATION.instant : DURATION.medium;
  const entrada = {
    initial: { opacity: 0, y: reduced ? 0 : 10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: duracao, ease: EASING.emphasized },
  };
  const toque = reduced ? {} : { whileTap: { scale: 0.97 }, transition: SPRING.interactive };

  return (
    <section className={styles.pagina} aria-label="Confirmar movimentação">
      <motion.button type="button" className={styles.voltar} onClick={voltar} {...toque}>
        <span aria-hidden>←</span> Voltar
      </motion.button>

      {estado === "carregando" ? (
        <div className={styles.skeleton} aria-hidden />
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
        <motion.article className={styles.cardExterno} {...entrada}>
          <div className={styles.cabecalho}>
            <div className={styles.tituloLinha}>
              <h1 className={styles.nome}>{prova.nome}</h1>
              <span className={styles.requerimento}>Requerimento: {prova.requerimento}</span>
            </div>

            <dl className={styles.metadados}>
              <Campo rotulo="Cliente:" valor={prova.cliente} />
              <Campo rotulo="Vendedor:" valor={prova.vendedor_nome ?? "—"} />
              <Campo rotulo="Rota:" valor={rotuloRota(prova.rota)} />
              <Campo rotulo="Ciclo Atual:" valor={String(prova.ciclo_atual)} />
              <Campo rotulo="Criada em:" valor={formatarData(prova.created_at)} />
              <Campo rotulo="Status:" valor={rotuloStatus(prova.status)} />
            </dl>
          </div>

          {/* Card preto — assinatura (placeholder C12) + Confirmar (gancho C11). */}
          <section className={styles.cardAssinatura} aria-label="Assinatura e confirmação">
            <h2 className={styles.assinaturaTitulo}>Assinatura Digital</h2>
            <div className={styles.assinaturaCanvas} role="img" aria-label="Área de assinatura">
              <span className={styles.assinaturaDica}>
                A captura de assinatura chega com o componente de assinatura (C12).
              </span>
            </div>
            <motion.button
              type="button"
              className={styles.botaoConfirmar}
              onClick={confirmar}
              {...toque}
            >
              Confirmar
            </motion.button>
          </section>
        </motion.article>
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
