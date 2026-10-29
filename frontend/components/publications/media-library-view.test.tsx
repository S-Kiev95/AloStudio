import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import type { MediaAsset } from "@/lib/api/media";

import { MediaLibraryView } from "./media-library-view";

const ADMIN_PROFILE = {
  data: {
    id: 1,
    name: "Admin",
    email: "admin@alostudio.test",
    accounts: [{ id: 1, name: "Demo", role: 1 }],
  },
};

const AGENT_PROFILE = {
  data: {
    id: 2,
    name: "Agente",
    email: "agent@alostudio.test",
    accounts: [{ id: 1, name: "Demo", role: 0 }],
  },
};

const SAMPLE_ASSET: MediaAsset = {
  id: 42,
  kind: "image",
  content_type: "image/jpeg",
  filename: "portada.jpg",
  size_bytes: 1024 * 500,
  url: "https://s3.example/portada.jpg",
  uploaded_by_id: 1,
  created_at: "2026-10-20T12:00:00Z",
};

const server = setupServer(
  http.get("*/api/v1/profile", () => HttpResponse.json(ADMIN_PROFILE)),
  http.get("*/api/v1/accounts/1/media", () =>
    HttpResponse.json([SAMPLE_ASSET]),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());

function renderMediaLibrary() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MediaLibraryView accountId="1" />
    </QueryClientProvider>,
  );
}

function makeFakeSizedFile(
  name: string,
  type: string,
  sizeBytes: number,
): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: sizeBytes });
  return file;
}

describe("MediaLibraryView", () => {
  it("rechaza una imagen mayor a 30 MB y un video mayor a 200 MB antes de subir", async () => {
    let uploadCalls = 0;
    server.use(
      http.post("*/api/v1/accounts/1/media", () => {
        uploadCalls += 1;
        return HttpResponse.json(SAMPLE_ASSET);
      }),
    );

    renderMediaLibrary();
    expect(await screen.findByText("portada.jpg")).toBeInTheDocument();

    const input = screen.getByLabelText("Seleccionar archivos para subir");

    // 31 MB image -> rejected locally
    const hugeImage = makeFakeSizedFile(
      "gigante.png",
      "image/png",
      31 * 1024 * 1024,
    );
    fireEvent.change(input, { target: { files: [hugeImage] } });

    expect(await screen.findByRole("alert")).toHaveTextContent(/30 MB/);
    expect(uploadCalls).toBe(0);

    // 205 MB video via native drop -> rejected locally
    const hugeVideo = makeFakeSizedFile(
      "largo.mp4",
      "video/mp4",
      205 * 1024 * 1024,
    );
    fireEvent.drop(screen.getByTestId("media-dropzone"), {
      dataTransfer: { files: [hugeVideo] },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(/200 MB/);
    expect(uploadCalls).toBe(0);
  });

  it("sube un archivo válido y muestra el 422 del backend si se intenta borrar uno en uso", async () => {
    let uploaded = false;
    server.use(
      http.post("*/api/v1/accounts/1/media", () => {
        uploaded = true;
        return HttpResponse.json({
          ...SAMPLE_ASSET,
          id: 99,
          filename: "nuevo.png",
        });
      }),
      http.delete("*/api/v1/accounts/1/media/42", () =>
        HttpResponse.json(
          {
            message:
              "No se puede borrar porque está en uso en una publicación programada.",
          },
          { status: 422 },
        ),
      ),
    );
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderMediaLibrary();
    expect(await screen.findByText("portada.jpg")).toBeInTheDocument();

    const validFile = makeFakeSizedFile("nuevo.png", "image/png", 1024 * 120);
    const input = screen.getByLabelText("Seleccionar archivos para subir");
    fireEvent.change(input, { target: { files: [validFile] } });

    await waitFor(() => expect(uploaded).toBe(true));

    // Delete in-use asset -> displays 422 message
    fireEvent.click(
      await screen.findByRole("button", { name: "Borrar portada.jpg" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /está en uso en una publicación programada/,
    );
  });

  it("oculta el botón de borrar a un agente pero mantiene la subida", async () => {
    server.use(
      http.get("*/api/v1/profile", () => HttpResponse.json(AGENT_PROFILE)),
    );

    renderMediaLibrary();
    expect(await screen.findByText("portada.jpg")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Subir" })).toBeInTheDocument();

    const dropzone = screen.getByTestId("media-dropzone");
    expect(
      within(dropzone).queryByRole("button", { name: /Borrar/ }),
    ).toBeNull();
  });
});
