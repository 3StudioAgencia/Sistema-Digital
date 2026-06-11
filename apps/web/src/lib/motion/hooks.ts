"use client";

/**
 * useReducedMotion — fundação central de respeito ao prefers-reduced-motion
 * (DAT §5.3, RN-012, RNF-010). O W1-C19 estende a camada de animações sobre ela.
 *
 * SSR-safe via useSyncExternalStore: no servidor não há preferência detectável
 * (retorna false) e o cliente reconcilia no primeiro paint sem hydration
 * mismatch. Quando true, animações decorativas devem usar DURATION.instant.
 */
import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const mql = window.matchMedia(QUERY);
  mql.addEventListener("change", onChange);
  return () => mql.removeEventListener("change", onChange);
}

function getSnapshot(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(QUERY).matches;
}

function getServerSnapshot(): boolean {
  return false;
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
