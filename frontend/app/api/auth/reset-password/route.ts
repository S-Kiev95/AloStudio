import { NextResponse } from "next/server";

import { persistSessionFromResponse } from "@/lib/auth/session";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/**
 * Apply a password reset (`PUT /auth/password`). On success the backend
 * mints a fresh session — we capture it into cookies and sign the user
 * straight in.
 */
export async function POST(req: Request): Promise<Response> {
  const { token, password, passwordConfirmation } = (await req
    .json()
    .catch(() => ({}))) as {
    token?: string;
    password?: string;
    passwordConfirmation?: string;
  };
  if (!token || !password) {
    return NextResponse.json(
      { errors: ["Token y contraseña son obligatorios."] },
      { status: 422 },
    );
  }
  let res: Response;
  try {
    res = await fetch(`${BACKEND}/auth/password`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reset_password_token: token,
        password,
        password_confirmation: passwordConfirmation ?? password,
      }),
    });
  } catch {
    return NextResponse.json(
      { errors: ["No se pudo contactar el servidor."] },
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
      { errors: ["El servidor no devolvió credenciales de sesión."] },
      { status: 502 },
    );
  }
  return NextResponse.json({ ok: true, accountId });
}
