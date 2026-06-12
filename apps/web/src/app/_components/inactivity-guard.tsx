"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

import { getSupabaseBrowserClient } from "@/lib/supabase/client";

/** 30 minutos (RNF-004). Configurável via prop para os testes. */
const THIRTY_MINUTES_MS = 30 * 60 * 1000;

const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "click"];

/**
 * Encerramento por inatividade (W1-C03 / DP-3, RNF-004).
 *
 * Reinicia um timer a cada interação; após o intervalo ocioso, faz signOut e
 * volta ao login com ?expirado=1 (notice discreto, sem o Toaster do C19).
 * Montado nas páginas autenticadas (por ora /inicio; o C05 levará para um layout
 * autenticado compartilhado). Não renderiza nada.
 */
export function InactivityGuard({ timeoutMs = THIRTY_MINUTES_MS }: { timeoutMs?: number }) {
  const router = useRouter();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    async function expire() {
      const supabase = getSupabaseBrowserClient();
      try {
        const { error } = await supabase.auth.signOut();
        if (error) await supabase.auth.signOut(); // uma retentativa
      } catch {
        // Rede falhou no expirar: navega mesmo assim — se a sessão persistir,
        // o /login devolve ao shell (estado verdadeiro) e o timer recomeça.
      }
      router.replace("/login?expirado=1");
      router.refresh();
    }

    function reset() {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        void expire();
      }, timeoutMs);
    }

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, reset, { passive: true });
    }
    reset();

    return () => {
      if (timer.current) clearTimeout(timer.current);
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, reset);
      }
    };
  }, [router, timeoutMs]);

  return null;
}
