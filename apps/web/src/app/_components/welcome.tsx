"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type Variants, motion } from "framer-motion";

import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING } from "@/lib/motion/tokens";

import styles from "../bem-vindo/bem-vindo.module.css";

/**
 * Boas-vindas (cliente). No desktop (≥768px) encaminha para /login — a tela é
 * mobile-only (DP-7). Entrada coreografada sobre os tokens de motion, degradando
 * para instantânea com prefers-reduced-motion.
 */
export function Welcome() {
  const router = useRouter();
  const reduce = useReducedMotion();

  useEffect(() => {
    if (window.matchMedia("(min-width: 768px)").matches) {
      router.replace("/login");
    }
  }, [router]);

  const container: Variants = {
    hidden: {},
    show: {
      transition: {
        staggerChildren: reduce ? 0 : 0.08,
        delayChildren: reduce ? 0 : 0.1,
      },
    },
  };
  const item: Variants = {
    hidden: { opacity: 0, y: reduce ? 0 : 16 },
    show: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? DURATION.instant : DURATION.long, ease: EASING.emphasized },
    },
  };

  return (
    <div className={styles.screen}>
      <div className={styles.hero} aria-hidden="true" />
      <motion.div className={styles.content} variants={container} initial="hidden" animate="show">
        <motion.div variants={item}>
          {/* eslint-disable-next-line @next/next/no-img-element -- SVG estático; next/image não otimiza SVG */}
          <img
            src="/logo-3studio.svg"
            alt="3Studio"
            width={122}
            height={28}
            className={styles.wordmark}
          />
        </motion.div>
        <motion.h1 className={styles.title} variants={item}>
          Seja bem vindo!
        </motion.h1>
        <motion.p className={styles.subtitle} variants={item}>
          Lorem ipsum silor domor amet
        </motion.p>
        <motion.div
          className={styles.ctaWrap}
          variants={item}
          whileHover={reduce ? undefined : { scale: 1.02 }}
          whileTap={reduce ? undefined : { scale: 0.98 }}
        >
          <Link href="/login" className={styles.cta}>
            Entrar
          </Link>
        </motion.div>
      </motion.div>
    </div>
  );
}
