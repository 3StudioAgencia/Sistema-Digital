"use client";

/**
 * Detalhe da prova (W2-C08) — a tela onde a prova "se abre".
 *
 * Client component (mesmo padrão do C07): busca `GET /provas/{id}` via `apiFetch`
 * (Bearer da sessão). Decisões do dono:
 * - DP-5: a arte vem por PROXY do backend (`GET /provas/{id}/arte`) como blob →
 *   `objectURL` num `<img>`; a key do R2 nunca é exposta nem há URL pública.
 * - DP-6: 404 (inexistente OU fora do escopo — MESMO caso, anti-enumeração §11)
 *   → toast genérico + `router.replace('/provas')`. "Voltar" usa `router.back()`
 *   (preserva os filtros da listagem) com fallback para `/provas`.
 * - DP-4: "Visualizar etiqueta" abre o PDF num `MotionModal` (C04); "Baixar"
 *   reusa `baixarEtiqueta` + `salvarArquivo` (C06).
 * - DP-2: "Histórico de movimentações" nasce em empty state (a timeline é do C13,
 *   os dados do C11) — esta seção é o lugar onde eles plugam.
 * - DP-1/DP-7: exibe `ciclo_atual` e o NOME real da rota (`rotuloRota`).
 *
 * Animações sobre os tokens (GPU — transform/opacity), instantâneas sob
 * `prefers-reduced-motion`.
 */
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { MotionModal } from "@/components/ui/modal/MotionModal";
import { useToast } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import {
  baixarArte,
  baixarEtiqueta,
  obterProva,
  salvarArquivo,
  type ProvaDetalhe,
} from "@/lib/api/provas";
import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";
import { rotuloRota } from "@/lib/provas/rota-labels";
import { rotuloStatus } from "@/lib/provas/status-labels";

import styles from "../prova-detalhe.module.css";

/** Mensagem ÚNICA p/ inexistente E fora-de-escopo (anti-enumeração — §11). */
const MSG_NAO_ENCONTRADA = "Prova não encontrada.";

