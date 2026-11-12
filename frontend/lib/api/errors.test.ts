import { describe, expect, it } from "vitest";

import { ApiError, messageFromBody } from "./errors";

describe("messageFromBody", () => {
  it("reads ChatwootHTTPException {message}", () => {
    expect(messageFromBody({ message: "boom" }, "fb")).toBe("boom");
  });

  it("reads RecordNotFound {error}", () => {
    expect(
      messageFromBody({ error: "Resource could not be found" }, "fb"),
    ).toBe("Resource could not be found");
  });

  it("joins devise {errors: [...]}", () => {
    expect(messageFromBody({ errors: ["a", "b"] }, "fb")).toBe("a, b");
  });

  it("reads FastAPI {detail}", () => {
    expect(messageFromBody({ detail: "nope" }, "fb")).toBe("nope");
  });

  it("falls back when shape is unknown", () => {
    expect(messageFromBody(123, "fallback")).toBe("fallback");
    expect(messageFromBody(null, "fallback")).toBe("fallback");
  });

  it("says a permission denial in our own words", () => {
    // The English text has to keep arriving — an external client reads it —
    // so the body carries both and `code` is what we key on.
    expect(
      messageFromBody(
        {
          error: "You are not authorized to do this action",
          code: "not_authorized",
        },
        "fb",
      ),
    ).toBe("No tenés permiso para hacer esto.");
  });

  it("names the field for blank / taken, and follows the language cookie", () => {
    const body = { message: "Phone number can't be blank", code: "blank", field: "phone_number" };
    expect(messageFromBody(body, "fb")).toBe("Falta completar: Teléfono.");
    document.cookie = "alo_locale=en; path=/";
    try {
      expect(messageFromBody(body, "fb")).toBe("Missing: Phone number.");
      expect(
        messageFromBody({ errors: ["Invalid login credentials."], code: "invalid_login" }, "fb"),
      ).toBe("The email or password isn't correct.");
    } finally {
      document.cookie = "alo_locale=; path=/; max-age=0";
    }
  });

  it("leaves a code it has no wording for alone", () => {
    expect(
      messageFromBody({ error: "Something else", code: "some_other" }, "fb"),
    ).toBe("Something else");
  });
});

describe("ApiError", () => {
  it("carries status + body", () => {
    const err = new ApiError(422, "bad", { message: "bad" }, "X");
    expect(err.status).toBe(422);
    expect(err.code).toBe("X");
    expect(err.message).toBe("bad");
  });
});
