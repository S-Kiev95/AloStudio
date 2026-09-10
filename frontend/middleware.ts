import { type NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIES } from "@/lib/auth/cookies";

/**
 * Auth guard. Protects the dashboard (everything under /accounts/*) by
 * checking for the presence of the devise auth cookie. The actual login
 * that sets the cookie lands in F.1; the guard is wired now so protected
 * routes redirect unauthenticated users to /login.
 */
export function middleware(req: NextRequest) {
  const hasSession = Boolean(
    req.cookies.get(AUTH_COOKIES.accessToken)?.value,
  );
  if (!hasSession) {
    const loginUrl = new URL("/login", publicOrigin(req));
    loginUrl.searchParams.set("next", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

/**
 * The origin the visitor actually typed, not the one Next is bound to.
 *
 * ``req.nextUrl.origin`` is built from the listening address, so behind the
 * Tailscale Funnel it is ``http://localhost:3000`` and the redirect sent
 * signed-out visitors to their own machine — a dead end that reads as the
 * app being down rather than as needing to sign in.
 *
 * A relative ``Location`` would sidestep the question, and is legal HTTP,
 * but not here: Next parses that header as a URL and throws
 * ``ERR_INVALID_URL`` on a relative one, which turns the bad redirect into
 * a 500. Verified the hard way.
 *
 * So we read the proxy's own account of the request. ``x-forwarded-host``
 * first, then ``host`` for a proxy that passes it through untouched. When
 * neither says anything — no proxy at all, or one that hides both — this
 * falls back to ``nextUrl.origin`` and behaves exactly as it used to.
 */
function publicOrigin(req: NextRequest): string {
  const host =
    req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  if (!host) return req.nextUrl.origin;

  // ``x-forwarded-proto`` can be a list when more than one proxy is in the
  // chain; the first entry is the one the client spoke.
  const forwardedProto = req.headers
    .get("x-forwarded-proto")
    ?.split(",")[0]
    ?.trim();
  const proto = forwardedProto || req.nextUrl.protocol.replace(/:$/, "");
  return `${proto}://${host}`;
}

export const config = {
  // Guard the dashboard only. /login, /api/*, static assets stay public.
  matcher: ["/accounts/:path*"],
};
