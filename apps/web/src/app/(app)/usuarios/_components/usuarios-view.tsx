"use client";

/**
 * Gerenciador de usuários (W1-C04) — tabela fiel ao design, busca com debounce
 * ≥300ms (RNF-023), filtros server-side e paginação por scroll infinito dentro
 * da área rolável da tabela (RNF-019; mantém o visual do Figma, sem paginador).
 *
 * Dados modelados como estado DERIVADO da chave de filtros: o efeito só agenda
 * a busca (nenhum setState síncrono) e a resposta carrega a chave a que
 * pertence — respostas atrasadas de filtros antigos nunca "vazam" para a tela.
 * Mutações atualizam a lista em memória com a resposta do backend (mínimo de
 * requisições — RNF-020); criar refaz a primeira página.
 */
import { motion } from "framer-motion";
import { ChevronDown, Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  LOCALIZACAO_LABELS,
  SETOR_LABELS,
  listarUsuarios,
  type Setor,
  type Usuario,
} from "@/lib/api/usuarios";
import { DURATION, EASING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";
import { useToast } from "@/components/ui/toast/ToastProvider";

import { ConfirmarStatusModal, type AcaoStatus } from "./confirmar-status-modal";
import { UsuarioFormModal, type EstadoForm } from "./usuario-form-modal";
import styles from "../usuarios.module.css";

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;

type Resultado = { chave: string; itens: Usuario[]; total: number };
type Falha = { chave: string; tipo: "erro" | "acesso_negado" };

export function UsuariosView() {
  const toast = useToast();
  const reduced = useReducedMotion();

  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [setor, setSetor] = useState<"" | Setor>("");
  const [statusFiltro, setStatusFiltro] = useState<"" | "ativo" | "inativo">("");

  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [falha, setFalha] = useState<Falha | null>(null);
  const [tentativa, setTentativa] = useState(0); // “tentar novamente” / pós-criação
  const [carregandoMais, setCarregandoMais] = useState(false);

  const [modalForm, setModalForm] = useState<EstadoForm | null>(null);
  const [confirmacao, setConfirmacao] = useState<{ usuario: Usuario; acao: AcaoStatus } | null>(
    null,
  );

  const corpoRef = useRef<HTMLDivElement | null>(null);
  const sentinelaRef = useRef<HTMLDivElement | null>(null);
  const paginaRef = useRef(1);

  const chaveFiltros = `${buscaAplicada}|${setor}|${statusFiltro}`;

  // Busca com debounce ≥ 300 ms — nada de requisição a cada tecla (RNF-023).
  useEffect(() => {
    const timer = setTimeout(() => setBuscaAplicada(busca.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [busca]);

  // Primeira página da chave corrente (e refetch via `tentativa`).
  useEffect(() => {
    const controller = new AbortController();
    listarUsuarios(
      { busca: buscaAplicada, setor, status: statusFiltro, page: 1, pageSize: PAGE_SIZE },
      controller.signal,
    )
      .then((pagina) => {
        paginaRef.current = 1;
        setResultado({ chave: chaveFiltros, itens: pagina.items, total: pagina.total });
        setFalha(null);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setFalha({
          chave: chaveFiltros,
          tipo: error instanceof ApiError && error.status === 403 ? "acesso_negado" : "erro",
        });
      });
    return () => controller.abort();
  }, [buscaAplicada, setor, statusFiltro, chaveFiltros, tentativa]);

  const pronto = resultado?.chave === chaveFiltros ? resultado : null;
  const falhaAtual = falha?.chave === chaveFiltros ? falha.tipo : null;
  const carregando = pronto === null && falhaAtual === null;
  const itens = pronto?.itens ?? [];
  const total = pronto?.total ?? 0;

  const carregarMais = useCallback(async () => {
    if (carregandoMais || pronto === null || pronto.itens.length >= pronto.total) return;
    setCarregandoMais(true);
    try {
      const proxima = paginaRef.current + 1;
      const pagina = await listarUsuarios({
        busca: buscaAplicada,
        setor,
        status: statusFiltro,
        page: proxima,
        pageSize: PAGE_SIZE,
      });
      paginaRef.current = proxima;
      setResultado((atual) =>
        atual && atual.chave === chaveFiltros
          ? { ...atual, itens: [...atual.itens, ...pagina.items], total: pagina.total }
          : atual,
      );
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Falha ao carregar mais usuários.");
    } finally {
      setCarregandoMais(false);
    }
  }, [buscaAplicada, carregandoMais, chaveFiltros, pronto, setor, statusFiltro, toast]);

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

  function substituirItem(usuario: Usuario) {
    setResultado((atual) =>
      atual
        ? { ...atual, itens: atual.itens.map((u) => (u.id === usuario.id ? usuario : u)) }
        : atual,
    );
  }

  function aoSalvar(usuario: Usuario, modo: "criar" | "editar") {
    setModalForm(null);
    if (modo === "editar") {
      substituirItem(usuario);
      toast.success("Alterações salvas.");
    } else {
      toast.success("Usuário cadastrado.");
      setTentativa((t) => t + 1); // refaz a primeira página (lista ordenada por nome)
    }
  }

  function aoConfirmarStatus(usuario: Usuario) {
    setConfirmacao(null);
    substituirItem(usuario);
    toast.success(usuario.ativo ? "Usuário reativado." : "Usuário desativado.");
  }

  function botoesAcao(usuario: Usuario) {
    return (
      <>
        <button
          type="button"
          className={styles.botaoEditar}
          onClick={() => setModalForm({ modo: "editar", usuario })}
        >
          Editar
        </button>
        {usuario.ativo ? (
          <button
            type="button"
            className={styles.botaoDesativar}
            onClick={() => setConfirmacao({ usuario, acao: "desativar" })}
          >
            Desativar
          </button>
        ) : (
          <button
            type="button"
            className={styles.botaoReativar}
            onClick={() => setConfirmacao({ usuario, acao: "reativar" })}
          >
            Reativar
          </button>
        )}
      </>
    );
  }

  const linhas = itens.map((usuario, indice) => (
    <motion.div
      role="row"
      key={usuario.id}
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
        {usuario.nome}
      </span>
      <span role="cell" className={styles.celula}>
        {usuario.email}
      </span>
      <span role="cell" className={styles.celula}>
        {SETOR_LABELS[usuario.setor]}
      </span>
      <span role="cell" className={styles.celula}>
        {usuario.localizacao ? LOCALIZACAO_LABELS[usuario.localizacao] : "—"}
      </span>
      <span role="cell" className={styles.celula}>
        {usuario.ativo ? "Ativo" : "Inativo"}
      </span>
      <span role="cell" className={styles.celula}>
        {usuario.administrador ? "Admin" : "Usuário"}
      </span>
      <span role="cell" className={`${styles.celula} ${styles.celulaAcoes}`}>
        {botoesAcao(usuario)}
      </span>
    </motion.div>
  ));

  const cartoes = itens.map((usuario) => (
    <li key={usuario.id} className={styles.cartao}>
      <p className={styles.cartaoNome}>{usuario.nome}</p>
      <p className={styles.cartaoEmail}>{usuario.email}</p>
      <p className={styles.cartaoMeta}>
        {SETOR_LABELS[usuario.setor]}
        {usuario.localizacao ? ` · ${LOCALIZACAO_LABELS[usuario.localizacao]}` : ""} ·{" "}
        {usuario.ativo ? "Ativo" : "Inativo"} · {usuario.administrador ? "Admin" : "Usuário"}
      </p>
      <div className={styles.cartaoAcoes}>{botoesAcao(usuario)}</div>
    </li>
  ));

  return (
    <section className={styles.pagina} aria-label="Gerenciador de usuários">
      <header className={styles.cabecalhoPagina}>
        <h1 className={styles.titulo}>Gerenciador de usuários</h1>
        <button
          type="button"
          className={styles.botaoNovo}
          onClick={() => setModalForm({ modo: "criar" })}
        >
          Novo usuário
        </button>
      </header>

      <div className={styles.filtros}>
        <div className={styles.campoBusca}>
          <Search size={22} strokeWidth={2} className={styles.iconeBusca} aria-hidden />
          <input
            type="search"
            value={busca}
            onChange={(event) => setBusca(event.target.value)}
            placeholder="Buscar por nome ou email..."
            aria-label="Buscar por nome ou email"
            className={styles.inputBusca}
          />
        </div>
        <div className={styles.campoSelect}>
          <select
            value={setor}
            onChange={(event) => setSetor(event.target.value as "" | Setor)}
            aria-label="Filtrar por setor"
            className={styles.select}
          >
            <option value="">Todos os setores</option>
            <option value="studio">3Studio</option>
            <option value="vendedor">Vendedor</option>
            <option value="motorista">Motorista</option>
            <option value="clicheria">Clicheria</option>
          </select>
          <ChevronDown size={22} className={styles.chevron} aria-hidden />
        </div>
        <div className={styles.campoSelect}>
          <select
            value={statusFiltro}
            onChange={(event) => setStatusFiltro(event.target.value as "" | "ativo" | "inativo")}
            aria-label="Filtrar por status"
            className={styles.select}
          >
            <option value="">Todos</option>
            <option value="ativo">Ativos</option>
            <option value="inativo">Inativos</option>
          </select>
          <ChevronDown size={22} className={styles.chevron} aria-hidden />
        </div>
      </div>

      {falhaAtual === "acesso_negado" ? (
        <p className={styles.estadoVazio} role="alert">
          Acesso restrito a administradores.
        </p>
      ) : falhaAtual === "erro" ? (
        <p className={styles.estadoVazio} role="alert">
          Não foi possível carregar os usuários.{" "}
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
          <div role="table" aria-label="Usuários" className={styles.card}>
            <div role="rowgroup" className={styles.cabecalhoTabela}>
              <div role="row" className={`${styles.linhaCabecalho} ${styles.grade}`}>
                <span role="columnheader" className={styles.celula}>
                  Nome
                </span>
                <span role="columnheader" className={styles.celula}>
                  E-mail
                </span>
                <span role="columnheader" className={styles.celula}>
                  Setor
                </span>
                <span role="columnheader" className={styles.celula}>
                  Localização
                </span>
                <span role="columnheader" className={styles.celula}>
                  Status
                </span>
                <span role="columnheader" className={styles.celula}>
                  Perfil
                </span>
                <span role="columnheader" className={styles.celula}>
                  Ações
                </span>
              </div>
            </div>
            <div role="rowgroup" className={styles.corpoTabela} ref={corpoRef}>
              {carregando ? (
                <div className={styles.skeletons} aria-hidden>
                  {Array.from({ length: 6 }, (_, i) => (
                    <div key={i} className={`${styles.linha} ${styles.grade} ${styles.skeleton}`} />
                  ))}
                </div>
              ) : itens.length === 0 ? (
                <p className={styles.estadoVazio}>Nenhum usuário encontrado.</p>
              ) : (
                linhas
              )}
              <div ref={sentinelaRef} aria-hidden />
              {carregandoMais && <p className={styles.carregandoMais}>Carregando…</p>}
            </div>
          </div>

          {/* Cards (mobile — DP-7) */}
          <ul className={styles.cartoes} aria-label="Usuários">
            {carregando ? (
              <li className={`${styles.cartao} ${styles.skeleton}`} aria-hidden />
            ) : itens.length === 0 ? (
              <li className={styles.estadoVazio}>Nenhum usuário encontrado.</li>
            ) : (
              cartoes
            )}
            {itens.length > 0 && itens.length < total && (
              <li className={styles.cartaoCarregarMais}>
                <button
                  type="button"
                  className={styles.botaoCarregarMais}
                  onClick={() => void carregarMais()}
                  disabled={carregandoMais}
                >
                  {carregandoMais ? "Carregando…" : "Carregar mais"}
                </button>
              </li>
            )}
          </ul>
        </>
      )}

      <UsuarioFormModal estado={modalForm} onFechar={() => setModalForm(null)} onSalvo={aoSalvar} />
      <ConfirmarStatusModal
        confirmacao={confirmacao}
        onFechar={() => setConfirmacao(null)}
        onConfirmado={aoConfirmarStatus}
      />
    </section>
  );
}
