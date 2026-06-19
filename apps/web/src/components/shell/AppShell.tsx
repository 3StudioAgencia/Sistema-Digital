"use client";

/**
 * AppShell (W1-C04 / ADR-026) — o layout de TODA a plataforma autenticada.
 *
 * Duas zonas (design do Figma): sidebar preta fixa à esquerda + área de
 * conteúdo ("shell branco" #eaeaea, raio 40) onde cada página renderiza. Novas
 * páginas plugam criando rotas dentro do grupo (app) — nada do shell se repete.
 *
 * Responsividade (DP-7, breakpoint 768px): sidebar vira drawer com hambúrguer;
 * o conteúdo ocupa a tela com raio reduzido. Animações GPU-only com tokens e
 * degradação por prefers-reduced-motion.
 */
import { AnimatePresence, motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import type { Usuario } from "@/lib/api/usuarios";
import { DURATION, EASING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";
import { PageTransition } from "@/components/ui/motion";

import { Sidebar } from "./Sidebar";
import styles from "./app-shell.module.css";

type AppShellProps = {
  usuario: Usuario | null;
  emailSessao: string;
  children: React.ReactNode;
};

export function AppShell({ usuario, emailSessao, children }: AppShellProps) {
  const pathname = usePathname();
  const reduced = useReducedMotion();
  // Estado DERIVADO: o drawer guarda em qual rota foi aberto — navegar para
  // outra rota o fecha naturalmente. O reset guardado em fase de render
  // (padrão oficial "storing information from previous renders") garante que
  // VOLTAR à rota original (back/forward) não reabra o drawer (revisão W1-C04).
  const [abertoNaRota, setAbertoNaRota] = useState<string | null>(null);
  const [rotaAnterior, setRotaAnterior] = useState(pathname);
  if (rotaAnterior !== pathname) {
    setRotaAnterior(pathname);
    if (abertoNaRota !== null) setAbertoNaRota(null);
  }
  const drawerAberto = abertoNaRota === pathname;
  const setDrawerAberto = (aberto: boolean) => setAbertoNaRota(aberto ? pathname : null);

  useEffect(() => {
    if (!drawerAberto) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setAbertoNaRota(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerAberto]);

  // Drawer (mobile) na faixa de drawers do RF-024 (150–300 ms) — W6-C19.
  const duracao = reduced ? DURATION.instant : DURATION.short;

  return (
    <div className={styles.layout}>
      {/* Sidebar fixa (desktop) */}
      <aside className={styles.sidebarDesktop}>
        <Sidebar usuario={usuario} emailSessao={emailSessao} />
      </aside>

      {/* Drawer (mobile) */}
      <AnimatePresence>
        {drawerAberto && (
          <motion.div
            className={styles.drawerOverlay}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: duracao, ease: EASING.standard }}
            onClick={() => setDrawerAberto(false)}
          >
            <motion.aside
              className={styles.drawer}
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ duration: duracao, ease: EASING.emphasized }}
              onClick={(event) => event.stopPropagation()}
              aria-label="Menu"
            >
              <button
                type="button"
                className={styles.fecharDrawer}
                onClick={() => setDrawerAberto(false)}
                aria-label="Fechar menu"
              >
                <X size={24} aria-hidden />
              </button>
              <Sidebar
                usuario={usuario}
                emailSessao={emailSessao}
                onNavigate={() => setDrawerAberto(false)}
              />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div className={styles.principal}>
        {/* Barra superior só no mobile */}
        <header className={styles.topbar}>
          <button
            type="button"
            className={styles.hamburguer}
            onClick={() => setDrawerAberto(true)}
            aria-label="Abrir menu"
          >
            <Menu size={24} aria-hidden />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element -- SVG estático */}
          <img src="/logo-3studio.svg" alt="3Studio" width={94} height={20} />
        </header>

        <main className={styles.conteudo}>
          {/* Transição de página (RF-023): fade + leve translateY do conteúdo
              que ENTRA. Re-montada a cada navegação pelo key={pathname}. A
              primitiva <PageTransition> (W6-C19) encapsula o comportamento que
              antes vivia inline aqui — GPU-only, instantânea sob reduced-motion. */}
          <PageTransition key={pathname} className={styles.conteudoInterno}>
            {children}
          </PageTransition>
        </main>
      </div>
    </div>
  );
}
