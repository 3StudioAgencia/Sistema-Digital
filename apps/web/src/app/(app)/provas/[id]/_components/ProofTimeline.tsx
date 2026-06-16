"use client";

/**
 * Timeline visual da prova (W3-C13) — `<ProofTimeline rota historico estado_atual />`.
 *
 * Embutida no card "Histórico de movimentações" do detalhe (C08), substituindo o
 * empty state. Busca `GET /provas/{id}/movimentacoes` (1 chamada — DP-2; o detalhe
 * já carregou o card) e desenha, por ciclo (DP-3), o caminho da rota: etapas
 * percorridas (responsável + data/hora), a ATUAL destacada (anel animado), as
 * futuras esmaecidas; laminação e travessias de motorista diferenciadas;
 * reprovação/cancelamento com motivo em destaque.
 *
 * O caminho canônico vem do backend (`etapas_canonicas`, derivado das regras do
 * C11 — DP-1): aqui só se PINTA o modelo de `construirTimeline`. Falha do
 * histórico é isolada (estado de erro próprio) — NÃO derruba o detalhe (§3.6).
 * Animações sobre os tokens (transform/opacity), instantâneas sob
 * `prefers-reduced-motion`.
 */
import { motion } from "framer-motion";
import { useEffect, useState } from "react";

import { obterMovimentacoes, type Timeline } from "@/lib/api/timeline";
import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING } from "@/lib/motion/tokens";
import { rotuloRota } from "@/lib/provas/rota-labels";
import { rotuloStatus } from "@/lib/provas/status-labels";
import {
  construirTimeline,
  type EtapaNode,
  type EventoNode,
  type TimelineNode,
} from "@/lib/provas/timeline";

import styles from "./ProofTimeline.module.css";

const EVENTO_TITULO: Record<EventoNode["tipo"], string> = {
  reprovacao: "Reprovada",
  cancelamento: "Cancelada",
  reinicio: "Ciclo reiniciado",
};

function formatarDataHora(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  // UTC (mesmo critério do detalhe/listagem): a data exibida casa com a do banco.
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mi = String(d.getUTCMinutes()).padStart(2, "0");
  return `${dd}/${mm}/${d.getUTCFullYear()} ${hh}:${mi}`;
}

function classeNo(node: TimelineNode): string {
  if (node.tipo === "etapa") {
    const mapa: Record<EtapaNode["status"], string> = {
      percorrido: styles.percorrido,
      atual: styles.atual,
      futuro: styles.futuro,
      nao_percorrido: styles.naoPercorrido,
    };
    return mapa[node.status];
  }
  const evento = node.atual ? styles.atual : "";
  return `${styles[node.tipo]} ${evento}`.trim();
}

function metaEtapa(node: EtapaNode): string {
  const quando = formatarDataHora(node.quando);
  if (node.ator_nome && node.quando) return `${node.ator_nome} · ${quando}`;
  if (node.estado === "criada" && node.quando) return `Criada em ${quando}`;
  if (node.status === "atual") return "Etapa atual";
  if (node.status === "futuro") return "Pendente";
  return quando;
}

function NoItem({
  node,
  indice,
  reduced,
}: {
  node: TimelineNode;
  indice: number;
  reduced: boolean;
}) {
  const entrada = {
    initial: { opacity: 0, x: reduced ? 0 : -8 },
    animate: { opacity: 1, x: 0 },
    transition: {
      duration: reduced ? DURATION.instant : DURATION.short,
      ease: EASING.emphasized,
      // Revelação progressiva (RF-026), com teto p/ rotas longas não arrastarem.
      delay: reduced ? 0 : Math.min(indice, 14) * 0.04,
    },
  };

  if (node.tipo === "etapa") {
    return (
      <motion.li className={`${styles.item} ${classeNo(node)}`} {...entrada}>
        <span className={styles.rail} aria-hidden>
          <span className={styles.marker} />
        </span>
        <div className={styles.conteudo}>
          <div className={styles.tituloLinha}>
            <span className={styles.titulo}>{rotuloStatus(node.estado)}</span>
            {node.laminacao && (
              <span className={`${styles.tag} ${styles.tagLamina}`}>Laminação</span>
            )}
            {node.motorista && (
              <span className={`${styles.tag} ${styles.tagMotorista}`}>Em trânsito</span>
            )}
            {node.tem_assinatura && (
              <span className={`${styles.tag} ${styles.tagAssinada}`}>✓ Assinada</span>
            )}
          </div>
          <span className={styles.meta}>{metaEtapa(node)}</span>
        </div>
      </motion.li>
    );
  }

  const quando = formatarDataHora(node.quando);
  return (
    <motion.li className={`${styles.item} ${classeNo(node)}`} {...entrada}>
      <span className={styles.rail} aria-hidden>
        <span className={styles.marker} />
      </span>
      <div className={styles.conteudo}>
        <div className={styles.tituloLinha}>
          <span className={styles.titulo}>{EVENTO_TITULO[node.tipo]}</span>
        </div>
        <span className={styles.meta}>
          {node.ator_nome ? `${node.ator_nome} · ${quando}` : quando}
        </span>
        {node.motivo && <p className={styles.motivo}>{node.motivo}</p>}
      </div>
    </motion.li>
  );
}

export function ProofTimeline({ provaId }: { provaId: string }) {
  const reduced = useReducedMotion();
  const [estado, setEstado] = useState<"carregando" | "pronto" | "erro">("carregando");
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    obterMovimentacoes(provaId, controller.signal)
      .then((t) => {
        setTimeline(t);
        setEstado("pronto");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        // Qualquer falha (incl. o 404 que não deveria ocorrer — o detalhe já
        // resolveu a prova) vira erro LOCAL da timeline; o detalhe segue de pé (§3.6).
        setEstado("erro");
      });
    return () => controller.abort();
  }, [provaId, tentativa]);

  if (estado === "carregando") {
    return (
      <div className={styles.skeleton} aria-hidden>
        <div className={styles.skeletonLinha} />
        <div className={styles.skeletonLinha} />
        <div className={styles.skeletonLinha} />
      </div>
    );
  }

  if (estado === "erro" || !timeline) {
    return (
      <p className={styles.erro} role="alert">
        Não foi possível carregar o histórico.{" "}
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
    );
  }

  const render = construirTimeline(timeline);
  const multiplosCiclos = render.ciclos.length > 1;

  return (
    <div className={styles.timeline}>
      <span className={styles.badgeRota}>Rota: {rotuloRota(timeline.rota)}</span>
      {render.ciclos.map((ciclo) => (
        <div key={ciclo.numero} className={styles.ciclo}>
          {multiplosCiclos && (
            <div className={styles.cicloSeparador}>
              <span>Ciclo {ciclo.numero}</span>
            </div>
          )}
          <ol className={styles.lista}>
            {ciclo.nodes.map((node, i) => (
              <NoItem key={`${ciclo.numero}-${i}`} node={node} indice={i} reduced={reduced} />
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
