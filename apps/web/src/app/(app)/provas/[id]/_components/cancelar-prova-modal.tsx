"use client";

/**
 * Cancelamento de prova (W3-C14) — modal de confirmação DESTRUTIVA.
 *
 * Ação administrativa exclusiva do 3Studio (RF-011/§6.6), TERMINAL e IRREVERSÍVEL
 * (RN-005): exige um MOTIVO (validado no front E no back) e avisa explicitamente
 * que a prova não poderá ser reativada. Reusa o `<MotionModal>` (C04) — animação e
 * `prefers-reduced-motion` já são dele. Invoca `cancelarProva` (endpoint dedicado
 * → motor do C11): atômico, idempotente, SEM assinatura desenhada (DP-2). Espelha
 * o padrão destrutivo do C04 (confirmar-status-modal): `enviando` no componente,
 * `onClose` travado durante a chamada para o resultado chegar, erro vira toast.
 *
 * Estado fresco por abertura: o pai REMONTA este modal via `key` a cada abertura
 * (mesma técnica do usuario-form-modal). Daí a `idempotencyKey` nascer no
 * inicializador de `useState` — UMA por confirmação, reusada nas retentativas
 * (o motor converge — ADR-068) — sem efeito que reinicie estado.
 */
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { MotionModal } from "@/components/ui/modal/MotionModal";
import { useToast } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import type { ProvaDetalhe } from "@/lib/api/provas";
import { cancelarProva } from "@/lib/api/transicoes";

import styles from "./cancelar-prova-modal.module.css";

const MOTIVO_MAX = 500;
/** Mensagem ÚNICA p/ inexistente E fora-de-escopo (anti-enumeração — §11). */
const MSG_NAO_ENCONTRADA = "Prova não encontrada.";

type Props = {
  prova: ProvaDetalhe;
  aberto: boolean;
  onFechar: () => void;
  /** Sucesso: devolve a prova já no estado Cancelada (o pai reflete + atualiza a timeline). */
  onCancelada: (prova: ProvaDetalhe) => void;
};

export function CancelarProvaModal({ prova, aberto, onFechar, onCancelada }: Props) {
  const router = useRouter();
  const toast = useToast();
  const tituloId = useId();
  const motivoId = useId();

  const [motivo, setMotivo] = useState("");
  const [tocado, setTocado] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  const motivoValido = motivo.trim().length > 0;

  async function confirmar() {
    if (enviando) return;
    if (!motivoValido) {
      setTocado(true);
      return;
    }
    setEnviando(true);
    try {
      const atualizada = await cancelarProva(prova.id, {
        motivo: motivo.trim(),
        idempotencyKey,
      });
      toast.success("Prova cancelada.");
      onCancelada(atualizada);
    } catch (error) {
      // Timeout (AbortSignal interno): mantém o modal ABERTO p/ nova tentativa —
      // a chave reusada converge se a primeira tentativa venceu (ADR-068).
      if (error instanceof DOMException && error.name === "AbortError") {
        toast.error("Tempo esgotado ao cancelar. Tente novamente.");
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
          toast.error("Não foi possível cancelar agora. Tente novamente.");
          return;
        }
        // 403/409/422 (resposta definitiva — ex.: prova já terminal): informa e fecha.
        toast.error(error.message);
        onFechar();
        return;
      }
      toast.error("Não foi possível cancelar a prova.");
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
        Cancelar prova
      </h2>
      <hr className={styles.separador} />
      <p className={styles.aviso}>
        Esta ação é <strong>irreversível</strong>. A prova <strong>{prova.codigo}</strong> será
        marcada como <strong>Cancelada</strong> e não poderá ser reativada — se precisar, crie uma
        nova prova. O histórico é preservado.
      </p>

      <div className={styles.campo}>
        <label htmlFor={motivoId} className={styles.label}>
          Motivo do cancelamento
        </label>
        <textarea
          id={motivoId}
          className={styles.textarea}
          value={motivo}
          onChange={(event) => setMotivo(event.target.value)}
          onBlur={() => setTocado(true)}
          rows={3}
          maxLength={MOTIVO_MAX}
          disabled={enviando}
          data-erro={tocado && !motivoValido ? "" : undefined}
          aria-invalid={tocado && !motivoValido}
          aria-describedby={tocado && !motivoValido ? `${motivoId}-erro` : undefined}
          placeholder="Descreva por que esta prova está sendo cancelada"
        />
        {tocado && !motivoValido && (
          <p id={`${motivoId}-erro`} className={styles.erro} role="alert">
            Informe o motivo para cancelar.
          </p>
        )}
      </div>

      <div className={styles.acoes}>
        <button type="button" className={styles.botaoVoltar} onClick={onFechar} disabled={enviando}>
          Voltar
        </button>
        <button
          type="button"
          className={styles.botaoPerigo}
          onClick={() => void confirmar()}
          disabled={enviando || !motivoValido}
        >
          {enviando ? "Cancelando…" : "Cancelar prova"}
        </button>
      </div>
    </MotionModal>
  );
}
