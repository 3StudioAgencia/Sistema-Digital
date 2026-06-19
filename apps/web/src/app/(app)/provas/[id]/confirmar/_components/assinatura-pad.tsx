"use client";

/**
 * Painel de assinatura desenhada (W3-C12) — wrapper fino sobre `react-signature-
 * canvas` (CLAUDE.md §4). Expõe um handle imperativo (`isEmpty`/`toDataURL`/
 * `clear`/`fromDataURL`) para a tela de confirmação capturar e RESTAURAR o traço
 * (resiliência — DP-5: nem falha de submissão nem reload perdem a assinatura).
 *
 * Redesign da tela de assinatura (ADR-096): o canvas é TRANSPARENTE
 * (`backgroundColor: rgba(0,0,0,0)`) para que as guias do novo design — o "X", a
 * linha de base e a legenda "Assine no espaço acima da linha" — apareçam ATRÁS do
 * traço. O traço segue escuro (`penColor`), legível sobre qualquer fundo (a Timeline
 * do C13 é clara). O PNG exportado deixou de ter fundo branco sólido e passou a ter
 * fundo transparente — só a aparência muda; o conteúdo (o desenho) é idêntico.
 * `clearOnResize=false` + área de altura estável: o teclado do mobile (que dispara
 * resize ao focar o motivo) NÃO apaga o que já foi desenhado.
 */
import { forwardRef, type Ref, useImperativeHandle, useRef } from "react";
import SignatureCanvas from "react-signature-canvas";

import styles from "../confirmar.module.css";

export type AssinaturaPadHandle = {
  isEmpty: () => boolean;
  toDataURL: () => string;
  clear: () => void;
  fromDataURL: (url: string) => void;
};

export const AssinaturaPad = forwardRef(function AssinaturaPad(
  { onBegin }: { onBegin?: () => void },
  ref: Ref<AssinaturaPadHandle>,
) {
  const pad = useRef<SignatureCanvas | null>(null);

  useImperativeHandle(ref, () => ({
    isEmpty: () => pad.current?.isEmpty() ?? true,
    toDataURL: () => pad.current?.toDataURL("image/png") ?? "",
    clear: () => pad.current?.clear(),
    fromDataURL: (url: string) => {
      pad.current?.fromDataURL(url);
    },
  }));

  return (
    <div className={styles.assinaturaPad}>
      {/* Guias do design (decorativas) — atrás do canvas transparente (DP-5). */}
      <div className={styles.assinaturaGuias} aria-hidden>
        <svg className={styles.assinaturaX} viewBox="0 0 24 24" fill="none">
          <path
            d="M5 5 19 19M19 5 5 19"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
        <span className={styles.assinaturaLinha} />
        <span className={styles.assinaturaLegenda}>Assine no espaço acima da linha</span>
      </div>
      <SignatureCanvas
        ref={pad}
        penColor="#1a1a1a"
        backgroundColor="rgba(0,0,0,0)"
        clearOnResize={false}
        onBegin={onBegin}
        canvasProps={{
          className: styles.assinaturaCanvasEl,
          "aria-label": "Área de assinatura — desenhe aqui",
        }}
      />
    </div>
  );
});
