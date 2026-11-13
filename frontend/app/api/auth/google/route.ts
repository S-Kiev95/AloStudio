import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { GOOGLE_NONCE_COOKIE } from "@/lib/auth/cookies";
import { persistSessionFromResponse } from "@/lib/auth/session";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/** Whether the login page shows "Entrar con Google". */
export async function GET(): Promise<Response> {
  try {
    const res = await fetch(`${BACKEND}/auth/google`, { cache: "no-store" });
    const body = await res.json().catch(() => ({}));
    return NextResponse.json({ enabled: Boolean(body?.enabled) });
  } catch {
    return NextResponse.json({ enabled: false });
  }
}

/**
 * Google's callback page posts `{ code, state }` here: the backend checks
 * them (with this browser's nonce) and answers like `/auth/sign_in`, whose
 * devise headers become the same httpOnly cookies the login route sets.
 */
export async function POST(req: Request): Promise<Response> {
  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid body" }, { status: 400 });
  }
  const { code, state } = (payload ?? {}) as { code?: string; state?: string };
  const jar = await cookies();
  const nonce = jar.get(GOOGLE_NONCE_COOKIE)?.value;
  jar.delete(GOOGLE_NONCE_COOKIE);
  if (!code || !state || !nonce) {
    return NextResponse.json(
      { errors: ["El ingreso con Google venció. Probá de nuevo."], code: "google_expired" },
      { status: 422 },
    );
  }

  let res: Response;
  try {
    res = await fetch(`${BACKEND}/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, state, nonce }),
    });
  } catch {
    return NextResponse.json(
      { errors: ["No se pudo contactar el servidor."], code: "server_unreachable" },
      { status: 502 },
    );
  }

  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    return NextResponse.json(body, { status: res.status });
  }

  const accountId = await persistSessionFromResponse(res, body);
  if (accountId === false) {
    return NextResponse.json(
      { errors: ["El servidor no devolvió credenciales de sesión."], code: "no_session" },
      { status: 502 },
    );
  }
  return NextResponse.json({ ok: true, accountId });
}
