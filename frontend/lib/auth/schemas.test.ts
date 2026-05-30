import { describe, expect, it } from "vitest";

import { loginSchema } from "./schemas";

describe("loginSchema", () => {
  it("accepts a valid email + password", () => {
    const r = loginSchema.safeParse({ email: "a@b.com", password: "x" });
    expect(r.success).toBe(true);
  });

  it("rejects an invalid email", () => {
    const r = loginSchema.safeParse({ email: "nope", password: "x" });
    expect(r.success).toBe(false);
  });

  it("rejects an empty password", () => {
    const r = loginSchema.safeParse({ email: "a@b.com", password: "" });
    expect(r.success).toBe(false);
  });
});
