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
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("next", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  // Guard the dashboard only. /login, /api/*, static assets stay public.
  matcher: ["/accounts/:path*"],
};
