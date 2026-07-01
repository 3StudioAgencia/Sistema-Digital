import { redirect } from "next/navigation";

import { HOME_PADRAO } from "@/lib/access-matrix";

export default function InicioPage() {
  redirect(HOME_PADRAO);
}
