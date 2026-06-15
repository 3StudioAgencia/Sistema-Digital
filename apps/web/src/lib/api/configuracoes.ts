/**
 * Tipos e operações do recurso /settings (W2-C09) — configurações do sistema.
 *
 * Espelho 1:1 dos schemas do backend (apps/api .../http/settings.py). Modelo
 * chave-valor (DP-1): `valor`/`default` são heterogêneos (inteiro do tempo de
 * atraso, objeto do template de etiqueta). Exclusivo do 3Studio (Matriz §7): o
 * GET/PUT respondem 403 a não-admin (defesa em profundidade — proxy + RLS).
 */
import { apiFetch } from "./client";

/** Chaves conhecidas (espelham src/domain/settings.py). */
export const CHAVE_DELAY = "delay_horas_uteis";
export const CHAVE_ETIQUETA = "etiqueta_template";

/** Fontes core do fpdf2 que o template aceita (espelha FONTES_ETIQUETA). */
export const FONTES_ETIQUETA = ["helvetica", "times", "courier"] as const;
export type FonteEtiqueta = (typeof FONTES_ETIQUETA)[number];

export const FONTE_LABELS: Record<FonteEtiqueta, string> = {
  helvetica: "Helvetica",
  times: "Times",
  courier: "Courier",
};

export type ModoEtiqueta = "padrao" | "personalizado";

/** Valor da chave `etiqueta_template` (os 5 parâmetros do template do C06 + modo). */
export type EtiquetaTemplateValor = {
  modo: ModoEtiqueta;
  largura: number;
  altura: number;
  margem: number;
  fonte: FonteEtiqueta;
  qr_zona_quieta_modulos: number;
};

/** Configuração para apresentação: valor EFETIVO + default + metadados. */
export type Configuracao<V = unknown> = {
  chave: string;
  valor: V;
  default: V;
  descricao: string;
  atualizado_em: string | null;
  atualizado_por: string | null;
};

/** Lista as configurações conhecidas (3Studio-only; 403 a não-admin). */
export function listarConfiguracoes(signal?: AbortSignal): Promise<Configuracao[]> {
  return apiFetch<Configuracao[]>("/settings", { signal });
}

/**
 * Salva uma configuração (PUT idempotente — RNF-015). Imediato (US-016): a
 * próxima leitura — incluindo o consumo server-side da etiqueta (C06) — já
 * reflete o novo valor (sem cache — DP-4). A validação por chave é do backend
 * (422 em valor inválido); o front valida em tempo real para feedback imediato.
 */
export function salvarConfiguracao<V = unknown>(
  chave: string,
  valor: V,
  signal?: AbortSignal,
): Promise<Configuracao<V>> {
  return apiFetch<Configuracao<V>>(`/settings/${chave}`, {
    method: "PUT",
    body: { valor },
    signal,
  });
}

/** Localiza a configuração por chave numa lista (helper de leitura da tela). */
export function acharConfig(configs: Configuracao[], chave: string): Configuracao | undefined {
  return configs.find((c) => c.chave === chave);
}
