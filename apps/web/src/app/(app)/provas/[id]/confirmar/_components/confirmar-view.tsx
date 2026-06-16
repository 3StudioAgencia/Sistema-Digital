"use client";

/**
 * Confirmação da movimentação (W3-C10/C12) — destino após identificar a prova.
 *
 * Fecha o laço identificar → assinar → confirmar → transição (RF-007/RF-028). Após
 * carregar a prova (C08) e as AÇÕES disponíveis (C12/DP-3 — reusa as regras do
 * C11), decide a branch (DP-4):
 *   (a) o ator é o próximo → a assinatura é apresentada AUTOMATICAMENTE (RF-028);
 *   (b) estados de posse do Vendedor → Aprovar/Reprovar (Reprovar exige motivo);
 *   (c) o ator NÃO é o próximo → bloqueio genérico, SEM revelar quem é (RN-014).
 *
 * Submete a assinatura desenhada (`react-signature-canvas` → PNG) + a ação ao motor
 * do C11 (atômico/idempotente). Resiliência (RNF-016/DP-5): falha de submissão
 * PRESERVA o traço (canvas em memória) + a ação (sessionStorage) e oferece retry
 * com a MESMA `idempotency_key` (converge, não duplica). Mobile-first; animações
 * sobre os tokens (GPU), instantâneas sob `prefers-reduced-motion`.
 */
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { useToast } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import { obterProva, type ProvaDetalhe } from "@/lib/api/provas";
import {
  type Acao,
  type AcaoDisponivel,
  acoesDisponiveis,
  executarTransicao,
} from "@/lib/api/transicoes";
import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";
import { rotuloRota } from "@/lib/provas/rota-labels";
import { rotuloStatus } from "@/lib/provas/status-labels";

import styles from "../confirmar.module.css";
import { AssinaturaPad, type AssinaturaPadHandle } from "./assinatura-pad";

/** Mensagem ÚNICA p/ inexistente E fora-de-escopo (anti-enumeração — §11). */
const MSG_NAO_ENCONTRADA = "Prova não encontrada.";
const MSG_ASSINE = "Desenhe a assinatura para confirmar.";
const MOTIVO_MAX = 500;

type Stash = { assinatura: string; acao: Acao; motivo: string; key: string };

function chaveStash(provaId: string): string {
  return `c12:confirmar:${provaId}`;
}

function lerStash(provaId: string): Stash | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    const bruto = sessionStorage.getItem(chaveStash(provaId));
    return bruto ? (JSON.parse(bruto) as Stash) : null;
  } catch {
    return null;
  }
}

function gravarStash(provaId: string, stash: Stash): void {
  try {
    sessionStorage?.setItem(chaveStash(provaId), JSON.stringify(stash));
  } catch {
    // quota/indisponível: a resiliência em-memória (canvas + retry) ainda vale.
  }
}

function limparStash(provaId: string): void {
  try {
    sessionStorage?.removeItem(chaveStash(provaId));
  } catch {
    /* no-op */
  }
}

