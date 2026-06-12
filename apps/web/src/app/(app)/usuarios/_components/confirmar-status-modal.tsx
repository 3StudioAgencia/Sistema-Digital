"use client";

/**
 * Confirmação de desativar/reativar (W1-C04 / US-015).
 *
 * Desativar bloqueia o login SEM apagar histórico — o texto deixa isso claro.
 * Erros de regra (RN-010: autodesativação, último admin) chegam do backend e
 * viram toast com a mensagem da regra.
 */
import { useId, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { desativarUsuario, reativarUsuario, type Usuario } from "@/lib/api/usuarios";
import { MotionModal } from "@/components/ui/modal/MotionModal";
import { useToast } from "@/components/ui/toast/ToastProvider";

import styles from "../usuarios.module.css";

export type AcaoStatus = "desativar" | "reativar";

type Props = {
  confirmacao: { usuario: Usuario; acao: AcaoStatus } | null;
  onFechar: () => void;
  onConfirmado: (usuario: Usuario) => void;
};

export function ConfirmarStatusModal({ confirmacao, onFechar, onConfirmado }: Props) {
  const toast = useToast();
  const tituloId = useId();
  const [enviando, setEnviando] = useState(false);

  const acao = confirmacao?.acao ?? "desativar";
  const usuario = confirmacao?.usuario;

  async function confirmar() {
    if (!usuario || enviando) return;
    setEnviando(true);
    try {
      const atualizado =
        acao === "desativar"
          ? await desativarUsuario(usuario.id)
          : await reativarUsuario(usuario.id);
      onConfirmado(atualizado);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Falha ao alterar o status.");
      onFechar();
    } finally {
      setEnviando(false);
    }
  }

  return (
    <MotionModal
      open={confirmacao !== null}
      onClose={onFechar}
      labelledBy={tituloId}
      panelClassName={styles.modalPainelConfirmacao}
    >
      <h2 id={tituloId} className={styles.modalTitulo}>
        {acao === "desativar" ? "Desativar usuário" : "Reativar usuário"}
      </h2>
      <hr className={styles.modalSeparador} />
      <p className={styles.modalTexto}>
        {acao === "desativar" ? (
          <>
            Tem certeza que deseja desativar <strong>{usuario?.nome}</strong>? O usuário não
            conseguirá mais entrar no sistema; todo o histórico é preservado.
          </>
        ) : (
          <>
            Reativar <strong>{usuario?.nome}</strong> permitirá que o usuário volte a entrar no
            sistema.
          </>
        )}
      </p>
      <div className={styles.modalAcoes}>
        <button
          type="button"
          className={styles.botaoCancelar}
          onClick={onFechar}
          disabled={enviando}
        >
          Cancelar
        </button>
        <button
          type="button"
          className={acao === "desativar" ? styles.botaoConfirmarPerigo : styles.botaoConfirmar}
          onClick={() => void confirmar()}
          disabled={enviando}
        >
          {enviando ? "Aguarde…" : acao === "desativar" ? "Desativar" : "Reativar"}
        </button>
      </div>
    </MotionModal>
  );
}
