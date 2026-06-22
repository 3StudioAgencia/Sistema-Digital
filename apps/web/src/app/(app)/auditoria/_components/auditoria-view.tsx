"use client";

/**
 * Log de Auditoria (W6-C20) — master-detail fiel ao design, read-only, 3Studio-only.
 *
 * Cabeçalho + barra de filtros (presets/Eventos/Ator/Ordem/busca/De/Até/Linhas) +
 * dois painéis: a lista rolável (ponto colorido por tipo de evento, nome do evento,
 * ator, hora) e o painel de detalhe (Ator/Setor/Prova/IP/Origem/Data + rodapé
 * "Registro íntegro e imutável" com o hash do chain). Estado de filtros na URL
 * (refresh-safe — reusa o padrão do C07); busca com debounce ≥300ms; paginação por
 * scroll infinito server-side. No mobile, lista → detalhe em drill-in. A
 * imutabilidade é estrutural; a tela só LÊ (e oferece a verificação do chain).
 */
import { motion } from "framer-motion";
import { ArrowLeft, Calendar, Search, ShieldCheck } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Dropdown } from "@/components/ui/select/Dropdown";
import { useToast } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import {
  listarAtoresAuditoria,
  listarAuditoria,
  verificarIntegridadeAuditoria,
  type AtorAuditoria,
  type FiltrosAuditoria,
  type OrdemAuditoria,
  type RegistroAuditoria,
} from "@/lib/api/auditoria";
import { EVENTO_ORDEM, EVENTO_LABELS, corEvento, rotuloEvento } from "@/lib/auditoria/evento-labels";
import { useReducedMotion } from "@/lib/motion/hooks";
import { REVEAL_OFFSET, STAGGER } from "@/lib/motion/tokens";
import { fadeRise, staggerContainer } from "@/lib/motion/variants";
import { rotuloStatus } from "@/lib/provas/status-labels";

import styles from "../auditoria.module.css";

const DEBOUNCE_MS = 300;

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

function formatarHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
function formatarDataHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

type Resultado = { chave: string; itens: RegistroAuditoria[]; total: number; pagina: number };

