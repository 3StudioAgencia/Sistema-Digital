"use client";

import { useState } from "react";
import { AnimatePresence, type Variants, motion } from "framer-motion";

import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";

import styles from "../login/login.module.css";
import { LoginPanel } from "./login-panel";

/**
 * Experiência de login adaptativa (W1-C03 / DP-7).
 *
 * - **Desktop (>=768px):** split — herói com formato custom (máscara SVG) +
 *   formulário. A imagem é estática (sem parallax/zoom).
 * - **Mobile:** boas-vindas PRIMEIRO (overlay) e o formulário só aparece ao
 *   clicar em "Entrar" — troca de passo (estado), sem mudar de rota, com
 *   transição fluida (sem redirecionamento por viewport).
 *
 * Toda animação degrada para instantânea com prefers-reduced-motion.
 */
export function AuthFlow({ expired }: { expired: boolean }) {
  const reduce = useReducedMotion();
  const [showForm, setShowForm] = useState(false);

  const welcomeContainer: Variants = {
    hidden: {},
    show: { transition: { staggerChildren: reduce ? 0 : 0.07, delayChildren: reduce ? 0 : 0.06 } },
  };
  const welcomeItem: Variants = {
    hidden: { opacity: 0, y: reduce ? 0 : 16 },
    show: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? DURATION.instant : DURATION.long, ease: EASING.emphasized },
    },
  };

  return (
    <div className={styles.page}>
      {/* Herói desktop — formato custom (máscara). Imagem estática; apenas um
          fade discreto na entrada, em sintonia com o restante. */}
      <motion.div
        className={styles.hero}
        aria-hidden="true"
        initial={reduce ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: reduce ? 0 : DURATION.long, ease: EASING.emphasized }}
      >
        <div className={styles.heroImg} />
      </motion.div>

      {/* Formulário — desktop: à direita; mobile: revelado após as boas-vindas. */}
      <div className={styles.formArea}>
        <LoginPanel expired={expired} />
      </div>

      {/* Boas-vindas — overlay mobile-only; sai de cena ao clicar em Entrar. */}
      <AnimatePresence>
        {!showForm && (
          <motion.section
            key="welcome"
            className={styles.welcome}
            aria-label="Boas-vindas"
            initial={{ opacity: reduce ? 1 : 0 }}
            animate={{ opacity: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: -48 }}
            transition={{ duration: reduce ? 0 : DURATION.medium, ease: EASING.exit }}
          >
            <div className={styles.welcomeHero} aria-hidden="true" />
            <motion.div
              className={styles.welcomeContent}
              variants={welcomeContainer}
              initial="hidden"
              animate="show"
            >
              <motion.div variants={welcomeItem}>
                {/* eslint-disable-next-line @next/next/no-img-element -- SVG estático; next/image não otimiza SVG */}
                <img
                  src="/logo-3studio.svg"
                  alt="3Studio"
                  width={122}
                  height={28}
                  className={styles.welcomeWordmark}
                />
              </motion.div>
              <motion.h1 className={styles.welcomeTitle} variants={welcomeItem}>
                Seja bem vindo!
              </motion.h1>
              <motion.p className={styles.welcomeSubtitle} variants={welcomeItem}>
                Lorem ipsum silor domor amet
              </motion.p>
              <motion.button
                type="button"
                className={styles.welcomeCta}
                variants={welcomeItem}
                onClick={() => setShowForm(true)}
                whileHover={reduce ? undefined : { scale: 1.03 }}
                whileTap={reduce ? undefined : { scale: 0.97 }}
                transition={SPRING.interactive}
              >
                Entrar
              </motion.button>
            </motion.div>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}
