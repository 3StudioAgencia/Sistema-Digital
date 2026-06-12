"use client";

/**
 * Criação de Prova Digital (W2-C06) — tela fiel ao design + reconciliação DP-1.
 *
 * - Campos obrigatórios do RF-001 com validação em tempo real (erro limpa ao
 *   corrigir); rota SEM pré-seleção: a escolha é manual e consciente (RN-007) e
 *   "criar sem rota" produz erro claro (critério §6.1).
 * - Vendedores carregados em UMA consulta (setor=vendedor & ativos — sem N+1).
 * - Dropzone valida tipo (JPG/PNG) e tamanho (≤ 10 MB) no client; o server
 *   revalida por magic bytes (defesa em profundidade).
 * - Pós-criação (DP-7): toast de sucesso + download automático da etiqueta +
 *   navegação para /provas; se o download falhar, painel com retry (degradação
 *   graciosa — nada se perde, a etiqueta é gerada sob demanda).
 * - Animações por tokens, transform/opacity apenas, zeradas sob reduced-motion.
 */
import { motion } from "framer-motion";
import { ArrowUp, Check } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  ARTE_TAMANHO_MAXIMO,
  ARTE_TIPOS,
  ROTA_LABELS,
  ROTAS_ORDEM_UI,
  baixarEtiqueta,
  criarProva,
  salvarArquivo,
  type Prova,
  type Rota,
} from "@/lib/api/provas";
import { listarUsuarios } from "@/lib/api/usuarios";
import { DURATION, EASING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";
import { Dropdown, type OpcaoDropdown } from "@/components/ui/select/Dropdown";
import { useToast } from "@/components/ui/toast/ToastProvider";

import styles from "../nova-prova.module.css";

type Erros = Partial<
  Record<"nome" | "requerimento" | "cliente" | "vendedor" | "rota" | "arte", string>
>;

type Vendedores =
  | { estado: "carregando" }
  | { estado: "erro" }
  | { estado: "ok"; opcoes: OpcaoDropdown<string>[] };

function formatarTamanho(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function validarArte(file: File): string | null {
  const tipoOk =
    (ARTE_TIPOS as readonly string[]).includes(file.type) || /\.(jpe?g|png)$/i.test(file.name);
  if (!tipoOk) return "Apenas arquivos JPG ou PNG.";
  if (file.size > ARTE_TAMANHO_MAXIMO) return "O arquivo excede o tamanho máximo de 10 MB.";
  return null;
}

export function NovaProvaView() {
  const router = useRouter();
  const toast = useToast();
  const reduced = useReducedMotion();
  const idBase = useId();

  const [nome, setNome] = useState("");
  const [requerimento, setRequerimento] = useState("");
  const [cliente, setCliente] = useState("");
  const [vendedorId, setVendedorId] = useState("");
  // Rota SEM default: escolha manual obrigatória (RN-007 / critério §6.1).
  const [rota, setRota] = useState<Rota | null>(null);
  const [arte, setArte] = useState<File | null>(null);

  const [erros, setErros] = useState<Erros>({});
  const [enviando, setEnviando] = useState(false);
  const [dragAtivo, setDragAtivo] = useState(false);
  const [vendedores, setVendedores] = useState<Vendedores>({ estado: "carregando" });
  const [recarregarVendedores, setRecarregarVendedores] = useState(0);
  // Criada mas com download da etiqueta pendente (falha de rede no download).
  const [pendenteEtiqueta, setPendenteEtiqueta] = useState<Prova | null>(null);
  const [baixandoEtiqueta, setBaixandoEtiqueta] = useState(false);

  const inputArquivoRef = useRef<HTMLInputElement | null>(null);

  // Vendedores ativos em UMA consulta (RNF-020/022) — o select é pequeno por
  // natureza (equipe de vendas), 100 cobre com folga.
  useEffect(() => {
    const controller = new AbortController();
    listarUsuarios(
      { setor: "vendedor", status: "ativo", page: 1, pageSize: 100 },
      controller.signal,
    )
      .then((pagina) =>
        setVendedores({
          estado: "ok",
          opcoes: pagina.items.map((u) => ({ value: u.id, label: u.nome })),
        }),
      )
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setVendedores({ estado: "erro" });
      });
    return () => controller.abort();
  }, [recarregarVendedores]);

  function limparErro(campo: keyof Erros) {
    setErros((atual) => {
      if (!(campo in atual)) return atual;
      const resto = { ...atual };
      delete resto[campo];
      return resto;
    });
  }

  function selecionarArte(file: File | null) {
    if (!file) return;
    const problema = validarArte(file);
    if (problema) {
      setArte(null);
      setErros((atual) => ({ ...atual, arte: problema }));
      return;
    }
    setArte(file);
    limparErro("arte");
  }

  function validarTudo(): Erros {
    const problemas: Erros = {};
    if (!nome.trim()) problemas.nome = "Informe o nome da prova.";
    if (!requerimento.trim()) problemas.requerimento = "Informe o número do requerimento.";
    else if (!/^\d+$/.test(requerimento.trim()))
      problemas.requerimento = "O requerimento aceita apenas números.";
    if (!cliente.trim()) problemas.cliente = "Informe o cliente.";
    if (!vendedorId) problemas.vendedor = "Selecione o vendedor responsável.";
    if (!rota) problemas.rota = "Selecione a rota de encaminhamento.";
    if (!arte) problemas.arte = "Anexe a arte da prova (JPG ou PNG, até 10 MB).";
    return problemas;
  }

  async function baixarEtiquetaDe(prova: Prova): Promise<boolean> {
    setBaixandoEtiqueta(true);
    try {
      const pdf = await baixarEtiqueta(prova.id);
      salvarArquivo(pdf, `etiqueta-${prova.codigo}.pdf`);
      return true;
    } catch {
      return false;
    } finally {
      setBaixandoEtiqueta(false);
    }
  }

  async function aoEnviar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (enviando || pendenteEtiqueta) return; // duplo submit nunca duplica prova
    const problemas = validarTudo();
    setErros(problemas);
    if (Object.keys(problemas).length > 0 || !rota || !arte) return;

    setEnviando(true);
    try {
      const prova = await criarProva({
        nome: nome.trim(),
        requerimento: requerimento.trim(),
        cliente: cliente.trim(),
        vendedorId,
        rota,
        arte,
      });
      toast.success(`Prova ${prova.codigo} criada.`);
      const baixou = await baixarEtiquetaDe(prova);
      if (baixou) {
        router.push("/provas"); // placeholder do C07 (DP-7)
      } else {
        setPendenteEtiqueta(prova); // degradação graciosa: retry sem perder nada
      }
    } catch (error) {
      const mensagem =
        error instanceof ApiError
          ? error.message
          : "Não foi possível criar a prova. Tente novamente.";
      toast.error(mensagem);
    } finally {
      setEnviando(false);
    }
  }

  const entrada = reduced
    ? { duration: DURATION.instant }
    : { duration: DURATION.medium, ease: EASING.emphasized };

  // ------------------------------------------------------------ pós-criação
  if (pendenteEtiqueta) {
    return (
      <section className={styles.pagina}>
        <header className={styles.cabecalho}>
          <h1 className={styles.titulo}>Nova prova Digital</h1>
        </header>
        <motion.div
          className={styles.cartaoSucesso}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={entrada}
        >
          <span className={styles.sucessoIcone} aria-hidden>
            <Check size={28} strokeWidth={3} />
          </span>
          <h2 className={styles.sucessoTitulo}>Prova {pendenteEtiqueta.codigo} criada</h2>
          <p className={styles.sucessoTexto}>
            O download automático da etiqueta falhou. A etiqueta é gerada sob demanda — nada foi
            perdido: baixe novamente abaixo.
          </p>
          <div className={styles.sucessoAcoes}>
            <button
              type="button"
              className={styles.botaoCriar}
              disabled={baixandoEtiqueta}
              onClick={() => {
                void baixarEtiquetaDe(pendenteEtiqueta).then((baixou) => {
                  if (baixou) router.push("/provas");
                  else toast.error("Download da etiqueta indisponível. Tente novamente.");
                });
              }}
            >
              {baixandoEtiqueta ? "Baixando…" : "Baixar etiqueta"}
            </button>
            <button
              type="button"
              className={styles.botaoSecundario}
              onClick={() => router.push("/provas")}
            >
              Continuar sem baixar
            </button>
          </div>
        </motion.div>
      </section>
    );
  }

  // ------------------------------------------------------------- formulário
  return (
    <section className={styles.pagina}>
      <form onSubmit={aoEnviar} noValidate>
        <header className={styles.cabecalho}>
          <h1 className={styles.titulo}>Nova prova Digital</h1>
          <button type="submit" className={styles.botaoCriar} disabled={enviando}>
            {enviando ? "Criando…" : "Criar Prova"}
          </button>
        </header>

        <motion.div
          className={styles.cartao}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={entrada}
        >
          <div className={styles.grade}>
            <div className={styles.campo}>
              <label className={styles.rotulo} htmlFor={`${idBase}-nome`}>
                Nome
              </label>
              <input
                id={`${idBase}-nome`}
                className={styles.entrada}
                value={nome}
                maxLength={200}
                onChange={(e) => {
                  setNome(e.target.value);
                  limparErro("nome");
                }}
                aria-invalid={!!erros.nome}
                aria-describedby={erros.nome ? `${idBase}-nome-erro` : undefined}
              />
              {erros.nome && (
                <p id={`${idBase}-nome-erro`} className={styles.erro} role="alert">
                  {erros.nome}
                </p>
              )}
            </div>

            <div className={styles.campo}>
              <label className={styles.rotulo} htmlFor={`${idBase}-requerimento`}>
                Requerimento
              </label>
              <input
                id={`${idBase}-requerimento`}
                className={styles.entrada}
                value={requerimento}
                inputMode="numeric"
                maxLength={50}
                onChange={(e) => {
                  setRequerimento(e.target.value);
                  limparErro("requerimento");
                }}
                aria-invalid={!!erros.requerimento}
                aria-describedby={erros.requerimento ? `${idBase}-req-erro` : undefined}
              />
              {erros.requerimento && (
                <p id={`${idBase}-req-erro`} className={styles.erro} role="alert">
                  {erros.requerimento}
                </p>
              )}
            </div>

            <div className={styles.campo}>
              <label className={styles.rotulo} htmlFor={`${idBase}-cliente`}>
                Cliente
              </label>
              <input
                id={`${idBase}-cliente`}
                className={styles.entrada}
                value={cliente}
                maxLength={200}
                onChange={(e) => {
                  setCliente(e.target.value);
                  limparErro("cliente");
                }}
                aria-invalid={!!erros.cliente}
                aria-describedby={erros.cliente ? `${idBase}-cliente-erro` : undefined}
              />
              {erros.cliente && (
                <p id={`${idBase}-cliente-erro`} className={styles.erro} role="alert">
                  {erros.cliente}
                </p>
              )}
            </div>

            <div className={styles.campo}>
              <span className={styles.rotulo} id={`${idBase}-vendedor-rotulo`}>
                Vendedor
              </span>
              {vendedores.estado === "erro" ? (
                <button
                  type="button"
                  className={styles.recarregar}
                  onClick={() => setRecarregarVendedores((n) => n + 1)}
                >
                  Falha ao carregar vendedores — tentar novamente
                </button>
              ) : (
                <div className={styles.slotSelect}>
                  <Dropdown
                    value={vendedorId}
                    opcoes={vendedores.estado === "ok" ? vendedores.opcoes : []}
                    onChange={(valor) => {
                      setVendedorId(valor);
                      limparErro("vendedor");
                    }}
                    labelledBy={`${idBase}-vendedor-rotulo`}
                    placeholder={
                      vendedores.estado === "carregando" ? "Carregando…" : "Selecione o vendedor"
                    }
                    variante="claro"
                  />
                </div>
              )}
              {erros.vendedor && (
                <p className={styles.erro} role="alert">
                  {erros.vendedor}
                </p>
              )}
            </div>
          </div>

          <div className={styles.campo}>
            <span className={styles.rotulo} id={`${idBase}-rota-rotulo`}>
              Rota
            </span>
            <div
              role="radiogroup"
              aria-labelledby={`${idBase}-rota-rotulo`}
              className={styles.segmento}
            >
              {ROTAS_ORDEM_UI.map((opcao) => {
                const ativa = rota === opcao;
                return (
                  <button
                    key={opcao}
                    type="button"
                    role="radio"
                    aria-checked={ativa}
                    className={styles.segmentoItem}
                    data-ativa={ativa || undefined}
                    onClick={() => {
                      setRota(opcao);
                      limparErro("rota");
                    }}
                  >
                    {ativa && (
                      <motion.span
                        layoutId={`${idBase}-rota-pill`}
                        className={styles.segmentoPill}
                        transition={
                          reduced
                            ? { duration: DURATION.instant }
                            : { duration: DURATION.short, ease: EASING.emphasized }
                        }
                        aria-hidden
                      />
                    )}
                    <span className={styles.segmentoRotulo}>{ROTA_LABELS[opcao]}</span>
                  </button>
                );
              })}
            </div>
            {erros.rota && (
              <p className={styles.erro} role="alert">
                {erros.rota}
              </p>
            )}
          </div>

          <div className={styles.campo}>
            <motion.div
              className={styles.dropzone}
              data-arrastando={dragAtivo || undefined}
              data-erro={erros.arte ? true : undefined}
              animate={reduced ? undefined : { scale: dragAtivo ? 1.01 : 1 }}
              transition={{ duration: DURATION.micro, ease: EASING.standard }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragAtivo(true);
              }}
              onDragLeave={() => setDragAtivo(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragAtivo(false);
                selecionarArte(e.dataTransfer.files?.[0] ?? null);
              }}
            >
              <input
                ref={inputArquivoRef}
                id={`${idBase}-arte`}
                type="file"
                accept="image/jpeg,image/png,.jpg,.jpeg,.png"
                className={styles.inputArquivo}
                onChange={(e) => {
                  selecionarArte(e.target.files?.[0] ?? null);
                  e.target.value = ""; // re-selecionar o mesmo arquivo dispara de novo
                }}
              />
              <button
                type="button"
                className={styles.dropzoneAlvo}
                onClick={() => inputArquivoRef.current?.click()}
                aria-describedby={erros.arte ? `${idBase}-arte-erro` : undefined}
              >
                {arte ? (
                  <>
                    <span className={styles.dropzoneTitulo}>{arte.name}</span>
                    <span className={styles.dropzoneDica}>
                      {formatarTamanho(arte.size)} — clique para trocar
                    </span>
                  </>
                ) : (
                  <>
                    <ArrowUp className={styles.dropzoneIcone} aria-hidden />
                    <span className={styles.dropzoneTitulo}>Solte ou clique</span>
                    <span className={styles.dropzoneDica}>JPG • PNG</span>
                  </>
                )}
              </button>
            </motion.div>
            {erros.arte && (
              <p id={`${idBase}-arte-erro`} className={styles.erro} role="alert">
                {erros.arte}
              </p>
            )}
          </div>
        </motion.div>
      </form>
    </section>
  );
}
