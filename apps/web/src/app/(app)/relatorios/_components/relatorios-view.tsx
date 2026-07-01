"use client";

import { motion } from "framer-motion";
import { Calendar, ChevronDown, Download, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Dropdown } from "@/components/ui/select/Dropdown";
import { useToast } from "@/components/ui/toast/ToastProvider";
import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING } from "@/lib/motion/tokens";
import { fadeRise, staggerContainer } from "@/lib/motion/variants";
import {
  exportarRelatorioCsv,
  listarVendedores,
  type Aba,
  type FiltrosRelatorio,
  type GrupoRota,
} from "@/lib/api/relatorios";
import type { VendedorRef } from "@/lib/api/provas";
import {
  STATUS_PROVA_LABELS,
  STATUS_PROVA_ORDEM,
  type EstadoProva,
} from "@/lib/provas/status-labels";

import styles from "../relatorios.module.css";
import { ClicheriaTab } from "./clicheria-tab";
import { GeralTab } from "./geral-tab";
import { StudioTab } from "./studio-tab";
import { VendedoresTab } from "./vendedores-tab";

const DEBOUNCE_MS = 300;
const ABAS: { id: Aba; rotulo: string }[] = [
  { id: "geral", rotulo: "Geral" },
  { id: "studio", rotulo: "3Studio" },
  { id: "vendedores", rotulo: "Vendedores" },
  { id: "clicheria", rotulo: "Clicheria" },
];
const GRUPOS_ROTA: { id: GrupoRota; rotulo: string }[] = [
  { id: "", rotulo: "Todas" },
  { id: "matriz", rotulo: "Matriz" },
  { id: "filial", rotulo: "Filial" },
];

function hojeIso(): string {
  return new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD local
}
function isoMenosDias(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() - dias);
  return d.toLocaleDateString("en-CA");
}
const PRESETS: { rotulo: string; de: () => string; ate: () => string }[] = [
  { rotulo: "Hoje", de: () => hojeIso(), ate: () => hojeIso() },
  { rotulo: "7d", de: () => isoMenosDias(6), ate: () => hojeIso() },
  { rotulo: "30d", de: () => isoMenosDias(29), ate: () => hojeIso() },
  { rotulo: "90d", de: () => isoMenosDias(89), ate: () => hojeIso() },
];

