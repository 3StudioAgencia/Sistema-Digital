"use client";

import { useState } from "react";
import { AnimatePresence, type Variants, motion } from "framer-motion";

import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";

import styles from "../login/login.module.css";
import { LoginPanel } from "./login-panel";

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
      <motion.div
        className={styles.hero}
        aria-hidden="true"
        initial={reduce ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: reduce ? 0 : DURATION.long, ease: EASING.emphasized }}
      >
        <div className={styles.heroImg} />
      </motion.div>

      <div className={styles.formArea}>
        <LoginPanel expired={expired} />
      </div>

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
