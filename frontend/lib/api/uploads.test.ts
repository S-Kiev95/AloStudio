import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { mimeToFileType, uploadAttachment } from "./uploads";

const server = setupServer(
  http.post("*/uploads/blob", () =>
    HttpResponse.json({
      key: "accounts/1/uploads/abc/report.png",
      file_url: "http://minio.test/alostudio/report.png",
    }),
  ),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("mimeToFileType", () => {
  it("maps MIME types to the attachment enum", () => {
    expect(mimeToFileType("image/png")).toBe("image");
    expect(mimeToFileType("audio/mpeg")).toBe("audio");
    expect(mimeToFileType("video/mp4")).toBe("video");
    expect(mimeToFileType("application/pdf")).toBe("file");
    expect(mimeToFileType(undefined)).toBe("file");
  });
});

describe("uploadAttachment", () => {
  it("POSTs the file and returns the attachment ref", async () => {
    const file = new File([new Uint8Array([1, 2, 3])], "report.png", {
      type: "image/png",
    });
    const res = await uploadAttachment("1", file);
    expect(res).toEqual({
      external_url: "http://minio.test/alostudio/report.png",
      file_type: "image",
    });
  });

  it("throws when the upload fails", async () => {
    server.use(
      http.post("*/uploads/blob", () =>
        HttpResponse.text("denied", { status: 500 }),
      ),
    );
    const file = new File([new Uint8Array([1])], "f.txt", {
      type: "text/plain",
    });
    await expect(uploadAttachment("1", file)).rejects.toThrow(/upload failed/);
  });
});
