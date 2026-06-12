import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import type { PaginaUsuarios, Usuario } from "@/lib/api/usuarios";

const mocks = vi.hoisted(() => ({
  listarUsuarios: vi.fn(),
  criarUsuario: vi.fn(),
  editarUsuario: vi.fn(),
  desativarUsuario: vi.fn(),
  reativarUsuario: vi.fn(),
}));

vi.mock("@/lib/api/usuarios", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/usuarios")>();
  return { ...original, ...mocks };
});

import { UsuariosView } from "./usuarios-view";

const ANA: Usuario = {
  id: "u-ana",
  nome: "Ana Lima",
  email: "ana@x.y",
  setor: "vendedor",
  localizacao: "matriz",
  administrador: false,
  ativo: true,
  created_at: null,
  updated_at: null,
};

const BRUNO: Usuario = {
  id: "u-bruno",
  nome: "Bruno Reis",
  email: "bruno@x.y",
  setor: "motorista",
  localizacao: null,
  administrador: true,
  ativo: false,
  created_at: null,
  updated_at: null,
};

function pagina(items: Usuario[], total = items.length): PaginaUsuarios {
  return { items, total, page: 1, page_size: 20 };
}

function renderView() {
  return render(
    <ToastProvider>
      <UsuariosView />
    </ToastProvider>,
  );
}

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
  mocks.listarUsuarios.mockResolvedValue(pagina([ANA, BRUNO]));
});

