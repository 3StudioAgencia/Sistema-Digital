"use client";

/**
 * Configurações do sistema (W2-C09) — exclusiva do 3Studio (Matriz §7).
 *
 * Tela de cards no padrão do design (cartão branco + "Salvar" POR card — save
 * granular). Implementa os settings reais do RF-022 (DP-6): tempo de atraso
 * (RN-008/US-016) e template de etiqueta (RN-011/DP-5: padrão ou sobrescrita dos
 * 5 parâmetros do C06). Sem cache (DP-4): salvar reflete imediatamente.
 *
 * Acesso: o proxy (C05) já gateia a rota ao admin; em profundidade, o GET/PUT
 * respondem 403 a não-admin → estado "restrito" (a UI não confia só no proxy).
 *
 * Animações sobre os tokens (GPU — transform/opacity), instantâneas sob
 * prefers-reduced-motion.
 */
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useRef, useState } from "react";

import { Dropdown } from "@/components/ui/select/Dropdown";
import { useToast } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import {
  CHAVE_DELAY,
  CHAVE_ETIQUETA,
  FONTES_ETIQUETA,
  FONTE_LABELS,
  acharConfig,
  listarConfiguracoes,
  salvarConfiguracao,
  type Configuracao,
  type EtiquetaTemplateValor,
  type FonteEtiqueta,
  type ModoEtiqueta,
} from "@/lib/api/configuracoes";
import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";

import styles from "../configuracoes.module.css";

type Estado = "carregando" | "pronto" | "erro" | "restrito";

const ETIQUETA_FALLBACK: EtiquetaTemplateValor = {
  modo: "padrao",
  largura: 95,
  altura: 55,
  margem: 3,
  fonte: "helvetica",
  qr_zona_quieta_modulos: 2,
};

function lerDelay(config: Configuracao | undefined): number {
  const v = config?.valor ?? config?.default;
  return typeof v === "number" ? v : 48;
}

function lerEtiqueta(config: Configuracao | undefined): EtiquetaTemplateValor {
  const v = config?.valor ?? config?.default;
  return v && typeof v === "object"
    ? { ...ETIQUETA_FALLBACK, ...(v as Partial<EtiquetaTemplateValor>) }
    : ETIQUETA_FALLBACK;
}

