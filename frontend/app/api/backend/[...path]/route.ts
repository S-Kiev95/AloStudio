import { cookies } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIES, AUTH_HEADERS } from "@/lib/auth/cookies";

/**
 * BFF proxy: browser → this same-origin route → FastAPI backend.
 *
 * Reads the httpOnly devise cookies and re-attaches them as the devise
 * **headers** (access-token / client / uid / expiry) the backend
 * expects. This is the cookie↔header bridge: the browser never sees the
 * tokens, but the backend still gets header auth.
 *
 * F.1 will add the login route that SETS these cookies. Until then the
 * proxy forwards unauthenticated (the backend answers 401, which the
 * client turns into a /login redirect).
 */
const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
const BACKEND_ORIGIN = new URL(BACKEND).origin;

// Hop-by-hop / unsafe headers we must not forward upstream.
//
// SECURITY: the four devise auth headers are stripped here too — they
// must come ONLY from the httpOnly cookies (set below), never from a
// client-supplied header, so the browser can't bypass the cookie model
// by sending its own ``access-token`` etc. (defence in depth for the
// httpOnly-token invariant).
const STRIP = new Set([
  "host",
  "connection",
  "content-length",
  "cookie",
  "transfer-encoding",
  "access-token",
  "client",
  "uid",
  "expiry",
]);

async function handle(req: NextRequest, path: string[]): Promise<Response> {
  const jar = await cookies();
  const target = new URL(
    `/${path.join("/")}${req.nextUrl.search}`,
    BACKEND,
  );

  // SECURITY: never let a crafted path (e.g. a leading empty segment
  // turning the relative ref into ``//evil.com``) resolve the target to
  // a different origin — we attach the user's auth headers below, so an
  // off-origin target would exfiltrate their devise token. Pin to the
  // backend origin.
  if (target.origin !== BACKEND_ORIGIN) {
    return new NextResponse(
      JSON.stringify({ error: "Bad gateway" }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!STRIP.has(key.toLowerCase())) headers.set(key, value);
  });

  // Attach devise auth headers from the httpOnly cookies.
  const accessToken = jar.get(AUTH_COOKIES.accessToken)?.value;
  const client = jar.get(AUTH_COOKIES.client)?.value;
  const uid = jar.get(AUTH_COOKIES.uid)?.value;
  const expiry = jar.get(AUTH_COOKIES.expiry)?.value;
  if (accessToken && client && uid) {
    headers.set(AUTH_HEADERS.accessToken, accessToken);
    headers.set(AUTH_HEADERS.client, client);
    headers.set(AUTH_HEADERS.uid, uid);
    if (expiry) headers.set(AUTH_HEADERS.expiry, expiry);
  }

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  const upstream = await fetch(target, init);
  // Pass the body + status straight back (strip hop-by-hop on the way out).
  const respHeaders = new Headers(upstream.headers);
  respHeaders.delete("transfer-encoding");
  respHeaders.delete("content-encoding");
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: respHeaders,
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return handle(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return handle(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return handle(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return handle(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return handle(req, (await ctx.params).path);
}
