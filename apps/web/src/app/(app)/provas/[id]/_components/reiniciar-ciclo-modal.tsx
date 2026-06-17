"use client";

/**
 * Reinício de ciclo (W3-C15) — modal de CONFIRMAÇÃO administrativa.
 *
 * Ação administrativa exclusiva do 3Studio (RF-009/§6.6), disponível SÓ em
 * "Reprovada pelo Vendedor". Ao contrário de Cancelar, NÃO é destrutiva: a prova
 * "renasce" no início do fluxo. É também a §6.6 "Ação administrativa: Reiniciar
 * Ciclo" — só CONFIRMAÇÃO, SEM motivo e SEM assinatura desenhada (DP-2). Reusa o
 * `<MotionModal>` (C04) — animação e `prefers-reduced-motion` já são dele. Invoca
 * `reiniciarCiclo` (endpoint dedicado → motor do C11): atômico (transição +
 * incremento de ciclo juntos), idempotente (reenvio converge sem reincrementar).
 *
 * Estado fresco por abertura: o pai REMONTA este modal via `key` a cada abertura.
 * Daí a `idempotencyKey` nascer no inicializador de `useState` — UMA por
 * confirmação, reusada nas retentativas (o motor converge) — sem efeito que
 * reinicie estado.
 */
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { MotionModal } from "@/components/ui/modal/MotionModal";
import { useToast } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import type { ProvaDetalhe } from "@/lib/api/provas";
import { reiniciarCiclo } from "@/lib/api/transicoes";

import styles from "./reiniciar-ciclo-modal.module.css";

/** Mensagem ÚNICA p/ inexistente E fora-de-escopo (anti-enumeração — §11). */
const MSG_NAO_ENCONTRADA = "Prova não encontrada.";

type Props = {
  prova: ProvaDetalhe;
  aberto: boolean;
  onFechar: () => void;
  /** Sucesso: devolve a prova já em "Criada" no novo ciclo (o pai reflete + atualiza a timeline). */
  onReiniciada: (prova: ProvaDetalhe) => void;
};

export function ReiniciarCicloModal({ prova, aberto, onFechar, onReiniciada }: Props) {
  const router = useRouter();
  const toast = useToast();
  const tituloId = useId();

  const [enviando, setEnviando] = useState(false);
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  async function confirmar() {
    if (enviando) return;
    setEnviando(true);
    try {
      const atualizada = await reiniciarCiclo(prova.id, { idempotencyKey });
      toast.success("Ciclo reiniciado.");
      onReiniciada(atualizada);
    } catch (error) {
      // Timeout (AbortSignal interno): mantém o modal ABERTO p/ nova tentativa —
      // a chave reusada converge se a primeira tentativa venceu (sem reincrementar).
      if (error instanceof DOMException && error.name === "AbortError") {
        toast.error("Tempo esgotado ao reiniciar. Tente novamente.");
        return;
      }
      if (error instanceof ApiError) {
        // 404 (inexistente OU fora do escopo — anti-enumeração §11): volta à listagem.
        if (error.status === 404) {
          toast.error(MSG_NAO_ENCONTRADA);
          router.replace("/provas");
          return;
        }
        // Rede/servidor (0/5xx): mantém aberto p/ nova tentativa (chave reusada).
        if (error.status === 0 || error.status >= 500) {
          toast.error("Não foi possível reiniciar agora. Tente novamente.");
          return;
        }
        // 403/409/422 (resposta definitiva — ex.: prova não está mais reprovada): informa e fecha.
        toast.error(error.message);
        onFechar();
        return;
      }
      toast.error("Não foi possível reiniciar o ciclo.");
      onFechar();
    } finally {
      setEnviando(false);
    }
  }

  return (
    <MotionModal
      open={aberto}
      onClose={() => {
        // ESC/overlay não fecham no meio da chamada — o resultado precisa chegar.
        if (!enviando) onFechar();
      }}
      labelledBy={tituloId}
      panelClassName={styles.painel}
    >
      <h2 id={tituloId} className={styles.titulo}>
        Reiniciar ciclo
      </h2>
      <hr className={styles.separador} />
      <p className={styles.aviso}>
        A prova <strong>{prova.codigo}</strong> voltará ao status <strong>Criada</strong> e iniciará
        um <strong>novo ciclo</strong>. A <strong>rota é mantida</strong> e o{" "}
        <strong>histórico do ciclo anterior é preservado</strong> — o código e a etiqueta continuam
        os mesmos. Deseja continuar?
      </p>

      <div className={styles.acoes}>
        <button type="button" className={styles.botaoVoltar} onClick={onFechar} disabled={enviando}>
          Voltar
        </button>
        <button
          type="button"
          className={styles.botaoConfirmar}
          onClick={() => void confirmar()}
          disabled={enviando}
        >
          {enviando ? "Reiniciando…" : "Reiniciar ciclo"}
        </button>
      </div>
    </MotionModal>
  );
}
