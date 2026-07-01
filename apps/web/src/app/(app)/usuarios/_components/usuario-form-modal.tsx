"use client";

import { useId, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  criarUsuario,
  editarUsuario,
  type Localizacao,
  type Setor,
  type Usuario,
} from "@/lib/api/usuarios";
import { emailValido, senhaValida } from "@/lib/validacao";
import { MotionModal } from "@/components/ui/modal/MotionModal";
import { Dropdown } from "@/components/ui/select/Dropdown";
import { useToast } from "@/components/ui/toast/ToastProvider";

import styles from "../usuarios.module.css";

export type EstadoForm = { modo: "criar" } | { modo: "editar"; usuario: Usuario };

type Props = {
  estado: EstadoForm | null;
  onFechar: () => void;
  onSalvo: (usuario: Usuario, modo: "criar" | "editar") => void;
};

export function UsuarioFormModal({ estado, onFechar, onSalvo }: Props) {
  const tituloId = useId();
  const [enviando, setEnviando] = useState(false);
  return (
    <MotionModal
      open={estado !== null}
      onClose={() => {
        if (!enviando) onFechar();
      }}
      labelledBy={tituloId}
      panelClassName={styles.modalPainel}
    >
      {estado !== null && (
        <FormInterno
          key={estado.modo === "editar" ? `editar-${estado.usuario.id}` : "criar"}
          estado={estado}
          tituloId={tituloId}
          onFechar={onFechar}
          onSalvo={onSalvo}
          enviando={enviando}
          setEnviando={setEnviando}
        />
      )}
    </MotionModal>
  );
}

type Campos = {
  nome: string;
  email: string;
  senha: string;
  setor: "" | Setor;
  localizacao: "" | Localizacao;
  administrador: boolean;
};

function camposIniciais(estado: EstadoForm): Campos {
  if (estado.modo === "editar") {
    const u = estado.usuario;
    return {
      nome: u.nome,
      email: u.email,
      senha: "",
      setor: u.setor,
      localizacao: u.localizacao ?? "",
      administrador: u.administrador,
    };
  }
  return { nome: "", email: "", senha: "", setor: "", localizacao: "", administrador: false };
}

