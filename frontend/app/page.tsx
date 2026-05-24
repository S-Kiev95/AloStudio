import { redirect } from "next/navigation";

import { getAuthTokens } from "@/lib/auth/session";

/**
 * Root: send signed-in users to their dashboard, everyone else to login.
 * (Account routing refines in F.2 once we read the profile's accounts.)
 */
export default async function Home() {
  const tokens = await getAuthTokens();
  redirect(tokens ? "/accounts" : "/login");
}
