"use client";

/**
 * Criação de Prova Digital por REQUERIMENTO (Fatia 4).
 *
 * - O NÚMERO DO REQUERIMENTO é o campo principal: ao digitá-lo (debounce), o
 *   backend resolve no ERP (Firebird) nome/cliente/vendedor, exibidos TRAVADOS
 *   (auto-preenchidos, somente leitura). Não há mais upload de arte — a imagem
 *   oficial vem do servidor de arquivos na criação.
 * - Rota SEM pré-seleção: escolha manual e consciente (RN-007 / critério §6.1).
 * - Bloqueios do servidor (requerimento inexistente/incompleto, vendedor não
 *   cadastrado, imagem indisponível) chegam como toast/erro claro na criação.
 * - Pós-criação (DP-7): toast + download automático da etiqueta + navegação;
 *   se o download falhar, painel com retry (degradação graciosa).
 * - Animações por tokens, transform/opacity apenas, zeradas sob reduced-motion.
 */
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  ROTA_LABELS,
  ROTAS_ORDEM_UI,
  baixarArteRequerimento,
  baixarEtiqueta,
  consultarRequerimento,
  criarProva,
  salvarArquivo,
  type Prova,
  type RequerimentoResolvido,
  type Rota,
} from "@/lib/api/provas";
import { DURATION, EASING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";
import { fadeRise, staggerContainer } from "@/lib/motion/variants";
import { useToast } from "@/components/ui/toast/ToastProvider";

import styles from "../nova-prova.module.css";

type Erros = Partial<Record<"requerimento" | "rota", string>>;

// Estado da resolução do requerimento no ERP (preview auto-preenchido).
type Resolucao =
  | { estado: "idle" }
  | { estado: "carregando" }
  | { estado: "ok"; dados: RequerimentoResolvido }
  | { estado: "nao_encontrado" }
  | { estado: "erro"; mensagem: string };

// COD_REQ_ART é INTEGER (int32) no ERP — o backend rejeita fora da faixa.
const COD_REQ_MAX = 2_147_483_647;

function gerarChaveIdempotencia(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function NovaProvaView() {
  const router = useRouter();
  const toast = useToast();
  const reduced = useReducedMotion();
  const idBase = useId();

  const [requerimento, setRequerimento] = useState("");
  const [resolucao, setResolucao] = useState<Resolucao>({ estado: "idle" });
  // Preview da imagem do requerimento (blob → objectURL), atrelado ao cod resolvido
  // para nunca exibir a arte de um requerimento anterior enquanto a nova carrega.
  const [arte, setArte] = useState<{ cod: number; url: string | null; erro: boolean } | null>(
    null,
  );
  // Rota SEM default: escolha manual obrigatória (RN-007 / critério §6.1).
  const [rota, setRota] = useState<Rota | null>(null);

  const [erros, setErros] = useState<Erros>({});
  const [enviando, setEnviando] = useState(false);
  const [pendenteEtiqueta, setPendenteEtiqueta] = useState<Prova | null>(null);
  const [baixandoEtiqueta, setBaixandoEtiqueta] = useState(false);

  const rotaRefs = useRef<(HTMLButtonElement | null)[]>([]);
  // Chave de idempotência (RNF-015): uma por preenchimento da tela, reusada nas
  // retentativas — reenvio após timeout converge no backend em vez de duplicar.
  const [chaveIdempotencia] = useState(gerarChaveIdempotencia);

  // Resolve o requerimento no ERP com DEBOUNCE (evita uma consulta por tecla). Todo
  // setState fica DENTRO do timer (assíncrono) — nunca no corpo do efeito.
  useEffect(() => {
    const num = requerimento.trim();
    const controller = new AbortController();
    const timer = setTimeout(() => {
      if (!/^\d+$/.test(num)) {
        setResolucao({ estado: "idle" });
        return;
      }
      if (Number(num) > COD_REQ_MAX) {
        setResolucao({ estado: "nao_encontrado" });
        return;
      }
      setResolucao({ estado: "carregando" });
      consultarRequerimento(Number(num), controller.signal)
        .then((dados) => setResolucao({ estado: "ok", dados }))
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
          if (error instanceof ApiError && error.status === 404) {
            setResolucao({ estado: "nao_encontrado" });
          } else {
            setResolucao({
              estado: "erro",
              mensagem:
                error instanceof ApiError
                  ? error.message
                  : "Falha ao consultar o requerimento. Tente novamente.",
            });
          }
        });
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [requerimento]);

  // Busca a imagem do requerimento resolvido (proxy do share → blob → objectURL).
  // Só faz fetch; o setState fica nos callbacks (nunca no corpo do efeito).
  useEffect(() => {
    if (resolucao.estado !== "ok") return;
    const cod = resolucao.dados.cod_req_art;
    const controller = new AbortController();
    let url: string | null = null;
    baixarArteRequerimento(cod, controller.signal)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setArte({ cod, url, erro: false });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setArte({ cod, url: null, erro: true });
      });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [resolucao]);

  function limparErro(campo: keyof Erros) {
    setErros((atual) => {
      if (!(campo in atual)) return atual;
      const resto = { ...atual };
      delete resto[campo];
      return resto;
    });
  }

  async function baixarEtiquetaDe(prova: Prova): Promise<boolean> {
    setBaixandoEtiqueta(true);
    try {
      const pdf = await baixarEtiqueta(prova.id);
      salvarArquivo(pdf, `etiqueta-${prova.codigo}.pdf`);
      return true;
    } catch {
      return false;
    } finally {
      setBaixandoEtiqueta(false);
    }
  }

  async function aoEnviar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (enviando || pendenteEtiqueta) return; // duplo submit nunca duplica prova
    const problemas: Erros = {};
    if (resolucao.estado !== "ok")
      problemas.requerimento = "Informe um número de requerimento válido e encontrado.";
    if (!rota) problemas.rota = "Selecione a rota de encaminhamento.";
    setErros(problemas);
    if (Object.keys(problemas).length > 0 || resolucao.estado !== "ok" || !rota) return;

    setEnviando(true);
    try {
      const prova = await criarProva({
        codReqArt: resolucao.dados.cod_req_art,
        rota,
        provaId: chaveIdempotencia, // RNF-015: retry após timeout converge
      });
      toast.success(`Prova ${prova.codigo} criada.`);
      const baixou = await baixarEtiquetaDe(prova);
      if (baixou) {
        // NÃO reabilita o botão: a navegação RSC ainda está em voo e um segundo
        // clique nesse intervalo criaria duplicata. `enviando` fica true até o unmount.
        router.push("/provas");
        return;
      }
      setPendenteEtiqueta(prova); // degradação graciosa: retry sem perder nada
      setEnviando(false);
    } catch (error) {
      const mensagem =
        error instanceof ApiError
          ? error.message
          : "Não foi possível criar a prova. Tente novamente.";
      toast.error(mensagem);
      setEnviando(false);
    }
  }

  const entrada = reduced
    ? { duration: DURATION.instant }
    : { duration: DURATION.medium, ease: EASING.emphasized };

  // Cascata dos campos do formulário (W6-C19): a grade orquestra; cada campo surge
  // em sequência. Técnica A nos nós existentes (preserva o grid).
  const gradeVar = staggerContainer(reduced);
  const campoVar = fadeRise(reduced);

  const dados = resolucao.estado === "ok" ? resolucao.dados : null;

  // ------------------------------------------------------------ pós-criação
  if (pendenteEtiqueta) {
    return (
      <section className={styles.pagina}>
        <header className={styles.cabecalho}>
          <h1 className={styles.titulo}>Nova prova Digital</h1>
        </header>
        <motion.div
          className={styles.cartaoSucesso}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={entrada}
        >
          <span className={styles.sucessoIcone} aria-hidden>
            <Check size={28} strokeWidth={3} />
          </span>
          <h2 className={styles.sucessoTitulo}>Prova {pendenteEtiqueta.codigo} criada</h2>
          <p className={styles.sucessoTexto}>
            O download automático da etiqueta falhou. A etiqueta é gerada sob demanda — nada foi
            perdido: baixe novamente abaixo.
          </p>
          <div className={styles.sucessoAcoes}>
            <button
              type="button"
              className={styles.botaoCriar}
              disabled={baixandoEtiqueta}
              onClick={() => {
                void baixarEtiquetaDe(pendenteEtiqueta).then((baixou) => {
                  if (baixou) router.push("/provas");
                  else toast.error("Download da etiqueta indisponível. Tente novamente.");
                });
              }}
            >
              {baixandoEtiqueta ? "Baixando…" : "Baixar etiqueta"}
            </button>
            <button
              type="button"
              className={styles.botaoSecundario}
              onClick={() => router.push("/provas")}
            >
              Continuar sem baixar
            </button>
          </div>
        </motion.div>
      </section>
    );
  }

  // ------------------------------------------------------------- formulário
  return (
    <section className={styles.pagina}>
      <form onSubmit={aoEnviar} noValidate className={styles.formulario}>
        <header className={styles.cabecalho}>
          <h1 className={styles.titulo}>Nova prova Digital</h1>
          <button type="submit" className={styles.botaoCriar} disabled={enviando}>
            {enviando ? "Criando…" : "Criar Prova"}
          </button>
        </header>

        <motion.div
          className={styles.cartao}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={entrada}
        >
          <motion.div className={styles.grade} variants={gradeVar} initial="hidden" animate="show">
            <motion.div className={styles.campo} variants={campoVar}>
              <label className={styles.rotulo} htmlFor={`${idBase}-requerimento`}>
                Requerimento:
              </label>
              <input
                id={`${idBase}-requerimento`}
                className={styles.entrada}
                value={requerimento}
                inputMode="numeric"
                maxLength={10}
                autoFocus
                onChange={(e) => {
                  setRequerimento(e.target.value.replace(/\D/g, ""));
                  limparErro("requerimento");
                }}
                aria-invalid={!!erros.requerimento}
                aria-describedby={`${idBase}-req-status`}
              />
              <p id={`${idBase}-req-status`} className={styles.campoStatus} role="status">
                {resolucao.estado === "carregando" && "Buscando requerimento…"}
                {resolucao.estado === "nao_encontrado" && (
                  <span className={styles.erro}>Requerimento não encontrado no ERP.</span>
                )}
                {resolucao.estado === "erro" && (
                  <span className={styles.erro}>{resolucao.mensagem}</span>
                )}
                {resolucao.estado === "ok" && (
                  <span className={styles.campoOk}>✓ Requerimento encontrado.</span>
                )}
                {erros.requerimento && resolucao.estado === "idle" && (
                  <span className={styles.erro}>{erros.requerimento}</span>
                )}
              </p>
            </motion.div>

            <motion.div className={styles.campo} variants={campoVar}>
              <span className={styles.rotulo} id={`${idBase}-nome-rotulo`}>
                Nome:
              </span>
              <input
                className={styles.entrada}
                value={dados?.nome ?? ""}
                readOnly
                aria-readonly
                aria-labelledby={`${idBase}-nome-rotulo`}
                placeholder="—"
                tabIndex={-1}
              />
            </motion.div>

            <motion.div className={styles.campo} variants={campoVar}>
              <span className={styles.rotulo} id={`${idBase}-cliente-rotulo`}>
                Cliente:
              </span>
              <input
                className={styles.entrada}
                value={dados?.nome_cliente ?? ""}
                readOnly
                aria-readonly
                aria-labelledby={`${idBase}-cliente-rotulo`}
                placeholder="—"
                tabIndex={-1}
              />
            </motion.div>

            <motion.div className={styles.campo} variants={campoVar}>
              <span className={styles.rotulo} id={`${idBase}-vendedor-rotulo`}>
                Vendedor:
              </span>
              <input
                className={styles.entrada}
                value={dados?.nome_vendedor ?? ""}
                readOnly
                aria-readonly
                aria-labelledby={`${idBase}-vendedor-rotulo`}
                placeholder="—"
                tabIndex={-1}
              />
            </motion.div>
          </motion.div>

          <div className={styles.campo}>
            <span className={styles.rotulo} id={`${idBase}-rota-rotulo`}>
              Rota:
            </span>
            <div
              role="radiogroup"
              aria-labelledby={`${idBase}-rota-rotulo`}
              aria-describedby={erros.rota ? `${idBase}-rota-erro` : undefined}
              aria-invalid={erros.rota ? true : undefined}
              className={styles.segmento}
              onKeyDown={(event) => {
                const teclas = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"];
                if (!teclas.includes(event.key)) return;
                event.preventDefault();
                const ultimo = ROTAS_ORDEM_UI.length - 1;
                const focado = rotaRefs.current.findIndex((b) => b === document.activeElement);
                const base = focado >= 0 ? focado : rota ? ROTAS_ORDEM_UI.indexOf(rota) : 0;
                let proximo: number;
                if (event.key === "Home") proximo = 0;
                else if (event.key === "End") proximo = ultimo;
                else if (event.key === "ArrowRight" || event.key === "ArrowDown")
                  proximo = (base + 1) % ROTAS_ORDEM_UI.length;
                else proximo = base <= 0 ? ultimo : base - 1;
                setRota(ROTAS_ORDEM_UI[proximo]);
                limparErro("rota");
                rotaRefs.current[proximo]?.focus();
              }}
            >
              {ROTAS_ORDEM_UI.map((opcao, indice) => {
                const ativa = rota === opcao;
                const tabStop = rota ? ativa : indice === 0;
                return (
                  <button
                    key={opcao}
                    ref={(node) => {
                      rotaRefs.current[indice] = node;
                    }}
                    type="button"
                    role="radio"
                    aria-checked={ativa}
                    tabIndex={tabStop ? 0 : -1}
                    className={styles.segmentoItem}
                    data-ativa={ativa || undefined}
                    onClick={() => {
                      setRota(opcao);
                      limparErro("rota");
                    }}
                  >
                    {ativa && (
                      <motion.span
                        layoutId={`${idBase}-rota-pill`}
                        className={styles.segmentoPill}
                        transition={
                          reduced
                            ? { duration: DURATION.instant }
                            : { duration: DURATION.short, ease: EASING.emphasized }
                        }
                        aria-hidden
                      />
                    )}
                    <span className={styles.segmentoRotulo}>{ROTA_LABELS[opcao]}</span>
                  </button>
                );
              })}
            </div>
            {erros.rota && (
              <p id={`${idBase}-rota-erro`} className={styles.erro} role="alert">
                {erros.rota}
              </p>
            )}
          </div>

          <div className={`${styles.campo} ${styles.campoArte}`}>
            <span className={styles.rotulo}>Imagem da prova:</span>
            <div className={styles.arteBox}>
              {resolucao.estado !== "ok" ? (
                <span className={styles.arteVazio}>
                  A imagem aparece aqui após informar o requerimento.
                </span>
              ) : arte && arte.cod === resolucao.dados.cod_req_art ? (
                arte.erro ? (
                  <span className={styles.arteIndisponivel}>
                    Imagem indisponível para este requerimento.
                  </span>
                ) : arte.url ? (
                  <motion.img
                    className={styles.arteImg}
                    src={arte.url}
                    alt={`Arte do requerimento ${resolucao.dados.cod_req_art}`}
                    initial={reduced ? undefined : { opacity: 0 }}
                    animate={reduced ? undefined : { opacity: 1 }}
                    transition={{ duration: DURATION.short, ease: EASING.standard }}
                  />
                ) : null
              ) : (
                <span className={styles.arteCarregando}>Carregando imagem…</span>
              )}
            </div>
          </div>
        </motion.div>
      </form>
    </section>
  );
}
