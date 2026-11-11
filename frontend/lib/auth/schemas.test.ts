import { describe, expect, it } from "vitest";

import { loginSchema, signupSchema } from "./schemas";

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

describe("signupSchema", () => {
  it("accepts valid company name, user name, email and 6+ char password", () => {
    const r = signupSchema.safeParse({
      account_name: "AloStudio",
      user_full_name: "Ana Pérez",
      email: "ana@alostudio.test",
      password: "secreto",
    });
    expect(r.success).toBe(true);
  });

  it("rejects passwords shorter than 6 characters", () => {
    const r = signupSchema.safeParse({
      account_name: "AloStudio",
      user_full_name: "Ana Pérez",
      email: "ana@alostudio.test",
      password: "12345",
    });
    expect(r.success).toBe(false);
  });
});
