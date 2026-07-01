"use client";
import { motion } from "framer-motion";
import { Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  LOCALIZACAO_LABELS,
  SETOR_LABELS,
  listarUsuarios,
  type Setor,
  type Usuario,
} from "@/lib/api/usuarios";
import { STAGGER } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";
import { fadeRise, staggerContainer } from "@/lib/motion/variants";
import { Dropdown } from "@/components/ui/select/Dropdown";
import { useToast } from "@/components/ui/toast/ToastProvider";

import { ConfirmarStatusModal, type AcaoStatus } from "./confirmar-status-modal";
import { UsuarioFormModal, type EstadoForm } from "./usuario-form-modal";
import styles from "../usuarios.module.css";

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;

type Resultado = { chave: string; itens: Usuario[]; total: number; pagina: number };
type Falha = { chave: string; tipo: "erro" | "acesso_negado" };

export function UsuariosView() {
  const toast = useToast();
  const reduced = useReducedMotion();
  const containerVar = staggerContainer(reduced);
  const itemVar = fadeRise(reduced);
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [setor, setSetor] = useState<"" | Setor>("");
  const [statusFiltro, setStatusFiltro] = useState<"" | "ativo" | "inativo">("");
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [falha, setFalha] = useState<Falha | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const [falhaPaginacaoEm, setFalhaPaginacaoEm] = useState<string | null>(null);
  const [modalForm, setModalForm] = useState<EstadoForm | null>(null);
  const [confirmacao, setConfirmacao] = useState<{ usuario: Usuario; acao: AcaoStatus } | null>(
    null,
  );

  const corpoRef = useRef<HTMLDivElement | null>(null);
  const sentinelaRef = useRef<HTMLDivElement | null>(null);

  const chaveFiltros = `${buscaAplicada}|${setor}|${statusFiltro}`;

  useEffect(() => {
    const timer = setTimeout(() => setBuscaAplicada(busca.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [busca]);

  useEffect(() => {
    const controller = new AbortController();
    listarUsuarios(
      { busca: buscaAplicada, setor, status: statusFiltro, page: 1, pageSize: PAGE_SIZE },
      controller.signal,
    )
      .then((pagina) => {
        setResultado({
          chave: chaveFiltros,
          itens: pagina.items,
          total: pagina.total,
          pagina: 1,
        });
        setFalha(null);
        setFalhaPaginacaoEm(null);
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

  const carregarMais = useCallback(
    async (manual = false) => {
      if (carregandoMais || pronto === null || pronto.itens.length >= pronto.total) return;
      if (!manual && falhaPaginacaoEm === chaveFiltros) return; // sem auto-retry em loop
      setCarregandoMais(true);
      try {
        const proxima = pronto.pagina + 1;
        const pagina = await listarUsuarios({
          busca: buscaAplicada,
          setor,
          status: statusFiltro,
          page: proxima,
          pageSize: PAGE_SIZE,
        });
        setResultado((atual) =>
          atual && atual.chave === chaveFiltros
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
        setFalhaPaginacaoEm(chaveFiltros);
      } finally {
        setCarregandoMais(false);
      }
    },
    [buscaAplicada, carregandoMais, chaveFiltros, falhaPaginacaoEm, pronto, setor, statusFiltro],
  );

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

  function aindaCasaComFiltros(usuario: Usuario): boolean {
    if (statusFiltro && (statusFiltro === "ativo") !== usuario.ativo) return false;
    if (setor && usuario.setor !== setor) return false;
    if (buscaAplicada) {
      const termo = buscaAplicada.toLowerCase();
      if (
        !usuario.nome.toLowerCase().includes(termo) &&
        !usuario.email.toLowerCase().includes(termo)
      ) {
        return false;
      }
    }
    return true;
  }

  function substituirItem(usuario: Usuario) {
    const mantem = aindaCasaComFiltros(usuario);
    setResultado((atual) =>
      atual
        ? {
            ...atual,
            itens: mantem
              ? atual.itens.map((u) => (u.id === usuario.id ? usuario : u))
              : atual.itens.filter((u) => u.id !== usuario.id),
            total: mantem ? atual.total : Math.max(0, atual.total - 1),
          }
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
      setTentativa((t) => t + 1);
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
      variants={indice < STAGGER.maxItens ? itemVar : undefined}
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
      <motion.header
        className={styles.cabecalhoPagina}
        variants={itemVar}
        initial="hidden"
        animate="show"
      >
        <h1 className={styles.titulo}>Gerenciador de usuários</h1>
        <button
          type="button"
          className={styles.botaoNovo}
          onClick={() => setModalForm({ modo: "criar" })}
        >
          Novo usuário
        </button>
      </motion.header>

      <motion.div
        className={styles.filtros}
        variants={itemVar}
        initial="hidden"
        animate="show"
        transition={{ delay: reduced ? 0 : STAGGER.gap }}
      >
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
          <Dropdown
            ariaLabel="Filtrar por setor"
            value={setor}
            onChange={setSetor}
            opcoes={[
              { value: "", label: "Todos os setores" },
              { value: "studio", label: "3Studio" },
              { value: "vendedor", label: "Vendedor" },
              { value: "motorista", label: "Motorista" },
              { value: "clicheria", label: "Clicheria" },
            ]}
          />
        </div>
        <div className={styles.campoSelect}>
          <Dropdown
            ariaLabel="Filtrar por status"
            value={statusFiltro}
            onChange={setStatusFiltro}
            opcoes={[
              { value: "", label: "Todos" },
              { value: "ativo", label: "Ativos" },
              { value: "inativo", label: "Inativos" },
            ]}
          />
        </div>
      </motion.div>

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
            <motion.div
              role="rowgroup"
              className={styles.corpoTabela}
              ref={corpoRef}
              variants={containerVar}
              initial="hidden"
              animate="show"
            >
              {carregando ? (
                // aria-hidden: skeletons ficam fora da árvore de acessibilidade
                // (rowgroup só expõe filhos row — revisão W1-C04)
                <div className={styles.skeletons} aria-hidden>
                  {Array.from({ length: 6 }, (_, i) => (
                    <div key={i} className={`${styles.linha} ${styles.grade} ${styles.skeleton}`} />
                  ))}
                </div>
              ) : itens.length === 0 ? (
                <div role="row" className={styles.grade}>
                  <span role="cell" className={`${styles.celula} ${styles.celulaVazia}`}>
                    Nenhum usuário encontrado.
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
              {falhaPaginacaoEm === chaveFiltros && !carregandoMais && (
                <div role="row" className={styles.grade}>
                  <span role="cell" className={`${styles.celula} ${styles.celulaVazia}`}>
                    Falha ao carregar mais usuários.{" "}
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
            </motion.div>
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

      <UsuarioFormModal estado={modalForm} onFechar={() => setModalForm(null)} onSalvo={aoSalvar} />
      <ConfirmarStatusModal
        confirmacao={confirmacao}
        onFechar={() => setConfirmacao(null)}
        onConfirmado={aoConfirmarStatus}
      />
    </section>
  );
}
