import { redirect } from "next/navigation";

import { AUTH_HEADERS } from "@/lib/auth/cookies";
import { getAuthTokens } from "@/lib/auth/session";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/**
 * Account bootstrap (F.1): resolve the signed-in user's account from
 * `/api/v1/profile` and redirect to its dashboard. The real account
 * switcher lands in F.2.
 */
export default async function AccountsIndex() {
  const tokens = await getAuthTokens();
  if (!tokens) redirect("/login");

  let accountId: number | null = null;
  let unauthorized = false;
  try {
    const res = await fetch(`${BACKEND}/api/v1/profile`, {
      headers: {
        [AUTH_HEADERS.accessToken]: tokens.accessToken,
        [AUTH_HEADERS.client]: tokens.client,
        [AUTH_HEADERS.uid]: tokens.uid,
      },
      cache: "no-store",
    });
    if (res.status === 401) {
      unauthorized = true;
    } else if (res.ok) {
      const data = (await res.json())?.data ?? {};
      accountId =
        data.account_id ?? data.accounts?.[0]?.id ?? null;
    }
  } catch {
    // Network error — fall through to the empty state below.
  }

  // redirect() throws NEXT_REDIRECT, so keep it outside the try/catch.
  if (unauthorized) redirect("/login");
  if (accountId) redirect(`/accounts/${accountId}`);

  return (
    <main className="mx-auto max-w-md p-8 text-fg">
      <h1 className="text-xl font-semibold">Sin cuentas</h1>
      <p className="mt-2 text-sm text-fg-muted">
        Tu usuario no tiene cuentas asociadas todavía.
      </p>
    </main>
  );
}
