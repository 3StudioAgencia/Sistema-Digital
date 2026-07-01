"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

import { getSupabaseBrowserClient } from "@/lib/supabase/client";

const THIRTY_MINUTES_MS = 30 * 60 * 1000;

const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "click"];

export function InactivityGuard({ timeoutMs = THIRTY_MINUTES_MS }: { timeoutMs?: number }) {
  const router = useRouter();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    async function expire() {
      const supabase = getSupabaseBrowserClient();
      try {
        const { error } = await supabase.auth.signOut();
        if (error) await supabase.auth.signOut();
      } catch {
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
