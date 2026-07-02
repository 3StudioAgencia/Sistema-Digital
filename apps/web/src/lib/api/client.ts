/**
 * Cliente HTTP do backend (browser) — migração Supabase->local.
 *
 * As chamadas vão pela MESMA ORIGEM (`/api/*`, rewrite do next.config): o cookie
 * httpOnly de sessão flui automaticamente — o browser não manuseia o token
 * (imune a XSS). Em 401 (access expirado), tenta renovar UMA vez (/api/auth/refresh)
 * e repete. Converte o envelope de erro canônico da API em `ApiError`.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

// Mesma origem: o rewrite /api/:path* → backend. Sem NEXT_PUBLIC_API_BASE_URL.
const API_BASE = "/api";
const DEFAULT_TIMEOUT_MS = 10_000;

type ErrorEnvelope = { error?: { code?: string; message?: string; request_id?: string | null } };

type RequestInitLeve = {
  method?: string;
  /** JSON por padrão; `FormData` envia multipart (o browser define o boundary). */
  body?: unknown;
  signal?: AbortSignal;
  /** Override do timeout — uploads/downloads (W2-C06) precisam de mais folga. */
  timeoutMs?: number;
};

async function enviar(path: string, init: RequestInitLeve): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const multipart = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body !== undefined && !multipart) headers["Content-Type"] = "application/json";

  const timeout = AbortSignal.timeout(init.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;

  return fetch(`${API_BASE}${path}`, {
    method: init.method ?? "GET",
    headers,
    body:
      init.body !== undefined
        ? multipart
          ? (init.body as FormData)
          : JSON.stringify(init.body)
        : undefined,
    cache: "no-store",
    signal,
  });
}

async function request(path: string, init: RequestInitLeve): Promise<Response> {
  let response: Response;
  try {
    response = await enviar(path, init);
    // Access expirado: renova UMA vez e repete (o refresh não passa por aqui).
    if (response.status === 401 && !path.startsWith("/auth/")) {
      const renovou = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", cache: "no-store" });
      if (renovou.ok) response = await enviar(path, init);
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "api_inacessivel", "Não foi possível falar com a API. Tente novamente.");
  }

  if (!response.ok) {
    let code = "http_error";
    let message = "Falha na comunicação com a API.";
    let requestId: string | null = null;
    try {
      const body = (await response.json()) as ErrorEnvelope;
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
      requestId = body.error?.request_id ?? null;
    } catch {
      // corpo fora do contrato (proxy/HTML) — mantém a mensagem genérica
    }
    throw new ApiError(response.status, code, message, requestId);
  }

  return response;
}

export async function apiFetch<T>(path: string, init: RequestInitLeve = {}): Promise<T> {
  const response = await request(path, init);
  return (await response.json()) as T;
}

/** Resposta binária (etiqueta PDF — W2-C06); mesmo contrato de erro do apiFetch. */
export async function apiFetchBlob(path: string, init: RequestInitLeve = {}): Promise<Blob> {
  const response = await request(path, init);
  return await response.blob();
}
