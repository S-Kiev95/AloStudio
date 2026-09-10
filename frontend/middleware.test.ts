import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { AUTH_COOKIES } from "@/lib/auth/cookies";
import { middleware } from "./middleware";

/**
 * The guard sent signed-out visitors to a machine that was not theirs.
 *
 * ``NextResponse.redirect`` needs an absolute URL, and the only origin
 * available inside middleware is the one Next binds to. Served behind the
 * Tailscale Funnel, opening a dashboard link without a session answered
 * ``Location: https://localhost:3000/login`` — a dead end that reads as the
 * app being down. Next does not read ``Host`` here, so sending the request
 * to port 3000 with the public host set changed nothing.
 *
 * These build the request on ``localhost`` on purpose: the point is that
 * the answer carries no origin at all, whatever origin asked.
 */
function request(path: string, withSession = false): NextRequest {
  const req = new NextRequest(new URL(path, "http://localhost:3000"));
  if (withSession) {
    req.cookies.set(AUTH_COOKIES.accessToken, "un-token");
  }
  return req;
}

describe("the dashboard guard", () => {
  it("redirects without naming an origin", () => {
    const res = middleware(request("/accounts/1/conversations/1"));

    expect(res.status).toBe(307);
    const location = res.headers.get("location");
    expect(location).toBe("/login?next=%2Faccounts%2F1%2Fconversations%2F1");
    // The regression, stated as itself: an absolute Location here is wrong
    // on every origin but the one Next happens to bind to.
    expect(location).not.toMatch(/^https?:\/\//);
    expect(location).not.toContain("localhost");
  });

  it("keeps the path so the login can send you back", () => {
    const res = middleware(request("/accounts/9/ajustes/campanas"));

    expect(res.headers.get("location")).toBe(
      "/login?next=%2Faccounts%2F9%2Fajustes%2Fcampanas",
    );
  });

  it("lets a request with the session cookie through", () => {
    const res = middleware(request("/accounts/1/conversations/1", true));

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });
});
