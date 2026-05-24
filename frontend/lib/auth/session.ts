import "server-only";

import { cookies } from "next/headers";

import { AUTH_COOKIES, AUTH_HEADERS, type AuthTokens } from "./cookies";

const COOKIE_OPTS = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  // ~60 days — devise long-lived window. Refreshed on each sign-in.
  maxAge: 60 * 60 * 24 * 60,
};

/** Persist the devise tokens as httpOnly cookies (called by login). */
export async function setAuthCookies(tokens: AuthTokens): Promise<void> {
  const jar = await cookies();
  jar.set(AUTH_COOKIES.accessToken, tokens.accessToken, COOKIE_OPTS);
  jar.set(AUTH_COOKIES.client, tokens.client, COOKIE_OPTS);
  jar.set(AUTH_COOKIES.uid, tokens.uid, COOKIE_OPTS);
  if (tokens.expiry) {
    jar.set(AUTH_COOKIES.expiry, tokens.expiry, COOKIE_OPTS);
  }
}

/** Read the devise tokens from cookies (or null if not signed in). */
export async function getAuthTokens(): Promise<AuthTokens | null> {
  const jar = await cookies();
  const accessToken = jar.get(AUTH_COOKIES.accessToken)?.value;
  const client = jar.get(AUTH_COOKIES.client)?.value;
  const uid = jar.get(AUTH_COOKIES.uid)?.value;
  if (!accessToken || !client || !uid) return null;
  return {
    accessToken,
    client,
    uid,
    expiry: jar.get(AUTH_COOKIES.expiry)?.value,
  };
}

/** Clear all auth cookies (called by logout). */
export async function clearAuthCookies(): Promise<void> {
  const jar = await cookies();
  for (const name of Object.values(AUTH_COOKIES)) {
    jar.delete(name);
  }
}

/**
 * Capture the devise auth headers off a backend auth response and store
 * them as cookies. Shared by every endpoint that mints a session
 * (sign_in, password reset, email confirmation).
 *
 * Returns the account id to land on, or ``false`` if the response lacked
 * session headers (treat as a 502).
 */
export async function persistSessionFromResponse(
  res: Response,
  body: unknown,
): Promise<number | null | false> {
  const accessToken = res.headers.get(AUTH_HEADERS.accessToken);
  const client = res.headers.get(AUTH_HEADERS.client);
  const uid = res.headers.get(AUTH_HEADERS.uid);
  if (!accessToken || !client || !uid) return false;
  await setAuthCookies({
    accessToken,
    client,
    uid,
    expiry: res.headers.get(AUTH_HEADERS.expiry) ?? undefined,
  });
  const data = (body as { data?: Record<string, unknown> })?.data ?? {};
  return (
    (data.account_id as number | null) ??
    ((data.accounts as Array<{ id: number }> | undefined)?.[0]?.id ?? null)
  );
}
