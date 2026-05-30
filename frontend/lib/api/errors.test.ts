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
});

describe("ApiError", () => {
  it("carries status + body", () => {
    const err = new ApiError(422, "bad", { message: "bad" }, "X");
    expect(err.status).toBe(422);
    expect(err.code).toBe("X");
    expect(err.message).toBe("bad");
  });
});
