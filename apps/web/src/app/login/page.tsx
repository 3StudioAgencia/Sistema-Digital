import { redirect } from "next/navigation";

import { HOME_PADRAO } from "@/lib/access-matrix";
import { getSupabaseServerClient } from "@/lib/supabase/server";

import { AuthFlow } from "../_components/auth-flow";

export const dynamic = "force-dynamic";
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const supabase = await getSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) redirect(HOME_PADRAO);

  const sp = await searchParams;
  return <AuthFlow expired={sp.expirado === "1"} />;
}