function novaChave(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

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
  const [acoes, setAcoes] = useState<AcaoDisponivel[]>([]);
  const [tentativaCarregar, setTentativaCarregar] = useState(0);

  const [modoReprovar, setModoReprovar] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [motivoErro, setMotivoErro] = useState(false);
  const [submetendo, setSubmetendo] = useState(false);
  const [sucesso, setSucesso] = useState(false);
  const [erroSubmissao, setErroSubmissao] = useState<string | null>(null);

  const padRef = useRef<AssinaturaPadHandle | null>(null);
  const idemRef = useRef<string>("");
  const ultimaAcaoRef = useRef<Acao | null>(null);
  // Traço preservado (DP-5) a restaurar quando o pad montar; nulo após restaurar.
  const restaurarRef = useRef<string | null>(null);
  const motivoId = useId();

  // Ações estáveis para o efeito de carga (evita re-disparo por mudança de ref).
  const acoesEfeito = useRef({ router, toast });
  useEffect(() => {
    acoesEfeito.current = { router, toast };
  });

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      obterProva(provaId, controller.signal),
      acoesDisponiveis(provaId, controller.signal),
    ])
      .then(([p, a]) => {
        setProva(p);
        setAcoes(a);
        // Chave de idempotência: reaproveita a de um stash (retry pós-reload
        // converge) ou nasce nova. Definida client-side (sem mismatch de SSR).
        const stash = lerStash(provaId);
        idemRef.current = stash?.key ?? novaChave();
        if (stash) {
          restaurarRef.current = stash.assinatura; // o traço é restaurado no efeito
          if (stash.acao === "reprovar") {
            setModoReprovar(true);
            setMotivo(stash.motivo);
          }
        }
        setEstado("pronto");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (error instanceof ApiError && error.status === 404) {
          acoesEfeito.current.toast.error(MSG_NAO_ENCONTRADA);
          acoesEfeito.current.router.replace("/escanear");
          return;
        }
        setEstado("erro");
      });
    return () => controller.abort();
  }, [provaId, tentativaCarregar]);

  // Resiliência (DP-5): quando o pad monta, restaura o traço preservado. Só
  // efeito colateral no canvas (sem setState — a ação/motivo já vieram na carga).
  useEffect(() => {
    if (estado !== "pronto" || restaurarRef.current === null || !padRef.current) return;
    const url = restaurarRef.current;
    restaurarRef.current = null;
    padRef.current.fromDataURL(url);
    acoesEfeito.current.toast.success("Recuperamos sua assinatura. Confirme para registrar.");
  }, [estado]);

  function voltar() {
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else router.push("/escanear");
  }

  async function confirmar(acao: Acao) {
    if (submetendo || sucesso) return;
    if (padRef.current?.isEmpty() ?? true) {
      toast.error(MSG_ASSINE);
      return;
    }
    if (acao === "reprovar" && !motivo.trim()) {
      setMotivoErro(true);
      toast.error("Informe o motivo da reprovação.");
      return;
    }
    const assinatura = padRef.current!.toDataURL();
    ultimaAcaoRef.current = acao;
    setSubmetendo(true);
    setErroSubmissao(null);
    // Preserva ANTES de ir à rede: nem um crash/reload perde a operação (DP-5).
    gravarStash(provaId, { assinatura, acao, motivo, key: idemRef.current });
    try {
      const atualizada = await executarTransicao(provaId, {
        acao,
        assinatura,
        idempotencyKey: idemRef.current,
        motivo: acao === "reprovar" ? motivo.trim() : undefined,
      });
      limparStash(provaId);
      setSucesso(true);
      toast.success(`Movimentação registrada: ${rotuloStatus(atualizada.status)}.`);
      const ir = () => router.replace(`/provas/${provaId}`);
      if (reduced) ir();
      else setTimeout(ir, 650);
    } catch (error: unknown) {
      setSubmetendo(false);
      tratarErroSubmissao(error);
    }
  }

  function tratarErroSubmissao(error: unknown) {
    if (error instanceof ApiError) {
      if (error.status === 404) {
        limparStash(provaId);
        toast.error(MSG_NAO_ENCONTRADA);
        router.replace("/escanear");
        return;
      }
      if (error.status === 403) {
        // Não é a vez do ator (genérico — não revela quem é, RN-014).
        limparStash(provaId);
        toast.error(error.message);
        router.replace("/escanear");
        return;
      }
      if (error.status === 422) {
        if (error.code === "motivo_obrigatorio") setMotivoErro(true);
        toast.error(error.message); // traço preservado no canvas; o ator reenvia
        return;
      }
      if (error.status === 409) {
        limparStash(provaId);
        toast.error(error.message);
        return;
      }
    }
    // Rede/timeout/5xx → retentável: o traço fica no canvas + o stash sobrevive.
    setErroSubmissao(
      "Não foi possível registrar agora. Sua assinatura foi preservada — tente novamente.",
    );
  }

  const duracao = reduced ? DURATION.instant : DURATION.medium;
  const entrada = {
    initial: { opacity: 0, y: reduced ? 0 : 10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: duracao, ease: EASING.emphasized },
  };
  const toque = reduced ? {} : { whileTap: { scale: 0.97 }, transition: SPRING.interactive };

  const bloqueado = estado === "pronto" && acoes.length === 0;
  const podeAprovar = acoes.some((a) => a.acao === "aprovar");
  const podeReprovar = acoes.some((a) => a.acao === "reprovar");
  const modoDecisao = podeAprovar || podeReprovar;

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
              setTentativaCarregar((t) => t + 1);
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

          <section className={styles.cardAssinatura} aria-label="Assinatura e confirmação">
            <h2 className={styles.assinaturaTitulo}>Assinatura Digital</h2>

            {bloqueado ? (
              // Branch (c): não é a vez deste ator — genérico, sem revelar quem é.
              <p className={styles.bloqueio} role="status">
                Esta prova não está aguardando uma ação sua no momento.
              </p>
            ) : (
              <>
                <AssinaturaPad ref={padRef} />
                <p className={styles.assinaturaDica}>
                  Desenhe a assinatura no quadro acima para confirmar a movimentação.
                  <button
                    type="button"
                    className={styles.linkLimpar}
                    onClick={() => padRef.current?.clear()}
                  >
                    Limpar
                  </button>
                </p>

                {modoReprovar && (
                  <div className={styles.motivoCampo}>
                    <label className={styles.motivoLabel} htmlFor={motivoId}>
                      Motivo da reprovação
                    </label>
                    <textarea
                      id={motivoId}
                      className={styles.motivoTextarea}
                      value={motivo}
                      maxLength={MOTIVO_MAX}
                      rows={3}
                      data-erro={motivoErro || undefined}
                      onChange={(e) => {
                        setMotivo(e.target.value);
                        setMotivoErro(false);
                      }}
                      placeholder="Descreva o que precisa ser corrigido"
                      aria-invalid={motivoErro || undefined}
                    />
                  </div>
                )}

                <div className={styles.acoes}>
                  {modoDecisao ? (
                    modoReprovar ? (
                      <>
                        <motion.button
                          type="button"
                          className={styles.botaoSecundario}
                          onClick={() => {
                            setModoReprovar(false);
                            setMotivoErro(false);
                          }}
                          disabled={submetendo}
                          {...toque}
                        >
                          Voltar
                        </motion.button>
                        <motion.button
                          type="button"
                          className={styles.botaoReprovar}
                          onClick={() => confirmar("reprovar")}
                          disabled={submetendo}
                          {...toque}
                        >
                          {submetendo ? "Registrando…" : "Confirmar reprovação"}
                        </motion.button>
                      </>
                    ) : (
                      <>
                        <motion.button
                          type="button"
                          className={styles.botaoReprovar}
                          onClick={() => setModoReprovar(true)}
                          disabled={submetendo || !podeReprovar}
                          {...toque}
                        >
                          Reprovar
                        </motion.button>
                        <motion.button
                          type="button"
                          className={styles.botaoConfirmar}
                          onClick={() => confirmar("aprovar")}
                          disabled={submetendo || !podeAprovar}
                          {...toque}
                        >
                          {submetendo ? "Registrando…" : "Aprovar"}
                        </motion.button>
                      </>
                    )
                  ) : (
                    <motion.button
                      type="button"
                      className={styles.botaoConfirmar}
                      onClick={() => confirmar("identificar_e_assinar")}
                      disabled={submetendo}
                      {...toque}
                    >
                      {submetendo ? "Registrando…" : "Confirmar"}
                    </motion.button>
                  )}
                </div>

                {erroSubmissao && (
                  <p className={styles.retry} role="alert">
                    {erroSubmissao}{" "}
                    <button
                      type="button"
                      className={styles.linkRetry}
                      onClick={() => ultimaAcaoRef.current && confirmar(ultimaAcaoRef.current)}
                      disabled={submetendo}
                    >
                      Tentar novamente
                    </button>
                  </p>
                )}
              </>
            )}
          </section>
        </motion.article>
      ) : null}

      {sucesso && (
        <motion.div
          className={styles.sucessoOverlay}
          role="status"
          initial={{ opacity: 0, scale: reduced ? 1 : 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{
            duration: reduced ? DURATION.instant : DURATION.short,
            ease: EASING.emphasized,
          }}
        >
          <span className={styles.sucessoPill}>
            <span aria-hidden>✓</span> Movimentação registrada
          </span>
        </motion.div>
      )}
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
