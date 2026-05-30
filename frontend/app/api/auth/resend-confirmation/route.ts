import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/** Resend the confirmation email. Backend always 204 (no enumeration). */
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
    await fetch(`${BACKEND}/resend_confirmation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
  } catch {
    // Swallow — we don't reveal whether the address exists.
  }
  return NextResponse.json({ ok: true });
}
