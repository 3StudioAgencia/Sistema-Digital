"use client";

/**
 * Leitor de QR por câmera (W3-C10) — in-app, sem app externo (RF-004).
 *
 * Usa `html5-qrcode` (stack do CLAUDE.md §4) via import DINÂMICO client-only (a
 * lib toca `navigator`/DOM e não pode entrar no bundle SSR). A câmera só abre por
 * GESTO do usuário ("Abrir câmera") — exigência do `getUserMedia` no mobile e
 * fiel ao design ("Pronto para escanear"). Degradação graciosa (RNF-014):
 * permissão negada / sem câmera NÃO bloqueia a tela — o componente mostra o aviso
 * e o campo manual segue acessível (o toggle nunca some). Lê o QR em tempo real
 * (≤ 2 s — RNF-002); o payload é o PRÓPRIO código (C06), repassado intacto.
 */
import { motion } from "framer-motion";
import type { Html5Qrcode } from "html5-qrcode";
import { useEffect, useId, useRef, useState } from "react";

import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";

import styles from "../escanear.module.css";

type Estado = "pronto" | "iniciando" | "ativo" | "indisponivel";

export function CameraScanner({
  onDetectar,
  ocupado,
}: {
  /** Chamado com o texto lido do QR (o próprio código — C06). */
  onDetectar: (codigo: string) => void;
  /** A identificação está em curso: trava o botão e congela o feedback. */
  ocupado: boolean;
}) {
  const reduced = useReducedMotion();
  const reactId = useId();
  const scannerId = `qr-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`;

  const [estado, setEstado] = useState<Estado>("pronto");
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const detectouRef = useRef(false);

  async function parar(): Promise<void> {
    const scanner = scannerRef.current;
    scannerRef.current = null;
    if (!scanner) return;
    try {
      await scanner.stop();
      scanner.clear();
    } catch {
      // já parado / parando — não é erro acionável
    }
  }

  // Para a câmera ao desmontar (trocar para Manual desmonta este componente —
  // render condicional no view): nunca deixa a câmera ligada em segundo plano.
  useEffect(() => {
    return () => {
      void parar();
    };
  }, []);

  async function iniciar(): Promise<void> {
    if (estado === "iniciando" || estado === "ativo") return;
    detectouRef.current = false;
    setEstado("iniciando");
    try {
      const { Html5Qrcode, Html5QrcodeSupportedFormats } = await import("html5-qrcode");
      const scanner = new Html5Qrcode(scannerId, {
        formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
        verbose: false,
      });
      scannerRef.current = scanner;
      await scanner.start(
        { facingMode: "environment" }, // câmera traseira no celular (RF-029)
        {
          fps: 10,
          qrbox: (w: number, h: number) => {
            const lado = Math.floor(Math.min(w, h) * 0.7);
            return { width: lado, height: lado };
          },
        },
        (texto) => {
          if (detectouRef.current) return; // só a primeira leitura conta
          detectouRef.current = true;
          void parar();
          onDetectar(texto);
        },
        () => {
          // callback de "frame sem QR" — silencioso (roda a cada quadro)
        },
      );
      setEstado("ativo");
    } catch {
      // Permissão negada OU nenhuma câmera: degrada — o manual segue disponível.
      await parar();
      setEstado("indisponivel");
    }
  }

  const toque = reduced ? {} : { whileTap: { scale: 0.97 }, transition: SPRING.interactive };
  const ativaCamera = estado === "ativo" || estado === "iniciando";

  return (
    <div className={styles.cameraCard}>
      <div className={styles.visorCol}>
        {/* Container do html5-qrcode (recebe o <video>); visível só com a câmera
            ativa. Mantido SEMPRE no DOM (a lib busca por id) — escondido por CSS
            no estado "pronto" para não empurrar o layout. */}
        <div className={`${styles.visor} ${ativaCamera ? styles.visorAtivo : styles.visorOculto}`}>
          <div id={scannerId} className={styles.scanner} />
          <span className={styles.visorLegenda}>Centralize o QR Code no quadro</span>
        </div>

        {!ativaCamera && (
          <motion.div
            className={styles.visorPlaceholder}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{
              duration: reduced ? DURATION.instant : DURATION.short,
              ease: EASING.standard,
            }}
            aria-hidden
          >
            <div className={styles.visorMoldura}>
              <span className={styles.visorIcone}>▣</span>
            </div>
            <span className={styles.visorLegenda}>Centralize o QR Code no quadro</span>
          </motion.div>
        )}
      </div>

      <div className={styles.cameraPainel}>
        {estado === "indisponivel" ? (
          <>
            <h2 className={styles.painelTitulo}>Câmera indisponível</h2>
            <p className={styles.painelTexto}>
              Não foi possível acessar a câmera. Verifique a permissão do navegador ou use o código
              manual — a aba “Manual” acima continua disponível.
            </p>
            <motion.button
              type="button"
              className={styles.botaoSecundario}
              onClick={() => setEstado("pronto")}
              {...toque}
            >
              Tentar novamente
            </motion.button>
          </>
        ) : ativaCamera ? (
          <>
            <h2 className={styles.painelTitulo}>Escaneando…</h2>
            <p className={styles.painelTexto}>
              Aponte para o QR Code da etiqueta. A leitura é instantânea e a movimentação é
              registrada com horário e usuário.
            </p>
            <motion.button
              type="button"
              className={styles.botaoSecundario}
              onClick={() => {
                void parar();
                setEstado("pronto");
              }}
              disabled={ocupado}
              {...toque}
            >
              Parar
            </motion.button>
          </>
        ) : (
          <>
            <h2 className={styles.painelTitulo}>Pronto para escanear</h2>
            <p className={styles.painelTexto}>
              Aponte a câmera para o QR Code da etiqueta. A leitura é instantânea e a movimentação é
              registrada com horário e usuário.
            </p>
            <motion.button
              type="button"
              className={styles.botaoPrimario}
              onClick={() => void iniciar()}
              disabled={ocupado}
              {...toque}
            >
              Abrir câmera
            </motion.button>
          </>
        )}
      </div>
    </div>
  );
}
