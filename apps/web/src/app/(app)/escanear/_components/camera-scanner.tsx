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
 *
 * Layout (fiel ao design): card branco em DUAS colunas — visor cinza quadrado
 * (placeholder do QR com molduras + scanline, ou o <video> da câmera) à esquerda;
 * painel "Pronto para escanear" + "Abrir câmera" e o rodapé "Última leitura / Ver
 * histórico" à direita. O visor é dimensionado pela ALTURA do card (quadrado que
 * cabe) — nunca estoura o card.
 */
import { motion } from "framer-motion";
import type { Html5Qrcode } from "html5-qrcode";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";

import styles from "../escanear.module.css";

type Estado = "pronto" | "iniciando" | "ativo" | "indisponivel";

export function CameraScanner({
  onDetectar,
  ocupado,
  rodape,
}: {
  /** Chamado com o texto lido do QR (o próprio código — C06). */
  onDetectar: (codigo: string) => void;
  /** A identificação está em curso: trava o botão e congela o feedback. */
  ocupado: boolean;
  /** Rodapé "Última leitura / Ver histórico" — renderizado dentro do card. */
  rodape: ReactNode;
}) {
  const reduced = useReducedMotion();
  const reactId = useId();
  const scannerId = `qr-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`;

  const [estado, setEstado] = useState<Estado>("pronto");
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const detectouRef = useRef(false);
  // Vida do componente: um `start()` é assíncrono (1-2 s no mobile — prompt de
  // permissão + abertura do track). Se desmontar nesse meio-tempo, este ref deixa
  // o `iniciar()` saber que precisa PARAR o track recém-aberto (senão a câmera
  // ficaria ligada em segundo plano) e não tocar estado morto.
  const vivoRef = useRef(true);

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
      vivoRef.current = false; // um start() que resolver após o unmount será parado
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
          if (detectouRef.current || !vivoRef.current) return; // só a 1ª leitura, e só se vivo
          detectouRef.current = true;
          void parar();
          onDetectar(texto);
        },
        () => {
          // callback de "frame sem QR" — silencioso (roda a cada quadro)
        },
      );
      if (!vivoRef.current) {
        // Desmontou durante o handshake do start(): o cleanup já chamou parar() com
        // o scanner AINDA iniciando — o stop() de lá lança ("not running") e é
        // engolido, então o track só foi de fato aberto AGORA. Encerra ESTE scanner
        // diretamente (não via scannerRef, que o cleanup já zerou) — a câmera nunca
        // fica ligada em segundo plano. Não toca estado morto.
        scannerRef.current = null;
        try {
          await scanner.stop();
          scanner.clear();
        } catch {
          // já parado/parando — não acionável
        }
        return;
      }
      setEstado("ativo");
    } catch {
      // Permissão negada OU nenhuma câmera: degrada — o manual segue disponível.
      await parar();
      if (vivoRef.current) setEstado("indisponivel");
    }
  }

  const toque = reduced ? {} : { whileTap: { scale: 0.97 }, transition: SPRING.interactive };
  const ativaCamera = estado === "ativo" || estado === "iniciando";

  return (
    <div className={styles.cameraCard}>
      <div className={styles.visor}>
        {/* Container do html5-qrcode (recebe o <video>) — sempre no DOM (a lib
            busca por id); escondido por CSS quando a câmera não está ativa. */}
        <div
          id={scannerId}
          className={`${styles.scanner} ${ativaCamera ? styles.scannerVisivel : styles.scannerOculto}`}
        />

        {!ativaCamera && (
          <motion.div
            className={styles.placeholder}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{
              duration: reduced ? DURATION.instant : DURATION.short,
              ease: EASING.standard,
            }}
            aria-hidden
          >
            <div className={styles.qrFrame}>
              <div className={styles.qrCard}>
                <span className={styles.scanline} />
                <QrArte />
              </div>
              <span className={`${styles.bracket} ${styles.bracketTL}`} />
              <span className={`${styles.bracket} ${styles.bracketTR}`} />
              <span className={`${styles.bracket} ${styles.bracketBL}`} />
              <span className={`${styles.bracket} ${styles.bracketBR}`} />
            </div>
            <span className={styles.visorLegenda}>Centralize o QR Code no quadro</span>
          </motion.div>
        )}
      </div>

      <div className={styles.cameraPainel}>
        <div className={styles.painelTopo}>
          {estado === "indisponivel" ? (
            <>
              <h2 className={styles.painelTitulo}>Câmera indisponível</h2>
              <p className={styles.painelTexto}>
                Não foi possível acessar a câmera. Verifique a permissão do navegador ou use o
                código manual — a aba “Manual” acima continua disponível.
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
                Aponte a câmera para o QR Code da etiqueta. A leitura é instantânea e a movimentação
                é registrada com horário e usuário.
              </p>
              <motion.button
                type="button"
                className={styles.botaoPrimario}
                onClick={() => void iniciar()}
                disabled={ocupado}
                {...toque}
              >
                <CameraIcone /> Abrir câmera
              </motion.button>
            </>
          )}
        </div>

        <div className={styles.cardRodape}>
          <hr className={styles.cardRodapeDivisor} />
          {rodape}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Arte do QR (placeholder do estado "pronto") — SVG decorativo, determinístico
// (semente fixa → sem mismatch de hidratação). Três finder patterns + módulos de
// dados + um quadrado amarelo central, como no design.
// ---------------------------------------------------------------------------
function construirModulos(): { x: number; y: number }[] {
  const N = 25; // grade de 25 módulos (viewBox 100 → passo 4)
  const ehFinder = (c: number, r: number) =>
    (c < 8 && r < 8) || (c > 16 && r < 8) || (c < 8 && r > 16);
  const ehCentro = (c: number, r: number) => c >= 9 && c <= 15 && r >= 9 && r <= 15;
  let semente = 0x6d2b79f5; // fixa → mesmo padrão no servidor e no cliente
  const proximo = () => {
    semente = (semente * 1103515245 + 12345) & 0x7fffffff;
    return semente / 0x7fffffff;
  };
  const mods: { x: number; y: number }[] = [];
  for (let r = 0; r < N; r++) {
    for (let c = 0; c < N; c++) {
      if (ehFinder(c, r) || ehCentro(c, r)) continue;
      if (proximo() > 0.52) mods.push({ x: c * 4, y: r * 4 });
    }
  }
  return mods;
}
const QR_MODULOS = construirModulos();

function QrFinder({ x, y }: { x: number; y: number }) {
  return (
    <>
      <rect x={x} y={y} width="28" height="28" rx="4" className={styles.qrModulo} />
      <rect x={x + 5} y={y + 5} width="18" height="18" rx="3" className={styles.qrVazio} />
      <rect x={x + 9} y={y + 9} width="10" height="10" rx="2" className={styles.qrModulo} />
    </>
  );
}

function QrArte() {
  return (
    <svg viewBox="0 0 100 100" className={styles.qrSvg} aria-hidden focusable="false">
      {QR_MODULOS.map((m, i) => (
        <rect key={i} x={m.x} y={m.y} width="4" height="4" className={styles.qrModulo} />
      ))}
      <QrFinder x={0} y={0} />
      <QrFinder x={72} y={0} />
      <QrFinder x={0} y={72} />
      <rect x="40" y="40" width="20" height="20" rx="5" className={styles.qrCentro} />
    </svg>
  );
}

function CameraIcone() {
  return (
    <svg
      className={styles.botaoIcone}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
    >
      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
      <circle cx="12" cy="13" r="4" />
    </svg>
  );
}
