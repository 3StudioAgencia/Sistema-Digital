"use client";
import Image from "next/image";
import { motion } from "framer-motion";
import { Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { Perfil } from "@/lib/access-matrix";
import { podeAcessarRota } from "@/lib/access-matrix";
import type { Usuario } from "@/lib/api/usuarios";
import { SETOR_LABELS } from "@/lib/api/usuarios";
import { DURATION } from "@/lib/motion/tokens";
import { SPRING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";
import { logout } from "@/lib/auth/client";
import logo3studio from "@/assets/logo-3studio.svg";
import { NAV_PRINCIPAL, NAV_SECUNDARIA, hrefAtivo, type NavItem } from "./nav-items";
import styles from "./sidebar.module.css";

type SidebarProps = {
  usuario: Usuario | null;
  emailSessao: string;
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
  const perfil: Perfil = {
    setor: usuario?.setor ?? null,
    administrador: usuario?.administrador ?? false,
  };
  const principais = NAV_PRINCIPAL.filter((item) => podeAcessarRota(perfil, item.href));
  const secundarias = NAV_SECUNDARIA.filter((item) => podeAcessarRota(perfil, item.href));

  async function sair() {
    await logout();
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
      <Image
        src={logo3studio}
        alt="3Studio"
        width={122}
        height={26}
        className={styles.wordmark}
      />

      <p className={styles.saudacao}>Olá {nome}!</p>
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
        <ul className={styles.navLista}>{principais.map(renderItem)}</ul>
        <ul className={`${styles.navLista} ${styles.navSecundaria}`}>
          {secundarias.map(renderItem)}
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
