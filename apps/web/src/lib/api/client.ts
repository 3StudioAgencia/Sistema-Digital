/**
 * Cliente HTTP do backend FastAPI (W1-C04) — browser.
 *
 * Anexa o Bearer da sessão Supabase corrente e converte o envelope de erro
 * canônico da API ({ error: { code, message, request_id } }) em `ApiError`.
 * Mantém o princípio do mínimo de requisições: nenhuma chamada automática,
 * sem retry agressivo — quem chama decide quando ir à rede (RNF-020/023).
 */
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;
const DEFAULT_TIMEOUT_MS = 10_000;

type ErrorEnvelope = { error?: { code?: string; message?: string; request_id?: string | null } };

async function accessToken(): Promise<string | null> {
  const supabase = getSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

export async function apiFetch<T>(
  path: string,
  init: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  if (!API_BASE_URL) {
    throw new ApiError(0, "api_nao_configurada", "API não configurada (NEXT_PUBLIC_API_BASE_URL).");
  }
  const token = await accessToken();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.body !== undefined) headers["Content-Type"] = "application/json";

  // O timeout vale SEMPRE — um signal externo (abort de filtro trocado) é
  // COMBINADO com ele, não o substitui (revisão W1-C04: API pendurada não pode
  // deixar skeleton infinito).
  const timeout = AbortSignal.timeout(DEFAULT_TIMEOUT_MS);
  const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: init.method ?? "GET",
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
      signal,
    });
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

  return (await response.json()) as T;
}
