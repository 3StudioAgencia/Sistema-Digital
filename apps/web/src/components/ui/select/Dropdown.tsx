"use client";

/**
 * Dropdown personalizado dos filtros (W1-C04, pedido do dono) — substitui o
 * <select> nativo por um painel com o design da plataforma (pill cinza +
 * opções arredondadas), mantendo acessibilidade de listbox:
 * - trigger com aria-haspopup/aria-expanded; painel role=listbox/option;
 * - setas navegam, Enter/Espaço selecionam, ESC fecha, clique fora fecha;
 * - animação por tokens (scale+fade, GPU-only), instantânea sob reduced-motion.
 */
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { DURATION, EASING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";

import styles from "./dropdown.module.css";

export type OpcaoDropdown<T extends string> = { value: T; label: string };

type DropdownProps<T extends string> = {
  value: T;
  opcoes: OpcaoDropdown<T>[];
  onChange: (value: T) => void;
  /** Nome acessível direto (filtros)… */
  ariaLabel?: string;
  /** …ou via id de um rótulo visível (campos do modal). */
  labelledBy?: string;
  /** id do texto de erro a anunciar (aria-describedby), quando inválido. */
  describedBy?: string;
  /** Marca o gatilho como inválido (aria-invalid) — feedback de erro do form. */
  invalido?: boolean;
  /** Desabilita o gatilho (ex.: enquanto as opções carregam) — não abre. */
  disabled?: boolean;
  /** Texto do gatilho quando nenhum valor casa (campo ainda vazio). */
  placeholder?: string;
  /** "claro" = filtros sobre o shell; "escuro" = campos do modal. */
  variante?: "claro" | "escuro";
  /** Direção do painel. "cima" evita o recorte pelo overflow do modal quando
      o campo está na metade de baixo dele. */
  abrirPara?: "baixo" | "cima";
};

export function Dropdown<T extends string>({
  value,
  opcoes,
  onChange,
  ariaLabel,
  labelledBy,
  describedBy,
  invalido = false,
  disabled = false,
  placeholder = "",
  variante = "claro",
  abrirPara = "baixo",
}: DropdownProps<T>) {
  const reduced = useReducedMotion();
  const [aberto, setAberto] = useState(false);
  const [foco, setFoco] = useState(0);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const opcaoRefs = useRef<(HTMLLIElement | null)[]>([]);

  const atual = opcoes.find((o) => o.value === value);

  function abrir() {
    // Sem opções (ex.: carregando) ou desabilitado: não abre um painel vazio.
    if (disabled || opcoes.length === 0) return;
    setFoco(
      Math.max(
        0,
        opcoes.findIndex((o) => o.value === value),
      ),
    );
    setAberto(true);
  }

  function fechar(devolverFoco = true) {
    setAberto(false);
    if (devolverFoco) triggerRef.current?.focus();
  }

  function selecionar(opcao: OpcaoDropdown<T>) {
    onChange(opcao.value);
    fechar();
  }

  // Clique/toque fora fecha (sem devolver o foco — o usuário foi para outro lugar).
  useEffect(() => {
    if (!aberto) return;
    function aoPressionarFora(event: PointerEvent) {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) {
        setAberto(false);
      }
    }
    document.addEventListener("pointerdown", aoPressionarFora);
    return () => document.removeEventListener("pointerdown", aoPressionarFora);
  }, [aberto]);

  // Foco acompanha a opção ativa enquanto o painel está aberto.
  useEffect(() => {
    if (aberto) opcaoRefs.current[foco]?.focus();
  }, [aberto, foco]);

  function aoTeclarNaLista(event: React.KeyboardEvent<HTMLUListElement>) {
    switch (event.key) {
      case "Escape":
        event.stopPropagation();
        fechar();
        break;
      case "ArrowDown":
        event.preventDefault();
        setFoco((f) => Math.min(f + 1, opcoes.length - 1));
        break;
      case "ArrowUp":
        event.preventDefault();
        setFoco((f) => Math.max(f - 1, 0));
        break;
      case "Home":
        event.preventDefault();
        setFoco(0);
        break;
      case "End":
        event.preventDefault();
        setFoco(opcoes.length - 1);
        break;
      case "Enter":
      case " ":
        event.preventDefault();
        selecionar(opcoes[foco]);
        break;
      case "Tab":
        fechar(false);
        break;
    }
  }

  const duracao = reduced ? DURATION.instant : DURATION.short;

  return (
    <div
      className={`${styles.wrap} ${variante === "escuro" ? styles.escuro : ""} ${
        abrirPara === "cima" ? styles.paraCima : ""
      }`}
      ref={wrapRef}
    >
      <button
        type="button"
        ref={triggerRef}
        className={styles.trigger}
        aria-haspopup="listbox"
        aria-expanded={aberto}
        aria-label={ariaLabel}
        aria-labelledby={labelledBy}
        aria-describedby={invalido ? describedBy : undefined}
        aria-invalid={invalido || undefined}
        disabled={disabled}
        onClick={() => (aberto ? fechar() : abrir())}
        onKeyDown={(event) => {
          if (!aberto && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
            event.preventDefault();
            abrir();
          }
        }}
      >
        <span className={styles.rotulo}>{atual?.label ?? placeholder}</span>
        <ChevronDown
          className={`${styles.chevron} ${aberto ? styles.chevronAberto : ""}`}
          aria-hidden
        />
      </button>

      <AnimatePresence>
        {aberto && (
          <motion.ul
            role="listbox"
            aria-label={ariaLabel}
            aria-labelledby={labelledBy}
            className={styles.painel}
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: duracao, ease: EASING.emphasized }}
            onKeyDown={aoTeclarNaLista}
          >
            {opcoes.map((opcao, indice) => (
              <li
                key={opcao.value}
                role="option"
                aria-selected={opcao.value === value}
                tabIndex={-1}
                ref={(node) => {
                  opcaoRefs.current[indice] = node;
                }}
                className={`${styles.opcao} ${opcao.value === value ? styles.opcaoAtiva : ""}`}
                onClick={() => selecionar(opcao)}
                onPointerMove={() => setFoco(indice)}
              >
                {opcao.label}
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
