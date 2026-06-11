"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { type Variants, motion } from "framer-motion";

import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING } from "@/lib/motion/tokens";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

import styles from "../login/login.module.css";

/**
 * Bloco do formulário de login (cliente) — wordmark, título, campos e botão,
 * com entrada coreografada e microinterações.
 *
 * - signInWithPassword (Supabase Auth); em falha, mensagem GENÉRICA que não
 *   revela se errou e-mail ou senha (acceptance do Backlog C03 / §3.4).
 * - "Esqueci minha senha" é inerte nesta wave (DP-5): exibe uma dica.
 * - Animações sobre os tokens (DAT §5.1), só transform/opacity, degradando para
 *   instantâneas com prefers-reduced-motion (RN-012, RNF-010).
 */
export function LoginPanel({ expired }: { expired: boolean }) {
  const router = useRouter();
  const reduce = useReducedMotion();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState(false);

  const container: Variants = {
    hidden: {},
    show: {
      transition: {
        staggerChildren: reduce ? 0 : 0.07,
        delayChildren: reduce ? 0 : 0.05,
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
  // Microinteração de foco: leve "respiro" do campo (transform — GPU).
  const fieldFocus = reduce ? undefined : { scale: 1.015 };
  const fieldTransition = { duration: reduce ? 0 : DURATION.micro, ease: EASING.standard };

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
        // Genérico de propósito: não revela QUAL campo falhou (anti-enumeração).
        setError("E-mail ou senha inválidos. Verifique e tente novamente.");
        setLoading(false);
        return;
      }
      router.push("/inicio");
      router.refresh();
    } catch {
      setError("Não foi possível entrar agora. Tente novamente em instantes.");
      setLoading(false);
    }
  }

  return (
    <motion.div className={styles.panel} variants={container} initial="hidden" animate="show">
      <motion.div className={styles.wordmarkWrap} variants={item}>
        {/* eslint-disable-next-line @next/next/no-img-element -- SVG estático; next/image não otimiza SVG */}
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
        Lorem ipsum silor domor amet
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
        <motion.input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          className={styles.field}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={loading}
          whileFocus={fieldFocus}
          transition={fieldTransition}
        />

        <label className={styles.label} htmlFor="senha">
          Senha:
        </label>
        <motion.input
          id="senha"
          name="senha"
          type="password"
          autoComplete="current-password"
          required
          className={styles.field}
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          disabled={loading}
          whileFocus={fieldFocus}
          transition={fieldTransition}
        />

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

        <motion.button
          type="submit"
          className={styles.submit}
          disabled={loading}
          whileHover={reduce ? undefined : { scale: 1.02 }}
          whileTap={reduce ? undefined : { scale: 0.98 }}
          transition={{ duration: reduce ? 0 : DURATION.micro, ease: EASING.standard }}
        >
          {loading ? "Entrando…" : "Entrar"}
        </motion.button>
      </motion.form>

      <motion.p className={styles.footer} variants={item}>
        ©3Studio 2026
      </motion.p>
    </motion.div>
  );
}