function formatarData(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  // Em UTC (mesmo critério da listagem): o dia exibido casa com o filtro/criação.
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getUTCFullYear()}`;
}

export function ProvaDetalheView({ provaId }: { provaId: string }) {
  const reduced = useReducedMotion();
  const router = useRouter();
  const toast = useToast();

  const [estado, setEstado] = useState<"carregando" | "pronto" | "erro">("carregando");
  const [prova, setProva] = useState<ProvaDetalhe | null>(null);
  const [tentativa, setTentativa] = useState(0);

  const [arteUrl, setArteUrl] = useState<string | null>(null);
  const [arteFalhou, setArteFalhou] = useState(false);

  const [baixando, setBaixando] = useState(false);
  const [visualizando, setVisualizando] = useState(false);
  const [etiquetaUrl, setEtiquetaUrl] = useState<string | null>(null);
  const [modalAberto, setModalAberto] = useState(false);

  // `router`/`toast` são estáveis em produção, mas mantidos FORA das deps do
  // efeito de busca via ref (mesmo padrão do C07 provas-view): evita refetch a
  // cada render e mantém o efeito dependente só do que de fato muda a consulta.
  const acoesRef = useRef({ router, toast });
  useEffect(() => {
    acoesRef.current = { router, toast };
  });

  // Detalhe da prova. 404 = inexistente OU fora do escopo (RLS) — MESMO caminho:
  // toast genérico + volta à listagem, sem revelar a existência (§11). O estado
  // inicial já é "carregando" (e o retry o re-arma no handler) — nada de setState
  // síncrono no corpo do efeito.
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
          acoesRef.current.router.replace("/provas");
          return;
        }
        setEstado("erro");
      });
    return () => controller.abort();
  }, [provaId, tentativa]);

  // Arte por proxy (DP-5): blob → objectURL. Revoga ao desmontar/trocar.
  const provaIdCarregada = prova?.id;
  useEffect(() => {
    if (!provaIdCarregada) return;
    const controller = new AbortController();
    let url: string | null = null;
    baixarArte(provaIdCarregada, controller.signal)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setArteUrl(url);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setArteFalhou(true); // degrada para placeholder; não derruba a tela
      });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [provaIdCarregada]);

  // Revoga o objectURL da etiqueta no unmount/troca (o modal pode estar ABERTO
  // ao sair por sidebar/back/troca de prova — `fecharModal` só cobre o fechar
  // manual). Também revoga o anterior ao re-visualizar. Único ponto de revogação.
  useEffect(() => {
    if (!etiquetaUrl) return;
    return () => URL.revokeObjectURL(etiquetaUrl);
  }, [etiquetaUrl]);

  function voltar() {
    // Preserva os filtros da listagem via histórico do navegador (DP-6); sem
    // histórico (entrada direta/refresh) cai na listagem.
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else router.push("/provas");
  }

  async function baixar() {
    if (!prova || baixando) return;
    setBaixando(true);
    try {
      const blob = await baixarEtiqueta(prova.id);
      salvarArquivo(blob, `etiqueta-${prova.codigo}.pdf`);
    } catch {
      toast.error("Não foi possível baixar a etiqueta. Tente novamente.");
    } finally {
      setBaixando(false);
    }
  }

  async function visualizar() {
    if (!prova || visualizando) return;
    setVisualizando(true);
    try {
      const blob = await baixarEtiqueta(prova.id);
      setEtiquetaUrl(URL.createObjectURL(blob));
      setModalAberto(true);
    } catch {
      toast.error("Não foi possível abrir a etiqueta. Tente novamente.");
    } finally {
      setVisualizando(false);
    }
  }

  function fecharModal() {
    setModalAberto(false);
    setEtiquetaUrl(null); // o efeito de cleanup revoga o objectURL anterior
  }

  const duracao = reduced ? DURATION.instant : DURATION.medium;
  // Entrada suave dos cartões (opacity + leve y), com pequeno stagger entre eles;
  // instantânea sob prefers-reduced-motion. Só transform/opacity (GPU — §3.4).
  const entrada = (delay: number) => ({
    initial: { opacity: 0, y: reduced ? 0 : 8 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: duracao, ease: EASING.emphasized, delay: reduced ? 0 : delay },
  });
  // Feedback tátil de toque nas ações (mola única da plataforma — C03/SPRING).
  const toque = reduced ? {} : { whileTap: { scale: 0.97 }, transition: SPRING.interactive };

  return (
    <section className={styles.pagina} aria-label="Detalhe da prova">
      <motion.button type="button" className={styles.voltar} onClick={voltar} {...toque}>
        <span aria-hidden>←</span> Voltar
      </motion.button>

      {estado === "carregando" ? (
        <div className={`${styles.cardDetalhe} ${styles.skeletonCard}`} aria-hidden />
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
          <motion.article className={styles.cardDetalhe} {...entrada(0)}>
            <div className={styles.arteCol}>
              {arteUrl ? (
                <motion.img
                  src={arteUrl}
                  alt={`Arte da prova ${prova.nome}`}
                  className={styles.arte}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{
                    duration: reduced ? DURATION.instant : DURATION.short,
                    ease: EASING.standard,
                  }}
                />
              ) : arteFalhou ? (
                <div className={styles.artePlaceholder} role="img" aria-label="Arte indisponível">
                  Arte indisponível
                </div>
              ) : (
                <div className={`${styles.artePlaceholder} ${styles.arteSkeleton}`} aria-hidden />
              )}
            </div>

            <div className={styles.meta}>
              <p className={styles.requerimento}>Requerimento: {prova.requerimento}</p>
              <h1 className={styles.nome}>{prova.nome}</h1>

              <hr className={styles.divisor} />

              <dl className={styles.grid}>
                <Campo rotulo="Cliente:" valor={prova.cliente} />
                <Campo rotulo="Rota:" valor={rotuloRota(prova.rota)} />
                <Campo rotulo="Criada em:" valor={formatarData(prova.created_at)} />
                <Campo rotulo="Vendedor:" valor={prova.vendedor_nome ?? "—"} />
                <Campo rotulo="Ciclo Atual:" valor={String(prova.ciclo_atual)} />
                <Campo rotulo="Status:" valor={rotuloStatus(prova.status)} />
              </dl>

              <div className={styles.acoes}>
                <motion.button
                  type="button"
                  className={styles.btnPrimario}
                  onClick={visualizar}
                  disabled={visualizando}
                  {...toque}
                >
                  {visualizando ? "Abrindo…" : "Visualizar etiqueta"}
                </motion.button>
                <motion.button
                  type="button"
                  className={styles.btnSecundario}
                  onClick={baixar}
                  disabled={baixando}
                  {...toque}
                >
                  {baixando ? "Baixando…" : "Baixar etiqueta"}
                </motion.button>
              </div>
            </div>
          </motion.article>

          {/* Histórico (DP-2): empty state agora; timeline do C13 pluga aqui. */}
          <motion.section
            className={styles.historico}
            aria-label="Histórico de movimentações"
            {...entrada(0.07)}
          >
            <h2 className={styles.historicoTitulo}>Histórico de movimentações</h2>
            <div className={styles.historicoVazio}>
              <p>Esta prova ainda não teve movimentações.</p>
              <p className={styles.historicoVazioSub}>
                A timeline visual fica disponível quando a prova for escaneada pela primeira vez.
              </p>
            </div>
          </motion.section>

          <MotionModal
            open={modalAberto}
            onClose={fecharModal}
            labelledBy="etiqueta-modal-titulo"
            panelClassName={styles.modalEtiqueta}
          >
            <div className={styles.modalCabecalho}>
              <h2 id="etiqueta-modal-titulo" className={styles.modalTitulo}>
                Etiqueta — {prova.codigo}
              </h2>
              <button type="button" className={styles.modalFechar} onClick={fecharModal}>
                Fechar
              </button>
            </div>
            {etiquetaUrl && (
              <iframe
                src={etiquetaUrl}
                title={`Etiqueta da prova ${prova.codigo}`}
                className={styles.iframeEtiqueta}
              />
            )}
          </MotionModal>
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
