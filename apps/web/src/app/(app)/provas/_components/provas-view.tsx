"use client";

/**
 * Listagem de provas (W2-C07) — tela de operação diária.
 *
 * Tabela REPLICADA do C04 (DP-1): mesmo card/colunas/scroll/pills. Busca com
 * debounce ≥300ms (RNF-023) e paginação por scroll infinito server-side
 * (RNF-019), no MESMO padrão do Gerenciador de Usuários. O ESCOPO de dado é da
 * RLS de `provas` (C06): a UI só ADAPTA a barra (esconde "Vendedor" quando o
 * escopo é "as próprias" — DP-2). Estado de filtros/paginação na URL (DP-5):
 * refresh-safe e compartilhável; "Limpar" zera a query. Dados como estado
 * DERIVADO da chave de filtros (a chave = a query da URL): resposta atrasada de
 * filtro antigo nunca "vaza" para a tela.
 */
import { motion } from "framer-motion";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Dropdown } from "@/components/ui/select/Dropdown";
import { ApiError } from "@/lib/api/client";
import {
  ROTAS_ORDEM_UI,
  ROTA_LABELS,
  listarProvas,
  listarVendedoresProvas,
  type EscopoProvas,
  type FiltrosProvas,
  type ProvaListagem,
  type VendedorRef,
} from "@/lib/api/provas";
import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING } from "@/lib/motion/tokens";
import { STATUS_PROVA_LABELS, STATUS_PROVA_ORDEM, rotuloStatus } from "@/lib/provas/status-labels";

import styles from "../provas.module.css";

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;

type Resultado = { chave: string; itens: ProvaListagem[]; total: number; pagina: number };
type Falha = { chave: string; tipo: "erro" | "acesso_negado" };

