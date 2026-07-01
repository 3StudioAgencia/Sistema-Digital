"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { type Variants, motion } from "framer-motion";

import { HOME_PADRAO } from "@/lib/access-matrix";
import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING, SPRING } from "@/lib/motion/tokens";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

import styles from "../login/login.module.css";

type FocusedField = "email" | "senha" | null;

export function LoginPanel({ expired }: { expired: boolean }) {
  const router = useRouter();
  const reduce = useReducedMotion();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState(false);
  const [focused, setFocused] = useState<FocusedField>(null);

  const container: Variants = {
    hidden: {},
    show: {
      transition: {
        staggerChildren: reduce ? 0 : 0.07,
        delayChildren: reduce ? 0 : 0.06,
      },
    },
  };
  const item: Variants = {
    hidden: { opacity: 0, y: reduce ? 0 : 14 },
    show: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? DURATION.instant : DURATION.long, ease: EASING.emphasized },
    },
  };

  const ringTransition = { duration: reduce ? 0 : DURATION.short, ease: EASING.standard };
  const press = reduce
    ? {}
    : { whileHover: { scale: 1.03 }, whileTap: { scale: 0.97 }, transition: SPRING.interactive };

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setHint(false);
    setLoading(true);
    try {
      const supabase = getSupabaseBrowserClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password: senha,
      });
      if (signInError) {
        setError("E-mail ou senha inválidos. Verifique e tente novamente.");
        setLoading(false);
        return;
      }
      router.push(HOME_PADRAO);
      router.refresh();
    } catch {
      setError("Não foi possível entrar agora. Tente novamente em instantes.");
      setLoading(false);
    }
  }

  return (
    <motion.div className={styles.panel} variants={container} initial="hidden" animate="show">
      <motion.div className={styles.wordmarkWrap} variants={item}>
        <img
          src="/logo-3studio.svg"
          alt="3Studio"
          width={122}
          height={26}
          className={styles.wordmark}
        />
      </motion.div>

      <motion.h1 className={styles.title} variants={item}>
        Fazer login
      </motion.h1>
      <motion.p className={styles.subtitle} variants={item}>
        Entre no sistema de provas digitais.
      </motion.p>

      {expired && (
        <motion.p className={styles.notice} role="status" variants={item}>
          Sua sessão expirou por inatividade. Entre novamente.
        </motion.p>
      )}

      <motion.form className={styles.form} onSubmit={onSubmit} variants={item} noValidate>
        <label className={styles.label} htmlFor="email">
          E-mail:
        </label>
        <div className={styles.fieldWrap}>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            className={styles.field}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onFocus={() => setFocused("email")}
            onBlur={() => setFocused((f) => (f === "email" ? null : f))}
            disabled={loading}
          />
          <motion.span
            className={styles.fieldRing}
            aria-hidden="true"
            initial={false}
            animate={{ opacity: focused === "email" ? 1 : 0 }}
            transition={ringTransition}
          />
        </div>

        <label className={styles.label} htmlFor="senha">
          Senha:
        </label>
        <div className={styles.fieldWrap}>
          <input
            id="senha"
            name="senha"
            type="password"
            autoComplete="current-password"
            required
            className={styles.field}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            onFocus={() => setFocused("senha")}
            onBlur={() => setFocused((f) => (f === "senha" ? null : f))}
            disabled={loading}
          />
          <motion.span
            className={styles.fieldRing}
            aria-hidden="true"
            initial={false}
            animate={{ opacity: focused === "senha" ? 1 : 0 }}
            transition={ringTransition}
          />
        </div>

        <button type="button" className={styles.forgot} onClick={() => setHint(true)}>
          Esqueci minha senha
        </button>
        {hint && (
          <p className={styles.hint}>
            Redefinição de senha chega em breve — por ora, fale com o administrador.
          </p>
        )}

        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        <motion.button type="submit" className={styles.submit} disabled={loading} {...press}>
          {loading ? "Entrando…" : "Entrar"}
        </motion.button>
      </motion.form>

      <motion.p className={styles.footer} variants={item}>
        ©3Studio 2026
      </motion.p>
    </motion.div>
  );
}
