import { redirect } from "next/navigation";

import { FloatingLogos } from "@/components/brand/floating-logos";
import { AUTH_HEADERS } from "@/lib/auth/cookies";
import { getAuthTokens } from "@/lib/auth/session";
import { getT } from "@/lib/i18n/server";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/**
 * Account bootstrap (F.1): resolve the signed-in user's account from
 * `/api/v1/profile` and redirect to its dashboard. The real account
 * switcher lands in F.2.
 */
export default async function AccountsIndex() {
  const t = await getT();
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
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden p-6 text-fg">
      <FloatingLogos />
      <div
        data-bounce
        className="glass-panel relative z-10 w-full max-w-md rounded-panel bg-surface p-8"
      >
        <div className="neon-sign">
          <h1 className="text-[28px] leading-[1.2]">{t("errors.noAccountsTitle")}</h1>
        </div>
        <p className="mt-2 text-sm text-fg-muted">
          {t("errors.noAccountsBody")}
        </p>
      </div>
    </main>
  );
}
