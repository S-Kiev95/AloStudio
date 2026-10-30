import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./errors";
import { apiFetch } from "./fetcher";

const original = window.location;

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status < 400,
      status,
      text: async () => JSON.stringify(body),
    }),
  );
}

beforeEach(() => {
  // jsdom's location is read-only; a plain object lets the assignment the
  // redirect performs be observed.
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { href: "/somewhere" },
  });
});

afterEach(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: original,
  });
  vi.unstubAllGlobals();
});

describe("apiFetch on a 401", () => {
  it("sends an expired session back to the login screen", async () => {
    mockFetch(401, { errors: ["Invalid login credentials"] });
    await expect(apiFetch("/whatever")).rejects.toBeInstanceOf(ApiError);
    expect(window.location.href).toBe("/login");
  });

  it("remembers where the user was, so signing in brings them back", async () => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: {
        href: "/oauth/authorize?client_id=alo_app_1&state=x",
        pathname: "/oauth/authorize",
        search: "?client_id=alo_app_1&state=x",
      },
    });
    mockFetch(401, { errors: ["Invalid login credentials"] });
    await expect(apiFetch("/api/v1/oauth/authorize")).rejects.toBeInstanceOf(ApiError);
    expect(window.location.href).toBe(
      "/login?next=%2Foauth%2Fauthorize%3Fclient_id%3Dalo_app_1%26state%3Dx",
    );
  });

  it("keeps an agent on the page when a panel is admin-only", async () => {
    // The API keeps Chatwoot's shape, where "not an administrator" is also
    // a 401. Redirecting on it threw an agent back to login the moment a
    // page touched an admin endpoint.
    mockFetch(401, {
      error: "You are not authorized to do this action",
      code: "not_authorized",
    });
    await expect(apiFetch("/campaigns")).rejects.toBeInstanceOf(ApiError);
    expect(window.location.href).toBe("/somewhere");
  });

  it("still reports the denial to the caller", async () => {
    mockFetch(401, {
      error: "You are not authorized to do this action",
      code: "not_authorized",
    });
    // The panel that asked has to be able to say something happened.
    await expect(apiFetch("/campaigns")).rejects.toMatchObject({ status: 401 });
  });

  it("does not redirect on other failures", async () => {
    mockFetch(422, { message: "Falta el texto" });
    await expect(apiFetch("/rules")).rejects.toBeInstanceOf(ApiError);
    expect(window.location.href).toBe("/somewhere");
  });

  it("returns the body on success", async () => {
    mockFetch(200, { id: 7 });
    await expect(apiFetch<{ id: number }>("/x")).resolves.toEqual({ id: 7 });
  });
});
