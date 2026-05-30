import { NextResponse } from "next/server";

import { AUTH_HEADERS } from "@/lib/auth/cookies";
import { clearAuthCookies, getAuthTokens } from "@/lib/auth/session";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/**
 * Logout: best-effort invalidate the session on the backend
 * (`DELETE /auth/sign_out`), then clear the cookies regardless.
 */
export async function POST(): Promise<Response> {
  const tokens = await getAuthTokens();
  if (tokens) {
    try {
      await fetch(`${BACKEND}/auth/sign_out`, {
        method: "DELETE",
        headers: {
          [AUTH_HEADERS.accessToken]: tokens.accessToken,
          [AUTH_HEADERS.client]: tokens.client,
          [AUTH_HEADERS.uid]: tokens.uid,
        },
      });
    } catch {
      // Ignore — we still clear the local session below.
    }
  }
  await clearAuthCookies();
  return NextResponse.json({ ok: true });
}
