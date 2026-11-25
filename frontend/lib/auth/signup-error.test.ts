import { describe, expect, it } from "vitest";

import { signupError } from "./signup-error";

describe("signupError", () => {
  it("says which field failed FastAPI's validation", () => {
    const body = { detail: [{ loc: ["body", "email"], msg: "value is not a valid email address" }] };
    expect(signupError(body)).toMatch(/correo no es válido/);
    expect(signupError({ detail: [{ loc: ["body", "password"] }] })).toMatch(/entre 8 y 72/);
  });

  it("puts the account builder's English messages in Spanish", () => {
    expect(signupError({ message: "User already exists with the given email" })).toMatch(
      /Ya hay una cuenta con ese correo/,
    );
    expect(signupError({ message: "Email is invalid" })).toMatch(/correo no es válido/);
  });

  it("keeps any other message and falls back when there is none", () => {
    expect(signupError({ message: "Otro motivo" })).toBe("Otro motivo");
    expect(signupError({})).toBe("No se pudo crear la cuenta.");
  });
});
