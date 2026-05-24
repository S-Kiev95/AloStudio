import "server-only";

import { cookies } from "next/headers";

import { AUTH_COOKIES, type AuthTokens } from "./cookies";

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
