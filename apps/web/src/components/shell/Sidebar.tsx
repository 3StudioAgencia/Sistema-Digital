"use client";

/**
 * Sidebar do app shell (W1-C04) — fiel ao design do Figma:
 * wordmark, saudação, busca (inerte até existir busca global), navegação com
 * indicador animado do item ativo (barra amarela desliza via layoutId) e
 * rodapé com avatar/usuário/Sair.
 */
import { motion } from "framer-motion";
import { Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import type { Usuario } from "@/lib/api/usuarios";
import { SETOR_LABELS } from "@/lib/api/usuarios";
import { DURATION } from "@/lib/motion/tokens";
import { SPRING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

import { NAV_PRINCIPAL, NAV_SECUNDARIA, hrefAtivo, type NavItem } from "./nav-items";
import styles from "./sidebar.module.css";

type SidebarProps = {
  usuario: Usuario | null;
  /** Fallback quando a linha de domínio ainda não existe (e-mail da sessão). */
  emailSessao: string;
  /** Fecha o drawer no mobile ao navegar (no desktop é no-op). */
  onNavigate?: () => void;
};

function primeiroNome(usuario: Usuario | null, emailSessao: string): string {
  if (usuario?.nome) return usuario.nome.trim().split(/\s+/)[0];
  const local = emailSessao.split("@")[0];
  return local || "usuário";
}

export function Sidebar({ usuario, emailSessao, onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const reduced = useReducedMotion();
  const ativo = hrefAtivo(pathname);
  const nome = primeiroNome(usuario, emailSessao);
  const subtitulo = usuario ? SETOR_LABELS[usuario.setor] : "3Studio";

  async function sair() {
    const supabase = getSupabaseBrowserClient();
    try {
      const { error } = await supabase.auth.signOut();
      if (error) await supabase.auth.signOut(); // uma retentativa
    } catch {
      // Rede falhou: navega mesmo assim — se a sessão persistir, o /login
      // (getUser no servidor) devolve o usuário ao shell, mostrando o estado
      // VERDADEIRO em vez de um "logout" silenciosamente falso (revisão W1-C04).
    }
    router.replace("/login");
    router.refresh();
  }

  function renderItem(item: NavItem) {
    const isAtivo = ativo === item.href;
    const Icone = item.icone;
    return (
      <li key={item.href}>
        <Link
          href={item.href}
          className={`${styles.navItem} ${isAtivo ? styles.navItemAtivo : ""}`}
          aria-current={isAtivo ? "page" : undefined}
          onClick={onNavigate}
        >
          <span className={styles.indicadorSlot} aria-hidden>
            {isAtivo && (
              <motion.span
                className={styles.indicador}
                layoutId="nav-indicador-ativo"
                transition={reduced ? { duration: DURATION.instant } : SPRING.interactive}
              />
            )}
          </span>
          <Icone className={styles.navIcone} size={22} strokeWidth={2} aria-hidden />
          <span>{item.rotulo}</span>
        </Link>
      </li>
    );
  }

  return (
    <div className={styles.sidebar}>
      {/* eslint-disable-next-line @next/next/no-img-element -- SVG estático; next/image não otimiza SVG */}
      <img
        src="/logo-3studio.svg"
        alt="3Studio"
        width={122}
        height={26}
        className={styles.wordmark}
      />

      <p className={styles.saudacao}>Olá {nome}!</p>

      {/* Busca global: alvo ainda não existe (provas = Wave 2) — campo fiel ao
          design, porém inerte (DP-6). */}
      <div className={styles.busca} title="Disponível em breve">
        <Search size={20} strokeWidth={2} className={styles.buscaIcone} aria-hidden />
        <input
          type="search"
          placeholder="Buscar..."
          disabled
          aria-label="Buscar (disponível em breve)"
          className={styles.buscaInput}
        />
      </div>

      <nav className={styles.nav} aria-label="Navegação principal">
        <ul className={styles.navLista}>{NAV_PRINCIPAL.map(renderItem)}</ul>
        <ul className={`${styles.navLista} ${styles.navSecundaria}`}>
          {NAV_SECUNDARIA.map(renderItem)}
        </ul>
      </nav>

      <footer className={styles.rodape}>
        <span className={styles.avatar} aria-hidden>
          {nome.charAt(0).toUpperCase()}
        </span>
        <span className={styles.rodapeTextos}>
          <span className={styles.rodapeNome}>{nome}</span>
          <span className={styles.rodapeSub}>{subtitulo}</span>
        </span>
        <button type="button" className={styles.sair} onClick={() => void sair()}>
          Sair
        </button>
      </footer>
    </div>
  );
}
