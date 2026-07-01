import { redirect } from "next/navigation";

import { HOME_PADRAO } from "@/lib/access-matrix";
import { getSupabaseServerClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function Home() {
  const supabase = await getSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  redirect(user ? HOME_PADRAO : "/login");
}