describe("UsuariosView (W1-C04)", () => {
  it("renderiza a tabela fiel ao design: colunas, rótulos e ações por linha", async () => {
    renderView();

    const tabela = screen.getByRole("table", { name: "Usuários" });
    for (const coluna of ["Nome", "E-mail", "Setor", "Localização", "Status", "Perfil", "Ações"]) {
      expect(within(tabela).getByRole("columnheader", { name: coluna })).toBeInTheDocument();
    }

    expect(await within(tabela).findByText("Ana Lima")).toBeInTheDocument();
    expect(within(tabela).getByText("Vendedor")).toBeInTheDocument();
    expect(within(tabela).getByText("Matriz")).toBeInTheDocument();
    expect(within(tabela).getByText("Inativo")).toBeInTheDocument();
    expect(within(tabela).getByText("Admin")).toBeInTheDocument();

    // Ativo → Desativar; inativo → Reativar (toggle por status)
    const linhaAna = within(tabela).getByText("Ana Lima").closest('[role="row"]') as HTMLElement;
    expect(within(linhaAna).getByRole("button", { name: "Desativar" })).toBeInTheDocument();
    const linhaBruno = within(tabela)
      .getByText("Bruno Reis")
      .closest('[role="row"]') as HTMLElement;
    expect(within(linhaBruno).getByRole("button", { name: "Reativar" })).toBeInTheDocument();
  });

  it("busca aplica debounce ≥300ms e só então consulta o backend (RNF-023)", async () => {
    vi.useFakeTimers();
    try {
      renderView();
      await act(async () => {
        await vi.runOnlyPendingTimersAsync();
      });
      mocks.listarUsuarios.mockClear();

      const campo = screen.getByLabelText("Buscar por nome ou email");
      fireEvent.change(campo, { target: { value: "an" } });
      fireEvent.change(campo, { target: { value: "ana" } });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(250);
      });
      expect(mocks.listarUsuarios).not.toHaveBeenCalled(); // ainda dentro do debounce

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
      expect(mocks.listarUsuarios).toHaveBeenCalledTimes(1); // UMA chamada para "ana"
      expect(mocks.listarUsuarios.mock.calls[0][0]).toMatchObject({ busca: "ana", page: 1 });
    } finally {
      vi.useRealTimers();
    }
  });

  it("filtros de setor e status disparam consulta server-side", async () => {
    renderView();
    await screen.findAllByText("Ana Lima");
    mocks.listarUsuarios.mockClear();

    fireEvent.change(screen.getByLabelText("Filtrar por setor"), {
      target: { value: "vendedor" },
    });
    await waitFor(() =>
      expect(mocks.listarUsuarios.mock.calls.at(-1)?.[0]).toMatchObject({ setor: "vendedor" }),
    );

    fireEvent.change(screen.getByLabelText("Filtrar por status"), {
      target: { value: "inativo" },
    });
    await waitFor(() =>
      expect(mocks.listarUsuarios.mock.calls.at(-1)?.[0]).toMatchObject({ status: "inativo" }),
    );
  });

  it("Novo usuário: valida senha em tempo real e envia o payload correto", async () => {
    const user = userEvent.setup();
    mocks.criarUsuario.mockResolvedValue({ ...ANA, id: "novo", nome: "Mario Souza" });
    renderView();
    await screen.findAllByText("Ana Lima");

    await user.click(screen.getByRole("button", { name: "Novo usuário" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Novo usuário")).toBeInTheDocument();

    const cadastrar = within(dialog).getByRole("button", { name: "Cadastrar" });
    expect(cadastrar).toBeDisabled(); // inválido até preencher tudo

    await user.type(within(dialog).getByLabelText("Nome:"), "Mario Souza");
    await user.type(within(dialog).getByLabelText("E-mail:"), "mario@estudio.com.br");
    const senha = within(dialog).getByLabelText(/senha/i);
    await user.type(senha, "curta");
    await user.tab();
    expect(
      within(dialog).getByText(/mínimo de 8 caracteres, com letra e número/i),
    ).toBeInTheDocument();

    await user.clear(senha);
    await user.type(senha, "senha-forte-1");
    await user.selectOptions(within(dialog).getByLabelText("Setor"), "vendedor");
    // RN-009: Vendedor exige localização — o campo condicional aparece
    await user.selectOptions(within(dialog).getByLabelText(/localização/i), "matriz");
    expect(cadastrar).toBeEnabled();

    await user.click(cadastrar);
    await waitFor(() =>
      expect(mocks.criarUsuario).toHaveBeenCalledWith({
        nome: "Mario Souza",
        email: "mario@estudio.com.br",
        senha: "senha-forte-1",
        setor: "vendedor",
        localizacao: "matriz",
        administrador: false,
      }),
    );
    expect(await screen.findByText("Usuário cadastrado.")).toBeInTheDocument(); // toast
  });

  it("e-mail duplicado (409) vira erro inline no formulário", async () => {
    const user = userEvent.setup();
    mocks.criarUsuario.mockRejectedValue(new ApiError(409, "email_ja_cadastrado", "dup"));
    renderView();
    await screen.findAllByText("Ana Lima");

    await user.click(screen.getByRole("button", { name: "Novo usuário" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Nome:"), "X");
    await user.type(within(dialog).getByLabelText("E-mail:"), "dup@x.y");
    await user.type(within(dialog).getByLabelText(/senha/i), "senha-forte-1");
    await user.selectOptions(within(dialog).getByLabelText("Setor"), "clicheria");
    await user.click(within(dialog).getByRole("button", { name: "Cadastrar" }));

    expect(
      await within(dialog).findByText(/já existe um usuário cadastrado com este e-mail/i),
    ).toBeInTheDocument();
  });

  it("desativar pede confirmação e reflete o novo status na tabela", async () => {
    const user = userEvent.setup();
    mocks.desativarUsuario.mockResolvedValue({ ...ANA, ativo: false });
    renderView();
    const tabela = screen.getByRole("table", { name: "Usuários" });
    await within(tabela).findByText("Ana Lima");

    const linhaAna = within(tabela).getByText("Ana Lima").closest('[role="row"]') as HTMLElement;
    await user.click(within(linhaAna).getByRole("button", { name: "Desativar" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/o histórico é preservado/i)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Desativar" }));

    await waitFor(() => expect(mocks.desativarUsuario).toHaveBeenCalledWith("u-ana"));
    await waitFor(() => {
      const linha = within(tabela).getByText("Ana Lima").closest('[role="row"]') as HTMLElement;
      expect(within(linha).getByText("Inativo")).toBeInTheDocument();
      expect(within(linha).getByRole("button", { name: "Reativar" })).toBeInTheDocument();
    });
  });

  it("regra de negócio negada (RN-010) vira toast de erro", async () => {
    const user = userEvent.setup();
    mocks.desativarUsuario.mockRejectedValue(
      new ApiError(422, "auto_desativacao", "Um administrador não pode desativar a própria conta."),
    );
    renderView();
    const tabela = screen.getByRole("table", { name: "Usuários" });
    await within(tabela).findByText("Ana Lima");

    const linhaAna = within(tabela).getByText("Ana Lima").closest('[role="row"]') as HTMLElement;
    await user.click(within(linhaAna).getByRole("button", { name: "Desativar" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Desativar" }),
    );

    expect(await screen.findByText(/não pode desativar a própria conta/i)).toBeInTheDocument();
  });

  it("403 do backend mostra acesso restrito (guard DP-5)", async () => {
    mocks.listarUsuarios.mockRejectedValue(new ApiError(403, "http_error", "Acesso restrito."));
    renderView();
    expect(await screen.findByText(/acesso restrito a administradores/i)).toBeInTheDocument();
  });

  it("falha de rede mostra estado de erro com retry", async () => {
    mocks.listarUsuarios.mockRejectedValueOnce(new ApiError(0, "api_inacessivel", "API fora."));
    renderView();
    expect(await screen.findByText(/não foi possível carregar/i)).toBeInTheDocument();

    mocks.listarUsuarios.mockResolvedValue(pagina([ANA]));
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findAllByText("Ana Lima")).not.toHaveLength(0);
  });
});
