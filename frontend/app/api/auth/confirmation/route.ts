import { NextResponse } from "next/server";

import { persistSessionFromResponse } from "@/lib/auth/session";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/**
 * Consume an email-confirmation token (`POST /auth/confirmation`). On
 * success the backend confirms the account + mints a session — we capture
 * it into cookies (auto sign-in after confirmation).
 */
export async function POST(req: Request): Promise<Response> {
  const { token } = (await req.json().catch(() => ({}))) as {
    token?: string;
  };
  if (!token) {
    return NextResponse.json(
      { message: "Token requerido." },
      { status: 422 },
    );
  }
  let res: Response;
  try {
    res = await fetch(`${BACKEND}/auth/confirmation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation_token: token }),
    });
  } catch {
    return NextResponse.json(
      { message: "No se pudo contactar el servidor." },
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
      { message: "El servidor no devolvió credenciales de sesión." },
      { status: 502 },
    );
  }
  return NextResponse.json({ ok: true, accountId });
}
