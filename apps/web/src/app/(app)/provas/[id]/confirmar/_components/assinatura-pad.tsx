"use client";

/**
 * Painel de assinatura desenhada (W3-C12) — wrapper fino sobre `react-signature-
 * canvas` (CLAUDE.md §4). Expõe um handle imperativo (`isEmpty`/`toDataURL`/
 * `clear`/`fromDataURL`) para a tela de confirmação capturar e RESTAURAR o traço
 * (resiliência — DP-5: nem falha de submissão nem reload perdem a assinatura).
 *
 * "Papel" branco com traço escuro (`backgroundColor`/`penColor`): o PNG exportado
 * fica legível em qualquer fundo (a Timeline do C13 é clara). `clearOnResize=false`
 * + área de altura FIXA: o teclado do mobile (que dispara resize ao focar o motivo)
 * NÃO apaga o que já foi desenhado.
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
      <SignatureCanvas
        ref={pad}
        penColor="#1a1a1a"
        backgroundColor="#ffffff"
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
