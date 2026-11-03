import { randomBytes } from "node:crypto";

import { NextResponse } from "next/server";

import { GOOGLE_NONCE_COOKIE } from "@/lib/auth/cookies";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/**
 * "Entrar con Google": draws this browser's nonce, keeps it in an httpOnly
 * cookie and sends the browser to Google's consent page, whose URL the
 * backend builds (with the nonce inside its signed state).
 */
export async function GET(req: Request): Promise<Response> {
  const nonce = randomBytes(24).toString("hex");
  let url: string | undefined;
  try {
    const res = await fetch(
      `${BACKEND}/auth/google/authorize_url?nonce=${nonce}`,
      { cache: "no-store" },
    );
    if (res.ok) url = (await res.json())?.url;
  } catch {
    url = undefined;
  }
  if (!url) {
    return NextResponse.redirect(new URL("/login?google=off", req.url));
  }
  const response = NextResponse.redirect(url);
  response.cookies.set(GOOGLE_NONCE_COOKIE, nonce, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    // Lax: Google brings the browser back with a top-level navigation.
    sameSite: "lax",
    path: "/",
    maxAge: 10 * 60,
  });
  return response;
}
