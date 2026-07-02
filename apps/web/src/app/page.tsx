import { redirect } from "next/navigation";

import { HOME_PADRAO } from "@/lib/access-matrix";
import { lerSessao } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

export default async function Home() {
  const sessao = await lerSessao();
  redirect(sessao ? HOME_PADRAO : "/login");
}
