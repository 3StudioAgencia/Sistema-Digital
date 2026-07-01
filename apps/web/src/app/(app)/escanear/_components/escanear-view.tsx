"use client";

import { motion } from "framer-motion";
import { Camera, KeyRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { Stagger, StaggerItem } from "@/components/ui/motion";
import { useToast } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import { identificarProva } from "@/lib/api/escaneamento";
import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";
import { mascararCodigo, validarCodigo } from "@/lib/provas/codigo";

import styles from "../escanear.module.css";
import { CameraScanner } from "./camera-scanner";

type Modo = "camera" | "manual";

const MSG_NAO_ENCONTRADA = "Prova não encontrada.";

export function EscanearView() {
  const reduced = useReducedMotion();
  const router = useRouter();
  const toast = useToast();

  const [modo, setModo] = useState<Modo>("camera");
  const [buscando, setBuscando] = useState(false);
  const [sucesso, setSucesso] = useState(false);
  const [ultimaLeitura, setUltimaLeitura] = useState<number | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  async function identificar(codigoBruto: string): Promise<void> {
    if (buscando) return;
    setBuscando(true);
    try {
      const prova = await identificarProva(codigoBruto);
      setUltimaLeitura(Date.now());
      setSucesso(true);
      const irParaConfirmacao = () => router.push(`/provas/${prova.id}/confirmar`);
      if (reduced) irParaConfirmacao();
      else timeoutRef.current = setTimeout(irParaConfirmacao, 450);
    } catch (error) {
      setBuscando(false);
      if (error instanceof ApiError && error.status === 404) {
        toast.error(MSG_NAO_ENCONTRADA);
      } else if (error instanceof ApiError && error.status === 429) {
        toast.error(error.message);
      } else {
        toast.error("Não foi possível identificar a prova. Tente novamente.");
      }
    }
  }

  const rotuloLeitura = rotuloUltimaLeitura(ultimaLeitura);
  function verHistorico() {
    toast.success("O histórico de leituras chega com a timeline da prova (C13).");
  }

  return (
    <Stagger className={styles.pagina}>
      <section aria-label="Escanear prova" style={{ display: "contents" }}>
        <StaggerItem>
          <header className={styles.cabecalho}>
            <h1 className={styles.titulo}>Escanear prova</h1>
            <p className={styles.subtitulo}>
              Leia o QR Code da etiqueta com a câmera ou insira o código manualmente para confirmar
              a próxima movimentação.
            </p>
          </header>
        </StaggerItem>

        <StaggerItem>
          <ModoToggle modo={modo} onChange={setModo} reduced={reduced} />
        </StaggerItem>

        <StaggerItem className={styles.conteudo}>
          {modo === "camera" ? (
            <CameraScanner
              onDetectar={identificar}
              ocupado={buscando}
              rodape={<Rodape rotulo={rotuloLeitura} onHistorico={verHistorico} />}
            />
          ) : (
            <EntradaManual
              onBuscar={identificar}
              ocupado={buscando}
              reduced={reduced}
              rodape={<Rodape rotulo={rotuloLeitura} onHistorico={verHistorico} />}
            />
          )}

          {sucesso && (
            <motion.div
              className={styles.sucessoFlash}
              role="status"
              initial={{ opacity: 0, scale: reduced ? 1 : 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{
                duration: reduced ? DURATION.instant : DURATION.short,
                ease: EASING.emphasized,
              }}
            >
              <span className={styles.sucessoPill}>
                <span aria-hidden>✓</span> Prova identificada
              </span>
            </motion.div>
          )}
        </StaggerItem>
      </section>
    </Stagger>
  );
}

function Rodape({ rotulo, onHistorico }: { rotulo: string; onHistorico: () => void }) {
  return (
    <div className={styles.rodapeLinha}>
      <span className={styles.rodapeInfo}>{rotulo}</span>
      <button type="button" className={styles.rodapeLink} onClick={onHistorico}>
        Ver histórico →
      </button>
    </div>
  );
}

function rotuloUltimaLeitura(quando: number | null): string {
  if (quando === null) return "Nenhuma leitura nesta sessão";
  const minutos = Math.max(0, Math.round((Date.now() - quando) / 60000));
  if (minutos === 0) return "Última leitura agora";
  return `Última leitura há ${minutos} min`;
}

const MODOS: { value: Modo; label: string; Icone: typeof Camera }[] = [
  { value: "camera", label: "Câmera", Icone: Camera },
  { value: "manual", label: "Manual", Icone: KeyRound },
];

function ModoToggle({
  modo,
  onChange,
  reduced,
}: {
  modo: Modo;
  onChange: (m: Modo) => void;
  reduced: boolean;
}) {
  const pillId = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  return (
    <div
      className={styles.toggle}
      role="radiogroup"
      aria-label="Modo de leitura"
      onKeyDown={(event) => {
        const teclas = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"];
        if (!teclas.includes(event.key)) return;
        event.preventDefault();
        const ultimo = MODOS.length - 1;
        const focado = refs.current.findIndex((b) => b === document.activeElement);
        const base = focado >= 0 ? focado : MODOS.findIndex((m) => m.value === modo);
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
        const ativa = modo === opcao.value;
        const Icone = opcao.Icone;
        return (
          <button
            key={opcao.value}
            ref={(node) => {
              refs.current[indice] = node;
            }}
            type="button"
            role="radio"
            aria-checked={ativa}
            tabIndex={ativa ? 0 : -1}
            className={styles.toggleItem}
            data-ativa={ativa || undefined}
            onClick={() => onChange(opcao.value)}
          >
            {ativa && (
              <motion.span
                layoutId={`${pillId}-pill`}
                className={styles.togglePill}
                transition={
                  reduced
                    ? { duration: DURATION.instant }
                    : { duration: DURATION.short, ease: EASING.emphasized }
                }
                aria-hidden
              />
            )}
            <span className={styles.toggleRotulo}>
              <Icone className={styles.toggleIcone} aria-hidden /> {opcao.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function EntradaManual({
  onBuscar,
  ocupado,
  reduced,
  rodape,
}: {
  onBuscar: (codigo: string) => void;
  ocupado: boolean;
  reduced: boolean;
  rodape: ReactNode;
}) {
  const idBase = useId();
  const [codigo, setCodigo] = useState("");
  const valido = validarCodigo(codigo);
  const toque = reduced ? {} : { whileTap: { scale: 0.98 }, transition: SPRING.interactive };

  function submeter(event: React.FormEvent) {
    event.preventDefault();
    if (!valido || ocupado) return;
    onBuscar(codigo);
  }

  return (
    <form className={styles.manualCard} onSubmit={submeter} aria-label="Inserir código manualmente">
      <div className={styles.manualBloco}>
        <h2 className={styles.manualTitulo}>Inserir código manualmente</h2>
        <p className={styles.manualTexto}>
          Digite o código que aparece abaixo do QR Code da etiqueta. A movimentação será registrada
          após a confirmação.
        </p>

        <div className={styles.inputWrap}>
          <input
            id={`${idBase}-codigo`}
            className={styles.input}
            value={codigo}
            onChange={(e) => setCodigo(mascararCodigo(e.target.value))}
            placeholder="PRV-AAAA-MM-XXXXXX"
            inputMode="text"
            autoCapitalize="characters"
            autoCorrect="off"
            autoComplete="off"
            spellCheck={false}
            aria-label="Código da prova"
          />
        </div>

        <motion.button
          type="submit"
          className={styles.botaoPrimario}
          disabled={!valido || ocupado}
          {...toque}
        >
          {ocupado ? "Buscando…" : "Buscar prova →"}
        </motion.button>

        <div className={styles.cardRodape}>
          <hr className={styles.cardRodapeDivisor} />
          {rodape}
        </div>
      </div>
    </form>
  );
}
