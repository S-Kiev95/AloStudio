import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/** Request a password-reset email. Backend never enumerates (always 200). */
export async function POST(req: Request): Promise<Response> {
  const { email } = (await req.json().catch(() => ({}))) as {
    email?: string;
  };
  if (!email) {
    return NextResponse.json(
      { errors: ["El email es obligatorio."] },
      { status: 422 },
    );
  }
  try {
    const res = await fetch(`${BACKEND}/auth/password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const body = await res.json().catch(() => ({}));
    return NextResponse.json(body, { status: res.ok ? 200 : res.status });
  } catch {
    return NextResponse.json(
      { errors: ["No se pudo contactar el servidor."] },
      { status: 502 },
    );
  }
}
