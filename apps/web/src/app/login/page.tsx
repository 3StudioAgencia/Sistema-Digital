import { redirect } from "next/navigation";

import { HOME_PADRAO } from "@/lib/access-matrix";
import { lerSessao } from "@/lib/auth/session";

import { AuthFlow } from "../_components/auth-flow";

export const dynamic = "force-dynamic";
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const sessao = await lerSessao();
  if (sessao) redirect(HOME_PADRAO);

  const sp = await searchParams;
  return <AuthFlow expired={sp.expirado === "1"} />;
}