export function AuditoriaView() {
  const reduced = useReducedMotion();
  const containerVar = staggerContainer(reduced);
  const itemVar = fadeRise(reduced);
  const linhaVar = fadeRise(reduced, { dx: REVEAL_OFFSET.x, dy: 0 });
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const toast = useToast();
  const chave = searchParams.toString();

  const [busca, setBusca] = useState(() => searchParams.get("busca") ?? "");
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [falha, setFalha] = useState<"erro" | "acesso_negado" | null>(null);
  const [falhaChave, setFalhaChave] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const [falhaPaginacaoEm, setFalhaPaginacaoEm] = useState<string | null>(null);
  const [atores, setAtores] = useState<AtorAuditoria[]>([]);
  const [selId, setSelId] = useState<string | null>(null);
  const [detalheMobile, setDetalheMobile] = useState(false);
  const [verificando, setVerificando] = useState(false);

  const listaRef = useRef<HTMLDivElement | null>(null);
  const sentinelaRef = useRef<HTMLDivElement | null>(null);
  const searchParamsRef = useRef(searchParams);

  const aplicarParam = useCallback(
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
  const aplicarParamRef = useRef(aplicarParam);
  useEffect(() => {
    searchParamsRef.current = searchParams;
    aplicarParamRef.current = aplicarParam;
  });

  const lerFiltros = useCallback((): FiltrosAuditoria => {
    const sp = searchParamsRef.current;
    return {
      evento: (sp.get("evento") as FiltrosAuditoria["evento"]) ?? undefined,
      atorId: sp.get("ator") ?? undefined,
      busca: sp.get("busca") ?? undefined,
      de: sp.get("de") ?? undefined,
      ate: sp.get("ate") ?? undefined,
      ordem: (sp.get("ordem") as OrdemAuditoria | null) ?? undefined,
      pageSize: Number(sp.get("linhas")) || 50,
    };
  }, []);

  // Busca com debounce ≥300ms (RNF-023).
  useEffect(() => {
    const timer = setTimeout(() => {
      const atual = searchParamsRef.current.get("busca") ?? "";
      if (busca.trim() !== atual) aplicarParamRef.current({ busca: busca.trim() || undefined });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [busca]);

  // Atores do dropdown (escopados — admin).
  useEffect(() => {
    const controller = new AbortController();
    listarAtoresAuditoria(controller.signal)
      .then(setAtores)
      .catch(() => {
        /* dropdown vazio degrada para "Todos" */
      });
    return () => controller.abort();
  }, []);

  // Primeira página da chave corrente (e refetch via `tentativa`).
  useEffect(() => {
    const controller = new AbortController();
    listarAuditoria({ ...lerFiltros(), page: 1 }, controller.signal)
      .then((pagina) => {
        setResultado({ chave, itens: pagina.items, total: pagina.total, pagina: 1 });
        setFalha(null);
        setFalhaChave(null);
        setFalhaPaginacaoEm(null);
        setSelId(null); // volta a selecionar o 1º item da nova consulta
        setDetalheMobile(false);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setFalha(error instanceof ApiError && error.status === 403 ? "acesso_negado" : "erro");
        setFalhaChave(chave);
      });
    return () => controller.abort();
  }, [chave, tentativa, lerFiltros]);

  const pronto = resultado?.chave === chave ? resultado : null;
  const falhaAtual = falhaChave === chave ? falha : null;
  const carregando = pronto === null && falhaAtual === null;
  const itens = useMemo(() => pronto?.itens ?? [], [pronto]);

  const selecionado = useMemo(
    () => itens.find((i) => i.id === selId) ?? itens[0] ?? null,
    [itens, selId],
  );

  const carregarMais = useCallback(
    async (manual = false) => {
      if (carregandoMais || pronto === null || pronto.itens.length >= pronto.total) return;
      if (!manual && falhaPaginacaoEm === chave) return;
      setCarregandoMais(true);
      try {
        const proxima = pronto.pagina + 1;
        const pagina = await listarAuditoria({ ...lerFiltros(), page: proxima });
        setResultado((atual) =>
          atual && atual.chave === chave
            ? {
                ...atual,
                itens: [...atual.itens, ...pagina.items],
                total: pagina.total,
                pagina: proxima,
              }
            : atual,
        );
        setFalhaPaginacaoEm(null);
      } catch {
        setFalhaPaginacaoEm(chave);
      } finally {
        setCarregandoMais(false);
      }
    },
    [carregandoMais, chave, falhaPaginacaoEm, lerFiltros, pronto],
  );

  useEffect(() => {
    const sentinela = sentinelaRef.current;
    if (!sentinela || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) void carregarMais();
      },
      { root: listaRef.current, rootMargin: "120px" },
    );
    observer.observe(sentinela);
    return () => observer.disconnect();
  }, [carregarMais]);

  async function verificarIntegridade() {
    if (verificando) return;
    setVerificando(true);
    try {
      const r = await verificarIntegridadeAuditoria();
      if (r.intacto) {
        toast.success(`Registro íntegro e imutável (${r.total} eventos verificados).`);
      } else {
        toast.error(`Integridade comprometida: quebra a partir do evento #${r.quebrou_em}.`);
      }
    } catch {
      toast.error("Não foi possível verificar a integridade. Tente novamente.");
    } finally {
      setVerificando(false);
    }
  }

  function selecionar(registro: RegistroAuditoria) {
    setSelId(registro.id);
    setDetalheMobile(true);
  }

  const presetSelecionado = searchParams.get("preset") ?? "";

  const eventoOpcoes = [
    { value: "", label: "Eventos: Todos" },
    ...EVENTO_ORDEM.map((e) => ({ value: e, label: EVENTO_LABELS[e] })),
  ];
  const atorOpcoes = [
    { value: "", label: "Ator: Todos" },
    ...atores.map((a) => ({ value: a.id, label: a.nome ?? "—" })),
  ];
  const ordemOpcoes = [
    { value: "recentes", label: "Ordem: Recentes" },
    { value: "antigos", label: "Ordem: Antigos" },
  ];
  const linhasOpcoes = ["25", "50", "100", "200"].map((n) => ({ value: n, label: `Linhas: ${n}` }));

  return (
    <motion.section
      className={styles.pagina}
      aria-label="Auditoria"
      variants={containerVar}
      initial="hidden"
      animate="show"
    >
      <motion.header className={styles.cabecalho} variants={itemVar}>
        <div>
          <h1 className={styles.titulo}>Auditoria</h1>
          <p className={styles.subtitulo}>Log imutável de todas as ações do sistema</p>
        </div>
        <button
          type="button"
          className={styles.btnVerificar}
          onClick={() => void verificarIntegridade()}
          disabled={verificando}
        >
          <ShieldCheck aria-hidden /> {verificando ? "Verificando…" : "Verificar integridade"}
        </button>
      </motion.header>

      {/* Barra de filtros (DP-2) */}
      <motion.div className={styles.filtros} variants={itemVar}>
        <div className={styles.linhaFiltros}>
          <div className={styles.presets} role="group" aria-label="Período rápido">
            {PRESETS.map((p) => (
              <button
                key={p.rotulo}
                type="button"
                className={styles.preset}
                data-ativo={presetSelecionado === p.rotulo || undefined}
                onClick={() => aplicarParam({ de: p.de(), ate: p.ate(), preset: p.rotulo })}
              >
                {p.rotulo}
              </button>
            ))}
          </div>
          <Dropdown<string>
            ariaLabel="Filtrar por tipo de evento"
            variante="branco"
            value={searchParams.get("evento") ?? ""}
            onChange={(v) => aplicarParam({ evento: v || undefined })}
            opcoes={eventoOpcoes}
          />
          <Dropdown<string>
            ariaLabel="Filtrar por ator"
            variante="branco"
            value={searchParams.get("ator") ?? ""}
            onChange={(v) => aplicarParam({ ator: v || undefined })}
            opcoes={atorOpcoes}
          />
          <Dropdown<string>
            ariaLabel="Ordenar"
            variante="branco"
            value={searchParams.get("ordem") ?? "recentes"}
            onChange={(v) => aplicarParam({ ordem: v === "antigos" ? "antigos" : undefined })}
            opcoes={ordemOpcoes}
          />
        </div>

        <div className={styles.linhaFiltros}>
          <span className={styles.busca}>
            <Search aria-hidden />
            <input
              type="search"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Motivo, cliente ou nº requerimento"
              aria-label="Buscar"
            />
          </span>
          <label className={styles.campoData}>
            <span className={styles.campoDataPrefixo}>De</span>
            <input
              type="date"
              aria-label="Data inicial"
              value={searchParams.get("de") ?? ""}
              onChange={(e) => aplicarParam({ de: e.target.value || undefined, preset: undefined })}
            />
            <Calendar className={styles.campoDataIcone} aria-hidden />
          </label>
          <label className={styles.campoData}>
            <span className={styles.campoDataPrefixo}>Até</span>
            <input
              type="date"
              aria-label="Data final"
              value={searchParams.get("ate") ?? ""}
              onChange={(e) => aplicarParam({ ate: e.target.value || undefined, preset: undefined })}
            />
            <Calendar className={styles.campoDataIcone} aria-hidden />
          </label>
          <Dropdown<string>
            ariaLabel="Linhas por página"
            variante="branco"
            value={searchParams.get("linhas") ?? "50"}
            onChange={(v) => aplicarParam({ linhas: v === "50" ? undefined : v })}
            opcoes={linhasOpcoes}
          />
        </div>
      </motion.div>

      {/* Master-detail */}
      <motion.div
        className={styles.painel}
        data-mostrando={detalheMobile ? "detalhe" : "lista"}
        variants={itemVar}
      >
        {falhaAtual === "acesso_negado" ? (
          <p className={styles.estadoVazio} role="alert">
            Você não tem acesso ao log de auditoria.
          </p>
        ) : falhaAtual === "erro" ? (
          <p className={styles.estadoVazio} role="alert">
            Não foi possível carregar o log.{" "}
            <button
              type="button"
              className={styles.tentarNovamente}
              onClick={() => {
                setFalha(null);
                setFalhaChave(null);
                setTentativa((t) => t + 1);
              }}
            >
              Tentar novamente
            </button>
          </p>
        ) : (
          <>
            {/* Lista (esquerda) */}
            <div className={styles.lista} ref={listaRef} aria-label="Eventos do log">
              {carregando ? (
                <div className={styles.skeletons} aria-hidden>
                  {Array.from({ length: 8 }, (_, i) => (
                    <div key={i} className={`${styles.itemLista} ${styles.skeleton}`} />
                  ))}
                </div>
              ) : itens.length === 0 ? (
                <p className={styles.estadoVazio}>Nenhum evento encontrado.</p>
              ) : (
                <motion.ul
                  className={styles.listaUl}
                  variants={staggerContainer(reduced)}
                  initial="hidden"
                  animate="show"
                >
                  {itens.map((registro, indice) => {
                    const ativo = selecionado?.id === registro.id;
                    const conteudo = (
                      <button
                        type="button"
                        className={styles.itemLista}
                        data-ativo={ativo || undefined}
                        onClick={() => selecionar(registro)}
                      >
                        <span
                          className={styles.ponto}
                          style={{ backgroundColor: corEvento(registro.evento) }}
                          aria-hidden
                        />
                        <span className={styles.itemTexto}>
                          <span className={styles.itemEvento}>{rotuloEvento(registro.evento)}</span>
                          <span className={styles.itemAtor}>{registro.ator_nome ?? "—"}</span>
                        </span>
                        <span className={styles.itemHora}>{formatarHora(registro.created_at)}</span>
                      </button>
                    );
                    return (
                      <li key={registro.id}>
                        {indice < STAGGER.maxItens ? (
                          <motion.div variants={linhaVar}>{conteudo}</motion.div>
                        ) : (
                          conteudo
                        )}
                      </li>
                    );
                  })}
                  <div ref={sentinelaRef} aria-hidden />
                  {carregandoMais && <p className={styles.carregandoMais}>Carregando…</p>}
                  {falhaPaginacaoEm === chave && !carregandoMais && (
                    <p className={styles.carregandoMais}>
                      Falha ao carregar mais.{" "}
                      <button
                        type="button"
                        className={styles.tentarNovamente}
                        onClick={() => void carregarMais(true)}
                      >
                        Tentar novamente
                      </button>
                    </p>
                  )}
                </motion.ul>
              )}
            </div>

            {/* Detalhe (direita) */}
            <div className={styles.detalhe}>
              {selecionado ? (
                <Detalhe registro={selecionado} onVoltar={() => setDetalheMobile(false)} />
              ) : !carregando ? (
                <p className={styles.detalheVazio}>Selecione um evento para ver os detalhes.</p>
              ) : null}
            </div>
          </>
        )}
      </motion.div>
    </motion.section>
  );
}

function Campo({ rotulo, valor }: { rotulo: string; valor: string | null }) {
  return (
    <div className={styles.campoDetalhe}>
      <span className={styles.campoRotulo}>{rotulo}</span>
      <span className={styles.campoValor}>{valor ?? "—"}</span>
    </div>
  );
}

function Detalhe({
  registro,
  onVoltar,
}: {
  registro: RegistroAuditoria;
  onVoltar: () => void;
}) {
  const setorLabel =
    registro.ator_setor === "studio" ? "3Studio" : (registro.ator_setor ?? "—");
  const prova = registro.prova_requerimento ?? registro.prova_codigo ?? null;
  const transicao =
    registro.estado_origem && registro.estado_destino
      ? `${rotuloStatus(registro.estado_origem)} → ${rotuloStatus(registro.estado_destino)}`
      : null;
  return (
    <div className={styles.detalheCard}>
      <button type="button" className={styles.btnVoltar} onClick={onVoltar}>
        <ArrowLeft aria-hidden /> Voltar
      </button>
      <div className={styles.detalheTitulo}>
        <span
          className={styles.pontoGrande}
          style={{ backgroundColor: corEvento(registro.evento) }}
          aria-hidden
        />
        <div>
          <h2>{rotuloEvento(registro.evento)}</h2>
          <p className={styles.registradoPor}>Registrado por {registro.ator_nome ?? "—"}</p>
        </div>
      </div>

      <div className={styles.detalheGrid}>
        <Campo rotulo="Ator" valor={registro.ator_nome} />
        <Campo rotulo="Setor" valor={setorLabel} />
        <Campo rotulo="Prova" valor={prova} />
        <Campo rotulo="Endereço IP" valor={registro.ip} />
        <Campo rotulo="Data e hora" valor={formatarDataHora(registro.created_at)} />
        <Campo rotulo="Origem" valor={registro.origem} />
        {transicao ? <Campo rotulo="Transição" valor={transicao} /> : null}
        {registro.motivo ? <Campo rotulo="Motivo" valor={registro.motivo} /> : null}
      </div>

      <div className={styles.integridade}>
        <span className={styles.integridadeRotulo}>
          <ShieldCheck aria-hidden /> Registro íntegro e imutável
        </span>
        <span className={styles.hash} title={registro.hash}>
          sha256:{registro.hash.slice(0, 24)}…
        </span>
      </div>
    </div>
  );
}
