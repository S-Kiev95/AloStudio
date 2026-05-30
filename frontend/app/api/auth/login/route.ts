import { NextResponse } from "next/server";

import { persistSessionFromResponse } from "@/lib/auth/session";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/**
 * Login route handler: calls the backend `/auth/sign_in`, captures the
 * devise response headers, and stores them as httpOnly cookies. The
 * browser only ever receives the user payload + the account to land on.
 */
export async function POST(req: Request): Promise<Response> {
  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid body" }, { status: 400 });
  }
  const { email, password } = (payload ?? {}) as {
    email?: string;
    password?: string;
  };
  if (!email || !password) {
    return NextResponse.json(
      { errors: ["Email and password are required."] },
      { status: 422 },
    );
  }

  let res: Response;
  try {
    res = await fetch(`${BACKEND}/auth/sign_in`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    return NextResponse.json(
      { errors: ["No se pudo contactar el servidor."] },
      { status: 502 },
    );
  }

  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    // Pass devise's error envelope straight through (e.g. invalid creds).
    return NextResponse.json(body, { status: res.status });
  }

  const accountId = await persistSessionFromResponse(res, body);
  if (accountId === false) {
    return NextResponse.json(
      { errors: ["El servidor no devolvió credenciales de sesión."] },
      { status: 502 },
    );
  }
  const data = (body as { data?: Record<string, unknown> })?.data ?? {};
  return NextResponse.json({ ok: true, accountId, user: data });
}
