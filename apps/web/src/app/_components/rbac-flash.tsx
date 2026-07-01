"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import { useToast } from "@/components/ui/toast/ToastProvider";
import { FLASH_ACESSO_NEGADO } from "@/lib/access-matrix";

const MENSAGEM = "Você não tem permissão para acessar essa página.";

export function RbacFlash() {
  const { error } = useToast();
  const pathname = usePathname();

  useEffect(() => {
    if (consumirFlash()) error(MENSAGEM);
  }, [pathname, error]);

  return null;
}

function consumirFlash(): boolean {
  if (typeof document === "undefined") return false;
  const presente = document.cookie.split("; ").some((c) => c.startsWith(`${FLASH_ACESSO_NEGADO}=`));
  if (presente) {
    document.cookie = `${FLASH_ACESSO_NEGADO}=; path=/; max-age=0`;
  }
  return presente;
}