function formatarData(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  // Em UTC para casar com o limite de dia do filtro (o backend compara o dia em
  // UTC); evita a prova filtrada em "09/04" aparecer como "08/04" na coluna.
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}-${mm}-${d.getUTCFullYear()}`;
}

export function ProvasView({ escopo }: { escopo: EscopoProvas }) {
  const reduced = useReducedMotion();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const chave = searchParams.toString();

  // "Vendedor" só faz sentido para quem vê provas de vários vendedores (DP-2).
  const mostrarFiltroVendedor = escopo !== "proprias";

  // Inputs de texto: estado local (digitação fluida) + debounce → URL.
  const [busca, setBusca] = useState(() => searchParams.get("busca") ?? "");
  const [cliente, setCliente] = useState(() => searchParams.get("cliente") ?? "");

  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [falha, setFalha] = useState<Falha | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const [falhaPaginacaoEm, setFalhaPaginacaoEm] = useState<string | null>(null);
  const [vendedores, setVendedores] = useState<VendedorRef[]>([]);

  const corpoRef = useRef<HTMLDivElement | null>(null);
  const sentinelaRef = useRef<HTMLDivElement | null>(null);

  // Refs "último valor" para os efeitos de debounce não dependerem da URL
  // (evita reiniciar o timer a cada mudança de query).
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
  // Atualiza os refs FORA do render (regra react-hooks/refs).
  useEffect(() => {
    searchParamsRef.current = searchParams;
    aplicarParamRef.current = aplicarParam;
  });

  const lerFiltros = useCallback((): FiltrosProvas => {
    const sp = searchParamsRef.current;
    return {
      busca: sp.get("busca") ?? undefined,
      cliente: sp.get("cliente") ?? undefined,
      status: (sp.get("status") as FiltrosProvas["status"]) ?? undefined,
      rota: (sp.get("rota") as FiltrosProvas["rota"]) ?? undefined,
      vendedorId: sp.get("vendedor") ?? undefined,
      criada: sp.get("criada") ?? undefined,
      finalizada: sp.get("finalizada") ?? undefined,
    };
  }, []);

  // Busca/Cliente com debounce ≥300ms — nada de requisição a cada tecla (RNF-023).
  useEffect(() => {
    const timer = setTimeout(() => {
      const atual = searchParamsRef.current.get("busca") ?? "";
      if (busca.trim() !== atual) aplicarParamRef.current({ busca: busca.trim() || undefined });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [busca]);

  useEffect(() => {
    const timer = setTimeout(() => {
      const atual = searchParamsRef.current.get("cliente") ?? "";
      if (cliente.trim() !== atual)
        aplicarParamRef.current({ cliente: cliente.trim() || undefined });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [cliente]);

  // Vendedores do dropdown (escopados) — só quando o filtro aparece.
  useEffect(() => {
    if (!mostrarFiltroVendedor) return;
    const controller = new AbortController();
    listarVendedoresProvas(controller.signal)
      .then(setVendedores)
      .catch(() => {
        /* dropdown vazio degrada para "Todos" — a RLS ainda escopa os dados */
      });
    return () => controller.abort();
  }, [mostrarFiltroVendedor]);

  // Primeira página da chave corrente (e refetch via `tentativa`).
  useEffect(() => {
    const controller = new AbortController();
    listarProvas({ ...lerFiltros(), page: 1, pageSize: PAGE_SIZE }, controller.signal)
      .then((pagina) => {
        setResultado({ chave, itens: pagina.items, total: pagina.total, pagina: 1 });
        setFalha(null);
        setFalhaPaginacaoEm(null);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setFalha({
          chave,
          tipo: error instanceof ApiError && error.status === 403 ? "acesso_negado" : "erro",
        });
      });
    return () => controller.abort();
  }, [chave, tentativa, lerFiltros]);

  const pronto = resultado?.chave === chave ? resultado : null;
  const falhaAtual = falha?.chave === chave ? falha.tipo : null;
  const carregando = pronto === null && falhaAtual === null;
  const itens = pronto?.itens ?? [];
  const total = pronto?.total ?? 0;

  const carregarMais = useCallback(
    async (manual = false) => {
      if (carregandoMais || pronto === null || pronto.itens.length >= pronto.total) return;
      if (!manual && falhaPaginacaoEm === chave) return; // sem auto-retry em loop
      setCarregandoMais(true);
      try {
        const proxima = pronto.pagina + 1;
        const pagina = await listarProvas({ ...lerFiltros(), page: proxima, pageSize: PAGE_SIZE });
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

  // Scroll infinito: sentinela observada DENTRO da área rolável da tabela.
  useEffect(() => {
    const sentinela = sentinelaRef.current;
    if (!sentinela || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) void carregarMais();
      },
      { root: corpoRef.current, rootMargin: "120px" },
    );
    observer.observe(sentinela);
    return () => observer.disconnect();
  }, [carregarMais]);

  function limpar() {
    setBusca("");
    setCliente("");
    router.replace(pathname, { scroll: false });
  }

  function abrirDetalhe(id: string) {
    router.push(`/provas/${id}`);
  }

  const verBotao = (prova: ProvaListagem) => (
    <button type="button" className={styles.botaoVer} onClick={() => abrirDetalhe(prova.id)}>
      Ver
    </button>
  );

  const linhas = itens.map((prova, indice) => (
    <motion.div
      role="row"
      key={prova.id}
      className={`${styles.linha} ${styles.grade}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{
        duration: reduced ? DURATION.instant : DURATION.short,
        delay: reduced ? 0 : Math.min(indice % PAGE_SIZE, 12) * 0.025,
        ease: EASING.emphasized,
      }}
    >
      <span role="cell" className={styles.celula}>
        {prova.requerimento}
      </span>
      <span role="cell" className={styles.celula}>
        {prova.nome}
      </span>
      <span role="cell" className={styles.celula}>
        {prova.cliente}
      </span>
      <span role="cell" className={styles.celula}>
        {prova.vendedor_nome ?? "—"}
      </span>
      <span role="cell" className={styles.celula}>
        {rotuloStatus(prova.status)}
      </span>
      <span role="cell" className={styles.celula}>
        {ROTA_LABELS[prova.rota]}
      </span>
      <span role="cell" className={styles.celula}>
        {formatarData(prova.created_at)}
      </span>
      <span role="cell" className={`${styles.celula} ${styles.celulaAcoes}`}>
        {verBotao(prova)}
      </span>
    </motion.div>
  ));

  const cartoes = itens.map((prova) => (
    <li key={prova.id} className={styles.cartao}>
      <div className={styles.cartaoTopo}>
        <p className={styles.cartaoNome}>{prova.nome}</p>
        <span className={styles.cartaoReq}>{prova.requerimento}</span>
      </div>
      <p className={styles.cartaoMeta}>
        {prova.cliente} · {prova.vendedor_nome ?? "—"} · {rotuloStatus(prova.status)} ·{" "}
        {ROTA_LABELS[prova.rota]} · {formatarData(prova.created_at)}
      </p>
      <div className={styles.cartaoAcoes}>{verBotao(prova)}</div>
    </li>
  ));

  const statusOpcoes = [
    { value: "", label: "Todos" },
    ...STATUS_PROVA_ORDEM.map((s) => ({ value: s, label: STATUS_PROVA_LABELS[s] })),
  ];
  const rotaOpcoes = [
    { value: "", label: "Todos" },
    ...ROTAS_ORDEM_UI.map((r) => ({ value: r, label: ROTA_LABELS[r] })),
  ];
  const vendedorOpcoes = [
    { value: "", label: "Todos" },
    ...vendedores.map((v) => ({ value: v.id, label: v.nome })),
  ];

  return (
    <section className={styles.pagina} aria-label="Provas digitais">
      <h1 className={styles.titulo}>Provas digitais</h1>

      <div className={styles.filtros}>
        <label className={styles.campo}>
          <span className={styles.rotuloCampo}>Buscar nome ou requerimento:</span>
          <span className={styles.controle}>
            <input
              type="search"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="123456"
              className={styles.input}
            />
          </span>
        </label>

        <label className={styles.campo}>
          <span className={styles.rotuloCampo}>Cliente:</span>
          <span className={styles.controle}>
            <input
              type="text"
              value={cliente}
              onChange={(e) => setCliente(e.target.value)}
              placeholder="Nome do cliente"
              className={styles.input}
            />
          </span>
        </label>

        <div className={styles.campo}>
          <span className={styles.rotuloCampo}>Status:</span>
          <span className={styles.controle}>
            <Dropdown<string>
              ariaLabel="Filtrar por status"
              value={searchParams.get("status") ?? ""}
              onChange={(v) => aplicarParam({ status: v || undefined })}
              opcoes={statusOpcoes}
            />
          </span>
        </div>

        <div className={styles.campo}>
          <span className={styles.rotuloCampo}>Rota:</span>
          <span className={styles.controle}>
            <Dropdown<string>
              ariaLabel="Filtrar por rota"
              value={searchParams.get("rota") ?? ""}
              onChange={(v) => aplicarParam({ rota: v || undefined })}
              opcoes={rotaOpcoes}
            />
          </span>
        </div>

        {mostrarFiltroVendedor ? (
          <div className={styles.campo}>
            <span className={styles.rotuloCampo}>Vendedor:</span>
            <span className={styles.controle}>
              <Dropdown<string>
                ariaLabel="Filtrar por vendedor"
                value={searchParams.get("vendedor") ?? ""}
                onChange={(v) => aplicarParam({ vendedor: v || undefined })}
                opcoes={vendedorOpcoes}
              />
            </span>
          </div>
        ) : (
          // Espaçador: mantém "Limpar" na 4ª coluna da 2ª linha quando o filtro
          // Vendedor está escondido (escopo "as próprias").
          <div aria-hidden />
        )}

        <label className={styles.campo}>
          <span className={styles.rotuloCampo}>Criada em:</span>
          <span className={styles.controle}>
            <input
              type="date"
              value={searchParams.get("criada") ?? ""}
              onChange={(e) => aplicarParam({ criada: e.target.value || undefined })}
              className={`${styles.input} ${styles.inputData}`}
            />
          </span>
        </label>

        <label className={styles.campo}>
          <span className={styles.rotuloCampo}>Finalizada em:</span>
          <span className={styles.controle}>
            <input
              type="date"
              value={searchParams.get("finalizada") ?? ""}
              onChange={(e) => aplicarParam({ finalizada: e.target.value || undefined })}
              className={`${styles.input} ${styles.inputData}`}
            />
          </span>
        </label>

        <button type="button" className={styles.botaoLimpar} onClick={limpar}>
          Limpar
        </button>
      </div>

      {falhaAtual === "acesso_negado" ? (
        <p className={styles.estadoVazio} role="alert">
          Você não tem acesso a esta listagem.
        </p>
      ) : falhaAtual === "erro" ? (
        <p className={styles.estadoVazio} role="alert">
          Não foi possível carregar as provas.{" "}
          <button
            type="button"
            className={styles.tentarNovamente}
            onClick={() => {
              setFalha(null);
              setTentativa((t) => t + 1);
            }}
          >
            Tentar novamente
          </button>
        </p>
      ) : (
        <>
          {/* Tabela (desktop) */}
          <div role="table" aria-label="Provas" className={styles.card}>
            <div role="rowgroup" className={styles.cabecalhoTabela}>
              <div role="row" className={`${styles.linhaCabecalho} ${styles.grade}`}>
                <span role="columnheader" className={styles.celula}>
                  Requerimento
                </span>
                <span role="columnheader" className={styles.celula}>
                  Nome
                </span>
                <span role="columnheader" className={styles.celula}>
                  Cliente
                </span>
                <span role="columnheader" className={styles.celula}>
                  Vendedor
                </span>
                <span role="columnheader" className={styles.celula}>
                  Status
                </span>
                <span role="columnheader" className={styles.celula}>
                  Rota
                </span>
                <span role="columnheader" className={styles.celula}>
                  Criada em
                </span>
                <span role="columnheader" className={styles.celula} aria-label="Ações" />
              </div>
            </div>
            <div role="rowgroup" className={styles.corpoTabela} ref={corpoRef}>
              {carregando ? (
                <div className={styles.skeletons} aria-hidden>
                  {Array.from({ length: 7 }, (_, i) => (
                    <div key={i} className={`${styles.linha} ${styles.grade} ${styles.skeleton}`} />
                  ))}
                </div>
              ) : itens.length === 0 ? (
                <div role="row" className={styles.grade}>
                  <span role="cell" className={`${styles.celula} ${styles.celulaVazia}`}>
                    Nenhuma prova encontrada.
                  </span>
                </div>
              ) : (
                linhas
              )}
              <div ref={sentinelaRef} aria-hidden />
              {carregandoMais && (
                <div role="row" className={styles.grade}>
                  <span role="cell" className={`${styles.celula} ${styles.celulaVazia}`}>
                    Carregando…
                  </span>
                </div>
              )}
              {falhaPaginacaoEm === chave && !carregandoMais && (
                <div role="row" className={styles.grade}>
                  <span role="cell" className={`${styles.celula} ${styles.celulaVazia}`}>
                    Falha ao carregar mais provas.{" "}
                    <button
                      type="button"
                      className={styles.tentarNovamente}
                      onClick={() => void carregarMais(true)}
                    >
                      Tentar novamente
                    </button>
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Cards (mobile) */}
          <ul className={styles.cartoes} aria-label="Provas">
            {carregando ? (
              <li className={`${styles.cartao} ${styles.skeleton}`} aria-hidden />
            ) : itens.length === 0 ? (
              <li className={styles.estadoVazio}>Nenhuma prova encontrada.</li>
            ) : (
              cartoes
            )}
            {itens.length > 0 && itens.length < total && (
              <li className={styles.cartaoCarregarMais}>
                <button
                  type="button"
                  className={styles.botaoCarregarMais}
                  onClick={() => void carregarMais(true)}
                  disabled={carregandoMais}
                >
                  {carregandoMais ? "Carregando…" : "Carregar mais"}
                </button>
              </li>
            )}
          </ul>
        </>
      )}
    </section>
  );
}
