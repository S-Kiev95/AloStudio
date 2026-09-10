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
    // A *relative* Location, deliberately. ``NextResponse.redirect`` only
    // takes an absolute URL, and the origin it would be built from is the
    // one Next binds to — ``localhost:3000``. Behind the Tailscale Funnel
    // that sent every signed-out visitor on the public URL to a machine
    // that was not theirs, which is a dead end and looks like the app
    // being down. Next does not read the ``Host`` header here either, so
    // there is no absolute URL to build that would be right on both
    // origins.
    //
    // A relative reference is legal in ``Location`` (RFC 7231 §7.1.2) and
    // the browser resolves it against the URL it actually requested, so it
    // is correct on localhost, on the Funnel, and on whatever the app is
    // served from next — without trusting a proxy header.
    const next = encodeURIComponent(req.nextUrl.pathname);
    return new NextResponse(null, {
      status: 307,
      headers: { Location: `/login?next=${next}` },
    });
  }
  return NextResponse.next();
}

export const config = {
  // Guard the dashboard only. /login, /api/*, static assets stay public.
  matcher: ["/accounts/:path*"],
};
