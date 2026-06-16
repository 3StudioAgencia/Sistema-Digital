import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import type { ProvaDetalhe } from "@/lib/api/provas";

const mocks = vi.hoisted(() => ({
  identificarProva: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  back: vi.fn(),
  // câmera (html5-qrcode)
  start: vi.fn(() => Promise.resolve()),
  stop: vi.fn(() => Promise.resolve()),
  clear: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace, back: mocks.back }),
}));

vi.mock("@/lib/api/escaneamento", () => ({
  identificarProva: mocks.identificarProva,
}));

// Mock do leitor de QR: o import DINÂMICO de "html5-qrcode" é interceptado aqui.
vi.mock("html5-qrcode", () => ({
  Html5QrcodeSupportedFormats: { QR_CODE: 0 },
  Html5Qrcode: class {
    start = mocks.start;
    stop = mocks.stop;
    clear = mocks.clear;
  },
}));

import { EscanearView } from "./escanear-view";

const CODIGO = "PRV-2026-06-A2KMQ9";
const PROVA: ProvaDetalhe = {
  id: "p-1",
  codigo: CODIGO,
  nome: "Mussarela fatiada",
  requerimento: "155295",
  cliente: "Edulat",
  vendedor_id: "v-1",
  vendedor_nome: "Regiane",
  rota: "matriz",
  status: "criada",
  ciclo_atual: 1,
  created_at: "2026-06-16T00:00:00Z",
  finalizada_em: null,
};

function renderView() {
  return render(
    <ToastProvider>
      <EscanearView />
    </ToastProvider>,
  );
}

beforeEach(() => {
  for (const m of Object.values(mocks)) m.mockReset();
  mocks.identificarProva.mockResolvedValue(PROVA);
  mocks.start.mockResolvedValue(undefined);
  mocks.stop.mockResolvedValue(undefined);
  // reduced-motion = true → navegação imediata (sem setTimeout do flash de sucesso).
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
});

describe("EscanearView (W3-C10) — câmera + manual, mobile-first", () => {
  it("renderiza o cabeçalho e os DOIS modos sempre acessíveis (toggle)", () => {
    renderView();
    expect(screen.getByRole("heading", { name: "Escanear prova", level: 1 })).toBeInTheDocument();
    expect(screen.getByText(/Leia o QR Code da etiqueta/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Câmera/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Manual/ })).toBeInTheDocument();
    // Câmera é o modo inicial (fiel ao design "Pronto para escanear").
    expect(screen.getByRole("button", { name: "Abrir câmera" })).toBeInTheDocument();
  });

  it("manual: 'Buscar prova' só habilita com o código no formato do C06 (DP-1)", async () => {
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("radio", { name: /Manual/ }));

    const input = screen.getByLabelText(/Código da prova/);
    const botao = screen.getByRole("button", { name: /Buscar prova/ });
    expect(botao).toBeDisabled();

    fireEvent.change(input, { target: { value: "2026-06" } }); // incompleto
    expect(botao).toBeDisabled();

    fireEvent.change(input, { target: { value: "prv-2026-06-a2kmq9" } }); // colou tudo, minúsculas
    expect((input as HTMLInputElement).value).toBe("2026-06-A2KMQ9"); // mascarado
    expect(botao).toBeEnabled();
  });

  it("manual: identifica e navega à tela de confirmação (DP-2)", async () => {
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("radio", { name: /Manual/ }));
    fireEvent.change(screen.getByLabelText(/Código da prova/), {
      target: { value: "2026-06-A2KMQ9" },
    });
    await user.click(screen.getByRole("button", { name: /Buscar prova/ }));

    await waitFor(() => expect(mocks.identificarProva).toHaveBeenCalledWith(CODIGO));
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/provas/p-1/confirmar"));
  });

  it("manual: 404 (inválido/inexistente/fora-de-escopo) → MESMA mensagem genérica, sem navegar", async () => {
    mocks.identificarProva.mockRejectedValue(
      new ApiError(404, "prova_nao_encontrada", "Prova não encontrada."),
    );
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("radio", { name: /Manual/ }));
    fireEvent.change(screen.getByLabelText(/Código da prova/), {
      target: { value: "2026-06-A2KMQ9" },
    });
    await user.click(screen.getByRole("button", { name: /Buscar prova/ }));

    expect(await screen.findByText("Prova não encontrada.")).toBeInTheDocument(); // toast
    expect(mocks.push).not.toHaveBeenCalled();
  });

  it("manual: 429 → mostra a mensagem de limite de tentativas (RN-014)", async () => {
    mocks.identificarProva.mockRejectedValue(
      new ApiError(429, "limite_de_tentativas", "Muitas tentativas em pouco tempo. Aguarde."),
    );
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("radio", { name: /Manual/ }));
    fireEvent.change(screen.getByLabelText(/Código da prova/), {
      target: { value: "2026-06-A2KMQ9" },
    });
    await user.click(screen.getByRole("button", { name: /Buscar prova/ }));

    expect(await screen.findByText(/Muitas tentativas/)).toBeInTheDocument();
  });

  it("câmera negada NÃO bloqueia a tela — o manual segue acessível (RNF-014)", async () => {
    mocks.start.mockRejectedValue(new Error("NotAllowedError")); // permissão negada
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Abrir câmera" }));

    expect(await screen.findByText(/Câmera indisponível/)).toBeInTheDocument();
    // O toggle continua lá e leva ao campo manual.
    await user.click(screen.getByRole("radio", { name: /Manual/ }));
    expect(screen.getByLabelText(/Código da prova/)).toBeInTheDocument();
  });

  it("câmera: leitura do QR resolve o MESMO destino do manual (idempotência de mecanismo)", async () => {
    // o start chama o callback de sucesso com o texto do QR (= o próprio código)
    mocks.start.mockImplementation(
      (_cam: unknown, _cfg: unknown, onSuccess: (texto: string) => void) => {
        onSuccess(CODIGO);
        return Promise.resolve();
      },
    );
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Abrir câmera" }));

    await waitFor(() => expect(mocks.identificarProva).toHaveBeenCalledWith(CODIGO));
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/provas/p-1/confirmar"));
  });

  it("trocar p/ Manual durante o start() encerra o track quando o start resolve (sem vazar câmera)", async () => {
    let resolveStart: () => void = () => {};
    let stopCalls = 0;
    // 1ª chamada de stop() = cleanup com o scanner AINDA iniciando (o html5-qrcode
    // real lança "not running"); 2ª = após o start resolver → encerra o track.
    mocks.stop.mockImplementation(() => {
      stopCalls += 1;
      return stopCalls === 1
        ? Promise.reject(new Error("Cannot stop, scanner is not running or paused"))
        : Promise.resolve();
    });
    mocks.start.mockImplementation(() => new Promise<void>((res) => (resolveStart = res)));

    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Abrir câmera" }));
    // troca para Manual ENQUANTO o start está pendente → desmonta o CameraScanner
    await user.click(screen.getByRole("radio", { name: /Manual/ }));
    // o start só resolve agora (track recém-aberto após o unmount): tem de ser parado
    resolveStart();

    await waitFor(() => expect(mocks.stop.mock.calls.length).toBeGreaterThanOrEqual(2));
  });
});