export function ConfiguracoesView() {
  const reduced = useReducedMotion();
  const toast = useToast();

  const [estado, setEstado] = useState<Estado>("carregando");
  const [configs, setConfigs] = useState<Configuracao[]>([]);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    listarConfiguracoes(controller.signal)
      .then((cs) => {
        setConfigs(cs);
        setEstado("pronto");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        // 403 = não-3Studio (defesa em profundidade; o proxy já redireciona).
        if (error instanceof ApiError && error.status === 403) {
          setEstado("restrito");
          return;
        }
        setEstado("erro");
      });
    return () => controller.abort();
  }, [tentativa]);

  async function aoSalvar(chave: string, valor: unknown): Promise<boolean> {
    try {
      const atualizada = await salvarConfiguracao(chave, valor);
      setConfigs((cs) => cs.map((c) => (c.chave === chave ? atualizada : c)));
      toast.success("Configurações salvas.");
      return true;
    } catch (error) {
      const msg =
        error instanceof ApiError ? error.message : "Não foi possível salvar. Tente novamente.";
      toast.error(msg);
      return false;
    }
  }

  const delayConfig = acharConfig(configs, CHAVE_DELAY);
  const etiquetaConfig = acharConfig(configs, CHAVE_ETIQUETA);

  return (
    <section className={styles.pagina} aria-label="Configurações do sistema">
      <h1 className={styles.titulo}>Configurações do sistema</h1>

      {estado === "carregando" ? (
        <div className={styles.lista} aria-hidden>
          <div className={`${styles.card} ${styles.skeleton}`} />
          <div className={`${styles.card} ${styles.skeleton}`} />
        </div>
      ) : estado === "restrito" ? (
        <p className={styles.aviso} role="alert">
          Acesso restrito: as configurações do sistema são exclusivas do 3Studio.
        </p>
      ) : estado === "erro" ? (
        <p className={styles.aviso} role="alert">
          Não foi possível carregar as configurações.{" "}
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
      ) : (
        <div className={styles.lista}>
          <CardDelay config={delayConfig} aoSalvar={aoSalvar} reduced={reduced} ordem={0} />
          <CardEtiqueta config={etiquetaConfig} aoSalvar={aoSalvar} reduced={reduced} ordem={1} />
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Card genérico (título + descrição + campos + "Salvar" próprio)
// ---------------------------------------------------------------------------
type CardProps = {
  titulo: string;
  descricao: string;
  children: React.ReactNode;
  onSalvar: () => void;
  salvando: boolean;
  reduced: boolean;
  ordem: number;
};

function Card({ titulo, descricao, children, onSalvar, salvando, reduced, ordem }: CardProps) {
  const tituloId = useId();
  const toque = reduced ? {} : { whileTap: { scale: 0.97 }, transition: SPRING.interactive };
  return (
    <motion.section
      className={styles.card}
      aria-labelledby={tituloId}
      initial={{ opacity: 0, y: reduced ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: reduced ? DURATION.instant : DURATION.medium,
        ease: EASING.emphasized,
        delay: reduced ? 0 : ordem * 0.06,
      }}
    >
      <div className={styles.cardMain}>
        <h2 id={tituloId} className={styles.cardTitulo}>
          {titulo}
        </h2>
        <p className={styles.cardDescricao}>{descricao}</p>
        <div className={styles.cardCampos}>{children}</div>
      </div>
      <div className={styles.cardAcao}>
        <motion.button
          type="button"
          className={styles.botaoSalvar}
          onClick={onSalvar}
          disabled={salvando}
          {...toque}
        >
          {salvando ? "Salvando…" : "Salvar"}
        </motion.button>
      </div>
    </motion.section>
  );
}

// ---------------------------------------------------------------------------
// Tempo de atraso (RF-022a / RN-008 / US-016)
// ---------------------------------------------------------------------------
function validarDelay(valor: string): string | null {
  const texto = valor.trim();
  if (!texto) return "Informe o tempo em horas úteis.";
  if (!/^\d+$/.test(texto)) return "Use apenas números inteiros.";
  const n = Number(texto);
  if (n < 1) return "O tempo deve ser maior que zero.";
  if (n > 9999) return "O tempo deve ser no máximo 9999 horas úteis.";
  return null;
}

function CardDelay({
  config,
  aoSalvar,
  reduced,
  ordem,
}: {
  config: Configuracao | undefined;
  aoSalvar: (chave: string, valor: unknown) => Promise<boolean>;
  reduced: boolean;
  ordem: number;
}) {
  const idBase = useId();
  const [valor, setValor] = useState(() => String(lerDelay(config)));
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  async function salvar() {
    const problema = validarDelay(valor);
    if (problema) {
      setErro(problema);
      return;
    }
    setSalvando(true);
    await aoSalvar(CHAVE_DELAY, Number(valor.trim()));
    setSalvando(false);
  }

  return (
    <Card
      titulo="Tempo de atraso"
      descricao={config?.descricao ?? ""}
      onSalvar={salvar}
      salvando={salvando}
      reduced={reduced}
      ordem={ordem}
    >
      <div className={styles.campo}>
        <label className={styles.rotulo} htmlFor={`${idBase}-delay`}>
          Tempo (horas úteis)
        </label>
        <input
          id={`${idBase}-delay`}
          className={styles.entrada}
          inputMode="numeric"
          value={valor}
          aria-invalid={!!erro}
          aria-describedby={erro ? `${idBase}-delay-erro` : undefined}
          onChange={(e) => {
            setValor(e.target.value);
            setErro(null);
          }}
        />
        {erro && (
          <p id={`${idBase}-delay-erro`} className={styles.erro} role="alert">
            {erro}
          </p>
        )}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Template de etiqueta (RF-022b / RN-011 / DP-5)
// ---------------------------------------------------------------------------
type CampoNum = "largura" | "altura" | "margem" | "qr_zona_quieta_modulos";

const LIMITES: Record<CampoNum, { min: number; max: number; inteiro: boolean; rotulo: string }> = {
  largura: { min: 40, max: 300, inteiro: false, rotulo: "Largura (mm)" },
  altura: { min: 20, max: 300, inteiro: false, rotulo: "Altura (mm)" },
  margem: { min: 0, max: 20, inteiro: false, rotulo: "Margem (mm)" },
  qr_zona_quieta_modulos: { min: 0, max: 10, inteiro: true, rotulo: "Zona quieta do QR" },
};

function validarNum(campo: CampoNum, valor: string): string | null {
  const texto = valor.trim();
  const { min, max, inteiro, rotulo } = LIMITES[campo];
  if (!texto) return `${rotulo}: obrigatório.`;
  if (inteiro ? !/^\d+$/.test(texto) : !/^\d+([.,]\d+)?$/.test(texto))
    return `${rotulo}: ${inteiro ? "número inteiro" : "número"} inválido.`;
  const n = Number(texto.replace(",", "."));
  if (n < min || n > max) return `${rotulo}: entre ${min} e ${max}.`;
  return null;
}

function CardEtiqueta({
  config,
  aoSalvar,
  reduced,
  ordem,
}: {
  config: Configuracao | undefined;
  aoSalvar: (chave: string, valor: unknown) => Promise<boolean>;
  reduced: boolean;
  ordem: number;
}) {
  const idBase = useId();
  const inicial = lerEtiqueta(config);
  const [modo, setModo] = useState<ModoEtiqueta>(inicial.modo);
  const [campos, setCampos] = useState<Record<CampoNum, string>>({
    largura: String(inicial.largura),
    altura: String(inicial.altura),
    margem: String(inicial.margem),
    qr_zona_quieta_modulos: String(inicial.qr_zona_quieta_modulos),
  });
  const [fonte, setFonte] = useState<FonteEtiqueta>(inicial.fonte);
  const [erros, setErros] = useState<Partial<Record<CampoNum, string>>>({});
  const [salvando, setSalvando] = useState(false);

  // Validação só vale no modo personalizado (no padrão os campos não se aplicam).
  function errosPersonalizado(): Partial<Record<CampoNum, string>> {
    const e: Partial<Record<CampoNum, string>> = {};
    for (const campo of Object.keys(LIMITES) as CampoNum[]) {
      const problema = validarNum(campo, campos[campo]);
      if (problema) e[campo] = problema;
    }
    return e;
  }

  async function salvar() {
    if (modo === "padrao") {
      // Padrão: grava os defaults do C06 (sobrescritas não se aplicam) — limpa
      // quaisquer dimensões personalizadas antigas da linha persistida.
      setSalvando(true);
      await aoSalvar(CHAVE_ETIQUETA, { ...ETIQUETA_FALLBACK, modo: "padrao" });
      setSalvando(false);
      return;
    }
    const e = errosPersonalizado();
    setErros(e);
    if (Object.keys(e).length > 0) return;
    const valor: EtiquetaTemplateValor = {
      modo: "personalizado",
      largura: Number(campos.largura.replace(",", ".")),
      altura: Number(campos.altura.replace(",", ".")),
      margem: Number(campos.margem.replace(",", ".")),
      fonte,
      qr_zona_quieta_modulos: Number(campos.qr_zona_quieta_modulos),
    };
    setSalvando(true);
    await aoSalvar(CHAVE_ETIQUETA, valor);
    setSalvando(false);
  }

  function alterarCampo(campo: CampoNum, valor: string) {
    setCampos((c) => ({ ...c, [campo]: valor }));
    setErros((e) => {
      if (!(campo in e)) return e;
      const resto = { ...e };
      delete resto[campo];
      return resto;
    });
  }

  return (
    <Card
      titulo="Template de etiqueta"
      descricao={config?.descricao ?? ""}
      onSalvar={salvar}
      salvando={salvando}
      reduced={reduced}
      ordem={ordem}
    >
      <div className={styles.campo}>
        <span className={styles.rotulo} id={`${idBase}-modo`}>
          Modo
        </span>
        <Segmento value={modo} onChange={setModo} labelledBy={`${idBase}-modo`} reduced={reduced} />
      </div>

      <AnimatePresence initial={false}>
        {modo === "personalizado" && (
          <motion.div
            className={styles.gradeEtiqueta}
            initial={{ opacity: 0, y: reduced ? 0 : -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: reduced ? 0 : -6 }}
            transition={{
              duration: reduced ? DURATION.instant : DURATION.short,
              ease: EASING.standard,
            }}
          >
            {(Object.keys(LIMITES) as CampoNum[]).map((campo) =>
              campo === "qr_zona_quieta_modulos" ? null : (
                <div className={styles.campo} key={campo}>
                  <label className={styles.rotulo} htmlFor={`${idBase}-${campo}`}>
                    {LIMITES[campo].rotulo}
                  </label>
                  <input
                    id={`${idBase}-${campo}`}
                    className={styles.entrada}
                    inputMode="decimal"
                    value={campos[campo]}
                    aria-invalid={!!erros[campo]}
                    aria-describedby={erros[campo] ? `${idBase}-${campo}-erro` : undefined}
                    onChange={(e) => alterarCampo(campo, e.target.value)}
                  />
                  {erros[campo] && (
                    <p id={`${idBase}-${campo}-erro`} className={styles.erro} role="alert">
                      {erros[campo]}
                    </p>
                  )}
                </div>
              ),
            )}

            <div className={styles.campo}>
              <span className={styles.rotulo} id={`${idBase}-fonte`}>
                Fonte
              </span>
              <div className={styles.slotSelect}>
                <Dropdown
                  value={fonte}
                  opcoes={FONTES_ETIQUETA.map((f) => ({ value: f, label: FONTE_LABELS[f] }))}
                  onChange={(v) => setFonte(v)}
                  labelledBy={`${idBase}-fonte`}
                  variante="claro"
                />
              </div>
            </div>

            <div className={styles.campo}>
              <label className={styles.rotulo} htmlFor={`${idBase}-qr`}>
                {LIMITES.qr_zona_quieta_modulos.rotulo}
              </label>
              <input
                id={`${idBase}-qr`}
                className={styles.entrada}
                inputMode="numeric"
                value={campos.qr_zona_quieta_modulos}
                aria-invalid={!!erros.qr_zona_quieta_modulos}
                aria-describedby={erros.qr_zona_quieta_modulos ? `${idBase}-qr-erro` : undefined}
                onChange={(e) => alterarCampo("qr_zona_quieta_modulos", e.target.value)}
              />
              {erros.qr_zona_quieta_modulos && (
                <p id={`${idBase}-qr-erro`} className={styles.erro} role="alert">
                  {erros.qr_zona_quieta_modulos}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Segmented control (Padrão | Personalizado) — pílula deslizante (GPU)
// ---------------------------------------------------------------------------
const MODOS: { value: ModoEtiqueta; label: string }[] = [
  { value: "padrao", label: "Padrão" },
  { value: "personalizado", label: "Personalizado" },
];

function Segmento({
  value,
  onChange,
  labelledBy,
  reduced,
}: {
  value: ModoEtiqueta;
  onChange: (v: ModoEtiqueta) => void;
  labelledBy: string;
  reduced: boolean;
}) {
  const pillId = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  return (
    <div
      className={styles.segmento}
      role="radiogroup"
      aria-labelledby={labelledBy}
      onKeyDown={(event) => {
        // Padrão WAI-ARIA de radiogroup (espelha o segmented de Rota do C06):
        // setas movem E selecionam (com wrap); Home/End vão aos extremos.
        const teclas = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"];
        if (!teclas.includes(event.key)) return;
        event.preventDefault();
        const ultimo = MODOS.length - 1;
        const focado = refs.current.findIndex((b) => b === document.activeElement);
        const base = focado >= 0 ? focado : MODOS.findIndex((m) => m.value === value);
        let proximo: number;
        if (event.key === "Home") proximo = 0;
        else if (event.key === "End") proximo = ultimo;
        else if (event.key === "ArrowRight" || event.key === "ArrowDown")
          proximo = (base + 1) % MODOS.length;
        else proximo = base <= 0 ? ultimo : base - 1;
        onChange(MODOS[proximo].value);
        refs.current[proximo]?.focus();
      }}
    >
      {MODOS.map((opcao, indice) => {
        const ativa = value === opcao.value;
        return (
          <button
            key={opcao.value}
            ref={(node) => {
              refs.current[indice] = node;
            }}
            type="button"
            role="radio"
            aria-checked={ativa}
            // Roving tabindex: só a opção ativa é tab stop (há sempre uma).
            tabIndex={ativa ? 0 : -1}
            className={styles.segmentoItem}
            data-ativa={ativa || undefined}
            onClick={() => onChange(opcao.value)}
          >
            {ativa && (
              <motion.span
                layoutId={`${pillId}-pill`}
                className={styles.segmentoPill}
                transition={
                  reduced
                    ? { duration: DURATION.instant }
                    : { duration: DURATION.short, ease: EASING.emphasized }
                }
                aria-hidden
              />
            )}
            <span className={styles.segmentoRotulo}>{opcao.label}</span>
          </button>
        );
      })}
    </div>
  );
}
