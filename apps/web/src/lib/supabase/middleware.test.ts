/**
 * Enforcement de RBAC da camada SUPERIOR (W1-A-002).
 *
 * As funções puras (`can`/`podeAcessarRota`/`perfilDeClaims`) já têm cobertura;
 * o que faltava era o caminho que de fato BLOQUEIA: `updateSession` →
 * getUser() → getClaims() → decisão → 302 + flash. Aqui mockamos o client do
 * `@supabase/ssr` e exercemos o `updateSession` real.
 */
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FLASH_ACESSO_NEGADO, HOME_PADRAO } from "@/lib/access-matrix";

const mocks = vi.hoisted(() => ({
  getUser: vi.fn(),
  getClaims: vi.fn(),
}));

vi.mock("@supabase/ssr", () => ({
  createServerClient: () => ({
    auth: { getUser: mocks.getUser, getClaims: mocks.getClaims },
  }),
}));

vi.mock("./env", () => ({
  getSupabaseEnv: () => ({ url: "https://proj.supabase.co", anonKey: "anon-pub" }),
}));

import { updateSession } from "./middleware";

function req(pathname: string): NextRequest {
  return new NextRequest(`http://localhost${pathname}`);
}

function comUsuario(): void {
  mocks.getUser.mockResolvedValue({ data: { user: { id: "u1" } } });
}

function comClaims(setor: string | null, administrador: boolean): void {
  mocks.getClaims.mockResolvedValue({ data: { claims: { setor, administrador } } });
}

beforeEach(() => {
  mocks.getUser.mockReset();
  mocks.getClaims.mockReset();
});

describe("updateSession — enforcement de RBAC (camada superior)", () => {
  it("não-admin em rota admin → redirect à home do perfil + flash + no-store", async () => {
    comUsuario();
    comClaims("vendedor", false);

    const res = await updateSession(req("/usuarios"));

    expect(res.status).toBeGreaterThanOrEqual(300);
    expect(res.status).toBeLessThan(400);
    expect(res.headers.get("location")).toContain(HOME_PADRAO);
    expect(res.cookies.get(FLASH_ACESSO_NEGADO)?.value).toBe("1");
    expect(res.headers.get("Cache-Control")).toBe("no-store");
  });

  it("admin em rota admin → segue (next, sem redirect)", async () => {
    comUsuario();
    comClaims("studio", true);

    const res = await updateSession(req("/usuarios"));

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });

  it("qualquer autenticado em rota universal → segue", async () => {
    comUsuario();
    comClaims("vendedor", false);

    const res = await updateSession(req("/dashboard"));

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });

  it("não autenticado → segue sem consultar perfil (getClaims não é chamado)", async () => {
    mocks.getUser.mockResolvedValue({ data: { user: null } });

    const res = await updateSession(req("/usuarios"));

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
    expect(mocks.getClaims).not.toHaveBeenCalled();
  });
});
