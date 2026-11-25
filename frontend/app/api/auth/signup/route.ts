import { NextResponse } from "next/server";

import { persistSessionFromResponse } from "@/lib/auth/session";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/**
 * Signup route handler: forwards `POST /api/v1/accounts` to the backend.
 *
 * - On a multitenant install the backend returns `{ email }` without session
 *   headers and sends a confirmation email.
 * - On a dedicated install the backend mints a devise session immediately;
 *   we capture the headers into httpOnly cookies just like `/api/auth/login`.
 */
export async function POST(req: Request): Promise<Response> {
  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ message: "Datos inválidos." }, { status: 400 });
  }
  const { account_name, user_full_name, email, password } = (payload ?? {}) as {
    account_name?: string;
    user_full_name?: string;
    email?: string;
    password?: string;
  };
  if (!account_name || !user_full_name || !email || !password) {
    return NextResponse.json(
      { message: "Completá todos los campos obligatorios." },
      { status: 422 },
    );
  }

  let res: Response;
  try {
    res = await fetch(`${BACKEND}/api/v1/accounts`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...forwardedFor(req),
      },
      body: JSON.stringify({
        account_name,
        user_full_name,
        email,
        password,
      }),
    });
  } catch {
    return NextResponse.json(
      { message: "No se pudo contactar el servidor." },
      { status: 502 },
    );
  }

  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (
      res.status === 429 &&
      (typeof (body as { message?: unknown })?.message !== "string" ||
        !(body as { message: string }).message)
    ) {
      return NextResponse.json(
        { message: "Demasiados registros seguidos. Probá más tarde." },
        { status: 429 },
      );
    }
    return NextResponse.json(body, { status: res.status });
  }

  const accountId = await persistSessionFromResponse(res, body);
  if (accountId !== false) {
    const data = (body as { data?: Record<string, unknown> })?.data ?? {};
    return NextResponse.json({ ok: true, accountId, user: data });
  }

  const confirmedEmail = (body as { email?: unknown })?.email;
  if (typeof confirmedEmail === "string" && confirmedEmail) {
    return NextResponse.json({ email: confirmedEmail });
  }

  return NextResponse.json(
    { message: "El servidor no devolvió credenciales de sesión." },
    { status: 502 },
  );
}

function forwardedFor(req: Request): Record<string, string> {
  const xff = req.headers.get("x-forwarded-for");
  return xff ? { "X-Forwarded-For": xff } : {};
}
