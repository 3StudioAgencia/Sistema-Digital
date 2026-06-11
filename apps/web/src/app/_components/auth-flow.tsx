"use client";

import { type MouseEvent, useState } from "react";
import { AnimatePresence, type Variants, motion, useMotionValue, useSpring } from "framer-motion";

import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";

import styles from "../login/login.module.css";
import { LoginPanel } from "./login-panel";

/**
 * Experiência de login adaptativa (W1-C03 / DP-7).
 *
 * - **Desktop (>=768px):** split — herói com formato custom (máscara SVG) +
 *   formulário. O herói reage ao cursor com um parallax suave (hover).
 * - **Mobile:** boas-vindas PRIMEIRO (overlay) e o formulário só aparece ao
 *   clicar em "Entrar" — uma troca de passo (estado), sem mudar de rota, com
 *   transição fluida. Sem redirecionamento por viewport (robusto).
 *
 * Toda animação degrada para instantânea com prefers-reduced-motion.
 */
export function AuthFlow({ expired }: { expired: boolean }) {
  const reduce = useReducedMotion();
  const [showForm, setShowForm] = useState(false);

  // Parallax do herói no desktop: a imagem segue o cursor de leve (mola).
  const mvX = useMotionValue(0);
  const mvY = useMotionValue(0);
  const x = useSpring(mvX, SPRING.parallax);
  const y = useSpring(mvY, SPRING.parallax);

  function onHeroMove(event: MouseEvent<HTMLDivElement>) {
    if (reduce) return;
    const rect = event.currentTarget.getBoundingClientRect();
    mvX.set(((event.clientX - rect.left) / rect.width - 0.5) * 18);
    mvY.set(((event.clientY - rect.top) / rect.height - 0.5) * 18);
  }
  function onHeroLeave() {
    mvX.set(0);
    mvY.set(0);
  }

  const welcomeContainer: Variants = {
    hidden: {},
    show: { transition: { staggerChildren: reduce ? 0 : 0.07, delayChildren: reduce ? 0 : 0.06 } },
  };
  const welcomeItem: Variants = {
    hidden: { opacity: 0, y: reduce ? 0 : 18 },
    show: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? DURATION.instant : DURATION.long, ease: EASING.emphasized },
    },
  };

  return (
    <div className={styles.page}>
      {/* Herói desktop — formato custom (máscara) + parallax suave no hover. */}
      <motion.div
        className={styles.hero}
        aria-hidden="true"
        onMouseMove={onHeroMove}
        onMouseLeave={onHeroLeave}
        initial={reduce ? false : { opacity: 0, scale: 1.04 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: reduce ? 0 : DURATION.long, ease: EASING.emphasized }}
      >
        <motion.div
          className={styles.heroImg}
          style={{ x, y }}
          whileHover={reduce ? undefined : { scale: 1.04 }}
          transition={SPRING.interactive}
        />
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