function FormInterno({
  estado,
  tituloId,
  onFechar,
  onSalvo,
  enviando,
  setEnviando,
}: {
  estado: EstadoForm;
  tituloId: string;
  onFechar: () => void;
  onSalvo: (usuario: Usuario, modo: "criar" | "editar") => void;
  enviando: boolean;
  setEnviando: (valor: boolean) => void;
}) {
  const toast = useToast();
  const modo = estado.modo;
  const [campos, setCampos] = useState<Campos>(() => camposIniciais(estado));
  const [tocados, setTocados] = useState<Partial<Record<keyof Campos, boolean>>>({});
  const [erroServidor, setErroServidor] = useState<string | null>(null);

  function atualizar<K extends keyof Campos>(campo: K, valor: Campos[K]) {
    setCampos((atual) => ({ ...atual, [campo]: valor }));
    setErroServidor(null);
  }

  const erros = {
    nome: campos.nome.trim() ? null : "Informe o nome.",
    email: modo === "editar" || emailValido(campos.email) ? null : "Informe um e-mail válido.",
    senha:
      modo === "editar" || senhaValida(campos.senha)
        ? null
        : "Mínimo de 8 caracteres, com letra e número.",
    setor: campos.setor ? null : "Selecione o setor.",
    localizacao:
      campos.setor !== "vendedor" || campos.localizacao
        ? null
        : "Vendedor exige localização (RN-009).",
  };
  const valido = Object.values(erros).every((erro) => erro === null);

  async function enviar(event: React.FormEvent) {
    event.preventDefault();
    if (!valido || enviando) return;
    setEnviando(true);
    setErroServidor(null);
    try {
      const localizacao = campos.setor === "vendedor" ? (campos.localizacao as Localizacao) : null;
      const salvo =
        estado.modo === "criar"
          ? await criarUsuario({
              nome: campos.nome.trim(),
              email: campos.email.trim(),
              senha: campos.senha,
              setor: campos.setor as Setor,
              localizacao,
              administrador: campos.administrador,
            })
          : await editarUsuario(estado.usuario.id, {
              nome: campos.nome.trim(),
              setor: campos.setor as Setor,
              localizacao,
              administrador: campos.administrador,
            });
      onSalvo(salvo, estado.modo);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setErroServidor("Já existe um usuário cadastrado com este e-mail.");
      } else if (error instanceof ApiError && error.status === 422) {
        setErroServidor(error.message);
      } else {
        toast.error(error instanceof ApiError ? error.message : "Falha ao salvar o usuário.");
      }
    } finally {
      setEnviando(false);
    }
  }

  function marcarTocado(campo: keyof Campos) {
    setTocados((atual) => ({ ...atual, [campo]: true }));
  }

  function mostrarErro(campo: keyof typeof erros): string | null {
    return tocados[campo] ? erros[campo] : null;
  }

  return (
    <>
      <h2 id={tituloId} className={styles.modalTitulo}>
        {modo === "criar" ? "Novo usuário" : "Editar usuário"}
      </h2>
      <hr className={styles.modalSeparador} />

      <form onSubmit={(event) => void enviar(event)} noValidate>
        <div className={styles.modalCampo}>
          <label htmlFor={`${tituloId}-nome`} className={styles.modalLabel}>
            Nome:
          </label>
          <input
            id={`${tituloId}-nome`}
            type="text"
            value={campos.nome}
            onChange={(event) => atualizar("nome", event.target.value)}
            onBlur={() => marcarTocado("nome")}
            className={styles.modalInput}
            autoComplete="off"
            maxLength={200}
          />
          {mostrarErro("nome") && <p className={styles.modalErro}>{mostrarErro("nome")}</p>}
        </div>

        <div className={styles.modalCampo}>
          <label htmlFor={`${tituloId}-email`} className={styles.modalLabel}>
            E-mail:
          </label>
          <input
            id={`${tituloId}-email`}
            type="email"
            value={campos.email}
            onChange={(event) => atualizar("email", event.target.value)}
            onBlur={() => marcarTocado("email")}
            className={styles.modalInput}
            autoComplete="off"
            disabled={modo === "editar"}
            aria-describedby={modo === "editar" ? `${tituloId}-email-nota` : undefined}
          />
          {modo === "editar" && (
            <p id={`${tituloId}-email-nota`} className={styles.modalNota}>
              O e-mail é a identidade de acesso e não pode ser alterado.
            </p>
          )}
          {mostrarErro("email") && <p className={styles.modalErro}>{mostrarErro("email")}</p>}
        </div>

        {modo === "criar" && (
          <div className={styles.modalCampo}>
            <label htmlFor={`${tituloId}-senha`} className={styles.modalLabel}>
              Senha (min. 8, com letra e numero):
            </label>
            <input
              id={`${tituloId}-senha`}
              type="password"
              value={campos.senha}
              onChange={(event) => atualizar("senha", event.target.value)}
              onBlur={() => marcarTocado("senha")}
              className={styles.modalInput}
              autoComplete="new-password"
            />
            {mostrarErro("senha") && <p className={styles.modalErro}>{mostrarErro("senha")}</p>}
          </div>
        )}

        <div className={styles.modalCampo}>
          <span id={`${tituloId}-setor-label`} className={styles.modalLabel}>
            Setor
          </span>
          <div className={styles.modalDropdown}>
            <Dropdown<"" | Setor>
              variante="escuro"
              abrirPara="cima"
              labelledBy={`${tituloId}-setor-label`}
              value={campos.setor}
              onChange={(setor) => {
                setCampos((atual) => ({
                  ...atual,
                  setor,
                  localizacao: setor === "vendedor" ? atual.localizacao : "",
                }));
                setErroServidor(null);
                marcarTocado("setor");
              }}
              opcoes={[
                { value: "studio", label: "3Studio" },
                { value: "vendedor", label: "Vendedor" },
                { value: "motorista", label: "Motorista" },
                { value: "clicheria", label: "Clicheria" },
              ]}
            />
          </div>
          {mostrarErro("setor") && <p className={styles.modalErro}>{mostrarErro("setor")}</p>}
        </div>

        {campos.setor === "vendedor" && (
          <div className={styles.modalCampo}>
            <span id={`${tituloId}-localizacao-label`} className={styles.modalLabel}>
              Localização (Matriz ou Filial):
            </span>
            <div className={styles.modalDropdown}>
              <Dropdown<"" | Localizacao>
                variante="escuro"
                abrirPara="cima"
                labelledBy={`${tituloId}-localizacao-label`}
                value={campos.localizacao}
                onChange={(localizacao) => {
                  atualizar("localizacao", localizacao);
                  marcarTocado("localizacao");
                }}
                opcoes={[
                  { value: "matriz", label: "Matriz" },
                  { value: "filial", label: "Filial" },
                ]}
              />
            </div>
            {mostrarErro("localizacao") && (
              <p className={styles.modalErro}>{mostrarErro("localizacao")}</p>
            )}
          </div>
        )}

        <label className={styles.modalCheckboxLinha}>
          <input
            type="checkbox"
            checked={campos.administrador}
            onChange={(event) => atualizar("administrador", event.target.checked)}
            className={styles.modalCheckbox}
          />
          <span className={styles.modalCheckboxCaixa} aria-hidden />
          Administrador
        </label>

        {erroServidor && (
          <p className={styles.modalErro} role="alert">
            {erroServidor}
          </p>
        )}

        <div className={styles.modalAcoes}>
          <button
            type="button"
            className={styles.botaoCancelar}
            onClick={onFechar}
            disabled={enviando}
          >
            Cancelar
          </button>
          <button type="submit" className={styles.botaoConfirmar} disabled={!valido || enviando}>
            {enviando ? "Salvando…" : modo === "criar" ? "Cadastrar" : "Salvar"}
          </button>
        </div>
      </form>
    </>
  );
}
