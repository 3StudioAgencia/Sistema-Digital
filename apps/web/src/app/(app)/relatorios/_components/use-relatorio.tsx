"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";

import styles from "../relatorios.module.css";

type TipoErro = "erro" | "acesso_negado";

export type EstadoRelatorio<T> = {
  dados: T | null;
  carregando: boolean;
  erro: TipoErro | null;
  recarregar: () => void;
};

export function useRelatorio<T>(
  buscar: (signal: AbortSignal) => Promise<T>,
  chave: string,
): EstadoRelatorio<T> {
  const [resultado, setResultado] = useState<{ chave: string; dados: T } | null>(null);
  const [falha, setFalha] = useState<{ chave: string; tipo: TipoErro } | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const buscarRef = useRef(buscar);
  useEffect(() => {
    buscarRef.current = buscar;
  });

  useEffect(() => {
    const controller = new AbortController();
    buscarRef
      .current(controller.signal)
      .then((d) => setResultado({ chave, dados: d }))
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFalha({
          chave,
          tipo: e instanceof ApiError && e.status === 403 ? "acesso_negado" : "erro",
        });
      });
    return () => controller.abort();
  }, [chave, tentativa]);

  const dados = resultado?.chave === chave ? resultado.dados : null;
  const erro = falha?.chave === chave ? falha.tipo : null;
  return {
    dados,
    carregando: dados === null && erro === null,
    recarregar: () => setTentativa((t) => t + 1),
    erro,
  };
}

export function EstadoErro({ tipo, onRetry }: { tipo: TipoErro; onRetry: () => void }) {
  if (tipo === "acesso_negado") {
    return (
      <p className={styles.estadoErro} role="alert">
        Você não tem acesso aos relatórios.
      </p>
    );
  }
  return (
    <p className={styles.estadoErro} role="alert">
      Não foi possível carregar este relatório.{" "}
      <button type="button" className={styles.tentarNovamente} onClick={onRetry}>
        Tentar novamente
      </button>
    </p>
  );
}

export function GridSkeleton({ cards = 4 }: { cards?: number }) {
  return (
    <div className={styles.grid} aria-hidden>
      {Array.from({ length: cards }, (_, i) => (
        <div key={i} className={`${styles.card} ${styles.skeleton}`} />
      ))}
    </div>
  );
}
