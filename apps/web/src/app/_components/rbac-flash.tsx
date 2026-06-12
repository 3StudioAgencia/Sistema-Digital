"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import { useToast } from "@/components/ui/toast/ToastProvider";
import { FLASH_ACESSO_NEGADO } from "@/lib/access-matrix";

/** Mensagem genérica (anti-enumeração: não revela QUAL página — CLAUDE.md §11). */
const MENSAGEM = "Você não tem permissão para acessar essa página.";

/**
 * Toast de acesso negado (W1-C05 / DP-4).
 *
 * O proxy (camada superior do RBAC) não renderiza UI: quando nega uma rota,
 * redireciona à home e deixa um cookie efêmero (`rbac_negado`). Este componente,
 * montado no layout autenticado (dentro do ToastProvider), lê e LIMPA o cookie e
 * dispara o toast. Reage à mudança de rota para cobrir também navegações soft.
 */
export function RbacFlash() {
  const { error } = useToast();
  const pathname = usePathname();

  useEffect(() => {
    if (consumirFlash()) error(MENSAGEM);
  }, [pathname, error]);

  return null;
}

/** Lê o flash uma única vez (limpa o cookie). True se estava presente. */
function consumirFlash(): boolean {
  if (typeof document === "undefined") return false;
  const presente = document.cookie
    .split("; ")
    .some((c) => c.startsWith(`${FLASH_ACESSO_NEGADO}=`));
  if (presente) {
    document.cookie = `${FLASH_ACESSO_NEGADO}=; path=/; max-age=0`;
  }
  return presente;
}