export function RelatoriosView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const toast = useToast();
  const reduced = useReducedMotion();
  const transicaoPill = reduced
    ? { duration: DURATION.instant }
    : { duration: DURATION.short, ease: EASING.emphasized };
  const containerVar = staggerContainer(reduced);
  const itemVar = fadeRise(reduced);

  const aba = (searchParams.get("aba") as Aba | null) ?? "geral";
  const queryString = searchParams.toString();
  const filtros = useMemo<FiltrosRelatorio>(
    () => ({
      de: searchParams.get("de") ?? undefined,
      ate: searchParams.get("ate") ?? undefined,
      status: (searchParams.get("status") as EstadoProva | null) ?? "",
      grupoRota: (searchParams.get("rota") as GrupoRota | null) ?? "",
      busca: searchParams.get("busca") ?? undefined,
      vendedorId: searchParams.get("vendedor") ?? undefined,
    }),
    [queryString],
  );
  const chaveFiltros = `${filtros.de ?? ""}|${filtros.ate ?? ""}|${filtros.status ?? ""}|${
    filtros.grupoRota ?? ""
  }|${filtros.busca ?? ""}|${filtros.vendedorId ?? ""}`;

  const aplicar = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [k, v] of Object.entries(updates)) {
        if (v) params.set(k, v);
        else params.delete(k);
      }
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [searchParams, router, pathname],
  );
  const aplicarRef = useRef(aplicar);
  useEffect(() => {
    aplicarRef.current = aplicar;
  });

  const [busca, setBusca] = useState(() => searchParams.get("busca") ?? "");
  useEffect(() => {
    const timer = setTimeout(() => {
      const atual = new URLSearchParams(window.location.search).get("busca") ?? "";
      if (busca.trim() !== atual) aplicarRef.current({ busca: busca.trim() || undefined });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [busca]);

  const [vendedores, setVendedores] = useState<VendedorRef[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    listarVendedores(controller.signal)
      .then(setVendedores)
      .catch(() => {
      });
    return () => controller.abort();
  }, []);

  const [menuAberto, setMenuAberto] = useState(false);
  const exportWrapRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!menuAberto) return;
    function aoClicarFora(e: PointerEvent) {
      if (exportWrapRef.current && !exportWrapRef.current.contains(e.target as Node)) {
        setMenuAberto(false);
      }
    }
    document.addEventListener("pointerdown", aoClicarFora);
    return () => document.removeEventListener("pointerdown", aoClicarFora);
  }, [menuAberto]);

  const exportar = useCallback(
    async (alvo: Aba) => {
      setMenuAberto(false);
      try {
        await exportarRelatorioCsv(alvo, filtros);
      } catch {
        toast.error("Não foi possível exportar o CSV. Tente novamente.");
      }
    },
    [filtros, toast],
  );

  const statusOpcoes = [
    { value: "", label: "Status: Todos" },
    ...STATUS_PROVA_ORDEM.map((s) => ({ value: s, label: STATUS_PROVA_LABELS[s] })),
  ];
  const vendedorOpcoes = [
    { value: "", label: "Vendedor: Todos" },
    ...vendedores.map((v) => ({ value: v.id, label: v.nome })),
  ];

  const presetSelecionado = searchParams.get("preset") ?? "";
  const presetAtivo = (p: (typeof PRESETS)[number]) => presetSelecionado === p.rotulo;
  const abrirCalendario = (input: HTMLInputElement) => {
    try {
      input.showPicker();
    } catch {
    }
  };

  return (
    <motion.section
      className={styles.pagina}
      aria-label="Relatórios"
      variants={containerVar}
      initial="hidden"
      animate="show"
    >
      <motion.div className={styles.cabecalho} variants={itemVar}>
        <h1 className={styles.titulo}>Relatórios</h1>
        <div className={styles.exportWrap} ref={exportWrapRef}>
          <button
            type="button"
            className={styles.btnExportar}
            onClick={() => setMenuAberto((a) => !a)}
            aria-haspopup="menu"
            aria-expanded={menuAberto}
          >
            <Download aria-hidden /> Exportar CSV <ChevronDown aria-hidden />
          </button>
          {menuAberto ? (
            <div className={styles.menuExport} role="menu">
              {ABAS.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  role="menuitem"
                  onClick={() => void exportar(a.id)}
                >
                  Exportar “{a.rotulo}”
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </motion.div>

      <motion.div
        className={styles.tabBar}
        role="tablist"
        aria-label="Relatórios"
        variants={itemVar}
      >
        {ABAS.map((a) => (
          <button
            key={a.id}
            type="button"
            role="tab"
            aria-selected={aba === a.id}
            className={styles.tab}
            data-ativo={aba === a.id || undefined}
            onClick={() => aplicar({ aba: a.id === "geral" ? undefined : a.id })}
          >
            {aba === a.id && (
              <motion.span
                layoutId="rel-tab-pill"
                className={styles.segPill}
                transition={transicaoPill}
                aria-hidden
              />
            )}
            <span className={styles.segRotulo}>{a.rotulo}</span>
          </button>
        ))}
      </motion.div>

      <motion.div className={styles.filtros} variants={itemVar}>
        <div className={styles.linhaFiltros}>
          <div className={styles.campoData}>
            <span className={styles.campoDataPrefixo}>De</span>
            <input
              type="date"
              aria-label="Data inicial"
              value={filtros.de ?? ""}
              onChange={(e) => aplicar({ de: e.target.value || undefined, preset: undefined })}
              onClick={(e) => abrirCalendario(e.currentTarget)}
            />
            <Calendar className={styles.campoDataIcone} aria-hidden />
          </div>
          <div className={styles.campoData}>
            <span className={styles.campoDataPrefixo}>Até</span>
            <input
              type="date"
              aria-label="Data final"
              value={filtros.ate ?? ""}
              onChange={(e) => aplicar({ ate: e.target.value || undefined, preset: undefined })}
              onClick={(e) => abrirCalendario(e.currentTarget)}
            />
            <Calendar className={styles.campoDataIcone} aria-hidden />
          </div>
          <div className={styles.presets} role="group" aria-label="Período rápido">
            {PRESETS.map((p) => (
              <button
                key={p.rotulo}
                type="button"
                className={styles.preset}
                data-ativo={presetAtivo(p) || undefined}
                onClick={() => aplicar({ de: p.de(), ate: p.ate(), preset: p.rotulo })}
              >
                {presetAtivo(p) && (
                  <motion.span
                    layoutId="rel-presets-pill"
                    className={styles.segPill}
                    transition={transicaoPill}
                    aria-hidden
                  />
                )}
                <span className={styles.segRotulo}>{p.rotulo}</span>
              </button>
            ))}
          </div>
          <div className={styles.dropdownCampo}>
            <Dropdown<string>
              ariaLabel="Filtrar por status"
              variante="branco"
              value={filtros.status ?? ""}
              onChange={(v) => aplicar({ status: v || undefined })}
              opcoes={statusOpcoes}
            />
          </div>
        </div>

        <div className={styles.linhaFiltros}>
          <span className={styles.busca}>
            <Search aria-hidden />
            <input
              type="search"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar por nome, cliente ou nº requerimento"
              aria-label="Buscar"
            />
          </span>
          <div className={styles.toggleRota} role="group" aria-label="Filtrar por rota">
            {GRUPOS_ROTA.map((g) => {
              const ativo = (filtros.grupoRota ?? "") === g.id;
              return (
                <button
                  key={g.id || "todas"}
                  type="button"
                  className={styles.opcaoRota}
                  data-ativo={ativo || undefined}
                  onClick={() => aplicar({ rota: g.id || undefined })}
                >
                  {ativo && (
                    <motion.span
                      layoutId="rel-rota-pill"
                      className={styles.segPill}
                      transition={transicaoPill}
                      aria-hidden
                    />
                  )}
                  <span className={styles.segRotulo}>{g.rotulo}</span>
                </button>
              );
            })}
          </div>
          <div className={styles.dropdownCampo}>
            <Dropdown<string>
              ariaLabel="Filtrar por vendedor"
              variante="branco"
              value={filtros.vendedorId ?? ""}
              onChange={(v) => aplicar({ vendedor: v || undefined })}
              opcoes={vendedorOpcoes}
            />
          </div>
        </div>
      </motion.div>

      <motion.div
        key={aba}
        className={styles.conteudo}
        role="tabpanel"
        variants={itemVar}
        initial="hidden"
        animate="show"
      >
        {aba === "geral" ? (
          <GeralTab filtros={filtros} chave={chaveFiltros} />
        ) : aba === "studio" ? (
          <StudioTab filtros={filtros} chave={chaveFiltros} />
        ) : aba === "vendedores" ? (
          <VendedoresTab filtros={filtros} chave={chaveFiltros} />
        ) : (
          <ClicheriaTab filtros={filtros} chave={chaveFiltros} />
        )}
      </motion.div>
    </motion.section>
  );
}
