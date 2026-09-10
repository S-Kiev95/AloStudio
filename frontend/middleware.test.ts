import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { AUTH_COOKIES } from "@/lib/auth/cookies";
import { middleware } from "./middleware";

/**
 * The guard sent signed-out visitors to a machine that was not theirs.
 *
 * ``req.nextUrl.origin`` is the address Next is bound to, so behind the
 * Tailscale Funnel every dashboard link opened without a session answered
 * ``Location: http://localhost:3000/login`` — a dead end that reads as the
 * app being down.
 *
 * A relative ``Location`` looked like the clean answer and is legal HTTP,
 * but Next parses that header as a URL and throws ``ERR_INVALID_URL`` on a
 * relative one; shipping it turned the bad redirect into a 500. Hence the
 * last test here, which is the one that would have caught it: whatever we
 * put in ``Location`` has to survive ``new URL()`` on its own.
 *
 * The requests below are built on localhost on purpose — the point is that
 * the answer follows the *headers*, not the socket.
 */
function request(
  path: string,
  headers: Record<string, string> = {},
  withSession = false,
): NextRequest {
  const req = new NextRequest(new URL(path, "http://localhost:3000"), {
    headers,
  });
  if (withSession) {
    req.cookies.set(AUTH_COOKIES.accessToken, "un-token");
  }
  return req;
}

describe("the dashboard guard", () => {
  it("redirects to the host the visitor actually asked for", () => {
    const res = middleware(
      request("/accounts/1/conversations/1", {
        host: "vmi3426238.tail34088e.ts.net",
        "x-forwarded-proto": "https",
      }),
    );

    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(
      "https://vmi3426238.tail34088e.ts.net/login?next=%2Faccounts%2F1%2Fconversations%2F1",
    );
  });

  it("prefers x-forwarded-host over a rewritten host", () => {
    const res = middleware(
      request("/accounts/1/conversations/1", {
        host: "localhost:3000",
        "x-forwarded-host": "alostudio.example",
        "x-forwarded-proto": "https",
      }),
    );

    expect(res.headers.get("location")).toBe(
      "https://alostudio.example/login?next=%2Faccounts%2F1%2Fconversations%2F1",
    );
  });

  it("takes the first proto when a chain of proxies lists several", () => {
    const res = middleware(
      request("/accounts/1", {
        host: "alostudio.example",
        "x-forwarded-proto": "https, http",
      }),
    );

    expect(res.headers.get("location")).toBe(
      "https://alostudio.example/login?next=%2Faccounts%2F1",
    );
  });

  it("falls back to the bound origin when no proxy says anything", () => {
    // No worse than before this fix: with nothing to go on, the old
    // behaviour is the right behaviour.
    const res = middleware(request("/accounts/1"));

    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/login?next=%2Faccounts%2F1",
    );
  });

  it("keeps the path so the login can send you back", () => {
    const res = middleware(
      request("/accounts/9/settings/installation", {
        host: "alostudio.example",
      }),
    );

    expect(res.headers.get("location")).toContain(
      "next=%2Faccounts%2F9%2Fsettings%2Finstallation",
    );
  });

  it("answers a Location that is a URL on its own", () => {
    // Next throws ERR_INVALID_URL parsing a relative one, and the request
    // 500s. This is the assertion that was missing.
    const res = middleware(
      request("/accounts/1", { host: "alostudio.example" }),
    );
    const location = res.headers.get("location") ?? "";

    expect(() => new URL(location)).not.toThrow();
  });

  it("lets a request with the session cookie through", () => {
    const res = middleware(request("/accounts/1", {}, true));

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });
});
