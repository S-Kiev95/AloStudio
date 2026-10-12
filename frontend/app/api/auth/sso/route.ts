import { NextResponse } from "next/server";

import { persistSessionFromResponse } from "@/lib/auth/session";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/**
 * SSO route handler: exchanges the Postiz-minted JWT (from
 * `/auth/sso?token=…`) for an AloStudio session via the backend's
 * `POST /auth/sso`, then stores the devise headers as the same httpOnly
 * cookies the login route sets.
 */
export async function POST(req: Request): Promise<Response> {
  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid body" }, { status: 400 });
  }
  const { token } = (payload ?? {}) as { token?: string };
  if (!token) {
    return NextResponse.json(
      { errors: ["Falta el token de SSO."] },
      { status: 422 },
    );
  }

  let res: Response;
  try {
    res = await fetch(`${BACKEND}/auth/sso`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
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
  const data = (body as { data?: Record<string, unknown> })?.data ?? {};
  return NextResponse.json({ ok: true, accountId, user: data });
}
