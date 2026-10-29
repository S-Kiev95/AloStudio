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
import type {
  Channel,
  Publication,
  PublicationIn,
  PublicationSet,
  Signature,
} from "@/lib/api/publications";

import { PublicationEditorDialog } from "./publication-editor-dialog";

const IG_CHANNEL: Channel = {
  id: 10,
  network: "instagram",
  name: "AloStudio IG",
  username: "alostudio",
  avatar_url: null,
  status: "active",
  status_message: null,
  inbox_id: 3,
};

const THREADS_CHANNEL: Channel = {
  id: 20,
  network: "threads",
  name: "AloStudio Threads",
  username: "alostudio_th",
  avatar_url: null,
  status: "active",
  status_message: null,
  inbox_id: null,
};

const RECONNECT_CHANNEL: Channel = {
  id: 30,
  network: "facebook_page",
  name: "AloStudio FB",
  username: null,
  avatar_url: null,
  status: "reconnect",
  status_message: "Token expirado",
  inbox_id: 4,
};

const CHANNELS = [IG_CHANNEL, THREADS_CHANNEL, RECONNECT_CHANNEL];

const LIBRARY_ASSETS: MediaAsset[] = [
  {
    id: 101,
    kind: "image",
    filename: "foto-uno.jpg",
    content_type: "image/jpeg",
    size_bytes: 120_000,
    url: "https://s3.example/foto-uno.jpg",
    uploaded_by_id: 1,
    created_at: "2026-10-20T10:00:00Z",
  },
  {
    id: 102,
    kind: "video",
    filename: "reel-clip.mp4",
    content_type: "video/mp4",
    size_bytes: 4_500_000,
    url: "https://s3.example/reel-clip.mp4",
    uploaded_by_id: 1,
    created_at: "2026-10-20T11:00:00Z",
  },
];

const SIGNATURES: Signature[] = [
  {
    id: 1,
    content: "— Equipo AloStudio",
    auto_add: true,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  },
  {
    id: 2,
    content: "Consultas por DM",
    auto_add: false,
    created_at: "2026-10-02T00:00:00Z",
    updated_at: "2026-10-02T00:00:00Z",
  },
];

const SAVED_SETS: PublicationSet[] = [
  {
    id: 5,
    name: "Pack Lanzamiento",
    content: "Texto del set listo para publicar",
    media: [
      {
        media_id: 102,
        type: "video",
        url: "https://s3.example/reel-clip.mp4",
      },
    ],
    targets: [
      {
        channel_id: 10,
        channel: IG_CHANNEL,
        settings: { post_type: "reels" },
        content_override: null,
      },
      {
        channel_id: 20,
        channel: THREADS_CHANNEL,
        settings: {},
        content_override: "Versión corta en Threads",
      },
      {
        // Deleted channel -> must be ignored when applying set
        channel_id: 999,
        channel: null,
        settings: {},
        content_override: null,
      },
    ],
    created_at: "2026-10-10T00:00:00Z",
    updated_at: "2026-10-10T00:00:00Z",
  },
];

function stubCreatedPublication(body: PublicationIn): Publication {
  return {
    id: 700,
    account_id: 1,
    content: body.content ?? null,
    media: [],
    scheduled_for: body.scheduled_for ?? null,
    state: body.draft ? "draft" : body.scheduled_for ? "scheduled" : "publishing",
    created_by_id: 1,
    published_at: null,
    created_at: "2026-10-29T12:00:00Z",
    updated_at: "2026-10-29T12:00:00Z",
    targets: [],
  };
}

const server = setupServer(
  http.get("*/api/v1/accounts/1/publications/signatures", () =>
    HttpResponse.json([]),
  ),
  http.get("*/api/v1/accounts/1/publications/sets", () =>
    HttpResponse.json([]),
  ),
  http.get("*/api/v1/accounts/1/media", () =>
    HttpResponse.json(LIBRARY_ASSETS),
  ),
);

beforeAll(() => {
  server.listen({ onUnhandledRequest: "bypass" });
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});

afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());

function renderEditor({
  initial = null,
  defaultScheduledFor = null,
  onClose = vi.fn(),
}: {
  initial?: Publication | null;
  defaultScheduledFor?: Date | null;
  onClose?: () => void;
} = {}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <PublicationEditorDialog
        accountId="1"
        open={true}
        onClose={onClose}
        channels={CHANNELS}
        isAdmin={true}
        initial={initial}
        defaultScheduledFor={defaultScheduledFor}
      />
    </QueryClientProvider>,
  );
}

describe("PublicationEditorDialog — armado del cuerpo, reglas y 422", () => {
  it("arma el cuerpo de publicación programada con fecha ISO, media_id reordenados, post_type y content_override", async () => {
    const receivedBodies: PublicationIn[] = [];
    server.use(
      http.post("*/api/v1/accounts/1/publications", async ({ request }) => {
        const body = (await request.json()) as PublicationIn;
        receivedBodies.push(body);
        return HttpResponse.json(stubCreatedPublication(body));
      }),
    );

    const onClose = vi.fn();
    renderEditor({ onClose });

    // Only active channels are listed (RECONNECT_CHANNEL is excluded)
    expect(screen.queryByRole("button", { name: /AloStudio FB/ })).toBeNull();

    // Select Instagram + Threads
    fireEvent.click(screen.getByRole("button", { name: /AloStudio IG/ }));
    fireEvent.click(screen.getByRole("button", { name: /AloStudio Threads/ }));

    // Shared text
    fireEvent.change(screen.getByLabelText("Texto"), {
      target: { value: "Novedades de la semana" },
    });

    // Pick 2 media items from library (#101 then #102) and move #102 before #101
    fireEvent.click(
      screen.getByRole("button", { name: /Elegir de la biblioteca/i }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Elegir foto-uno.jpg" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Elegir reel-clip.mp4" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Mover medio 2 antes" }),
    );

    // Customize text on Threads
    const customizeButtons = screen.getAllByRole("button", {
      name: "Personalizar texto para este canal",
    });
    fireEvent.click(customizeButtons[1]); // 0 = IG, 1 = Threads
    fireEvent.change(screen.getByLabelText("Texto para AloStudio Threads"), {
      target: { value: "Hilo especial para Threads" },
    });

    // Schedule for specific local datetime
    const whenGroup = screen.getByRole("group", { name: "Cuándo publicar" });
    fireEvent.click(within(whenGroup).getByRole("button", { name: "Programar" }));

    const localInput = "2026-11-15T18:30";
    fireEvent.change(screen.getByLabelText("Fecha y hora de publicación"), {
      target: { value: localInput },
    });

    // Submit scheduled publication (draft: false) — second "Programar" button is the footer CTA
    const programarBtns = screen.getAllByRole("button", { name: "Programar" });
    fireEvent.click(programarBtns[programarBtns.length - 1]);

    await waitFor(() => expect(receivedBodies).toHaveLength(1));
    expect(receivedBodies[0]).toEqual({
      content: "Novedades de la semana",
      media: [{ media_id: 102 }, { media_id: 101 }],
      scheduled_for: new Date(localInput).toISOString(),
      draft: false,
      targets: [
        { channel_id: 10, settings: { post_type: "feed" } },
        {
          channel_id: 20,
          content_override: "Hilo especial para Threads",
        },
      ],
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("arma borrador (draft: true) y respeta post_type: 'reels' en Instagram", async () => {
    let sentBody: PublicationIn | null = null;
    server.use(
      http.post("*/api/v1/accounts/1/publications", async ({ request }) => {
        sentBody = (await request.json()) as PublicationIn;
        return HttpResponse.json(stubCreatedPublication(sentBody));
      }),
    );

    renderEditor();

    fireEvent.click(screen.getByRole("button", { name: /AloStudio IG/ }));
    const igTypeGroup = screen.getByRole("group", {
      name: /Tipo en AloStudio IG/i,
    });
    fireEvent.click(within(igTypeGroup).getByRole("button", { name: "Reels" }));

    // Pick video #102 from library
    fireEvent.click(
      screen.getByRole("button", { name: /Elegir de la biblioteca/i }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Elegir reel-clip.mp4" }),
    );

    fireEvent.change(screen.getByLabelText("Texto"), {
      target: { value: "Borrador de reel" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Guardar borrador" }));

    await waitFor(() => expect(sentBody).not.toBeNull());
    expect(sentBody).toMatchObject({
      content: "Borrador de reel",
      draft: true,
      media: [{ media_id: 102 }],
      targets: [{ channel_id: 10, settings: { post_type: "reels" } }],
    });
  });

  it("muestra errores de la tabla de reglas antes de enviar y muestra el 422 del backend con message y errors[]", async () => {
    let postCalls = 0;
    server.use(
      http.post("*/api/v1/accounts/1/publications", () => {
        postCalls += 1;
        return HttpResponse.json(
          {
            message: "No se pudo validar la publicación.",
            errors: [
              "Instagram: relación de aspecto fuera de rango",
              "Threads: cuenta temporalmente restringida",
            ],
          },
          { status: 422 },
        );
      }),
    );

    const onClose = vi.fn();
    renderEditor({ onClose });

    // Select Instagram -> Reels without a video triggers client-side rule error
    fireEvent.click(screen.getByRole("button", { name: /AloStudio IG/ }));
    const igTypeGroup = screen.getByRole("group", {
      name: /Tipo en AloStudio IG/i,
    });
    fireEvent.click(within(igTypeGroup).getByRole("button", { name: "Reels" }));

    // Submit button is the footer CTA (not the "Publicar ahora" option inside SegmentedControl)
    const publishNowBtns = screen.getAllByRole("button", {
      name: "Publicar ahora",
    });
    fireEvent.click(publishNowBtns[publishNowBtns.length - 1]);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Instagram Reels.*requiere exactamente 1 video/i,
    );
    expect(postCalls).toBe(0);

    // Fix client-side rule by picking video #102 -> now hits backend and displays 422 verbatim
    fireEvent.click(
      screen.getByRole("button", { name: /Elegir de la biblioteca/i }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Elegir reel-clip.mp4" }),
    );

    fireEvent.click(publishNowBtns[publishNowBtns.length - 1]);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No se pudo validar la publicación.");
    expect(alert).toHaveTextContent(
      "Instagram: relación de aspecto fuera de rango",
    );
    expect(alert).toHaveTextContent(
      "Threads: cuenta temporalmente restringida",
    );
    expect(postCalls).toBe(1);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("PublicationEditorDialog — firmas y sets", () => {
  it("arranca con la firma automática en una publicación nueva y permite agregar otra firma", async () => {
    server.use(
      http.get("*/api/v1/accounts/1/publications/signatures", () =>
        HttpResponse.json(SIGNATURES),
      ),
    );

    renderEditor();

    const textarea = screen.getByLabelText("Texto") as HTMLTextAreaElement;
    await waitFor(() =>
      expect(textarea.value).toBe("\n\n— Equipo AloStudio"),
    );

    // Click "Firma" and append the second signature on a new line
    fireEvent.click(screen.getByRole("button", { name: /Firma/i }));
    fireEvent.click(
      await screen.findByRole("menuitem", { name: /Consultas por DM/i }),
    );
    expect(textarea.value).toBe("\n\n— Equipo AloStudio\nConsultas por DM");
  });

  it("'Usar set' carga texto, medios y canales activos (ignorando channel: null) sin cambiar la fecha, y 'Guardar como set' envía el cuerpo esperado", async () => {
    let savedSetBody: unknown = null;
    server.use(
      http.get("*/api/v1/accounts/1/publications/sets", () =>
        HttpResponse.json(SAVED_SETS),
      ),
      http.post("*/api/v1/accounts/1/publications/sets", async ({ request }) => {
        savedSetBody = await request.json();
        return HttpResponse.json({
          ...SAVED_SETS[0],
          id: 99,
          name: "Set Viernes",
        });
      }),
    );

    const preset = new Date(2026, 10, 20, 14, 0, 0, 0);
    renderEditor({ defaultScheduledFor: preset });

    const dateInput = screen.getByLabelText(
      "Fecha y hora de publicación",
    ) as HTMLInputElement;
    const originalDateValue = dateInput.value;
    expect(originalDateValue).toMatch(/^2026-11-20T14:00$/);

    // Click "Usar set" -> select "Pack Lanzamiento"
    fireEvent.click(await screen.findByRole("button", { name: /Usar set/i }));
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Pack Lanzamiento" }),
    );

    // Content replaced
    expect((screen.getByLabelText("Texto") as HTMLTextAreaElement).value).toBe(
      "Texto del set listo para publicar",
    );
    // Media loaded (#102)
    expect(screen.getByText(/Medios \(1\)/)).toBeInTheDocument();
    // Active channels selected; scheduled date untouched
    expect(
      screen.getByRole("button", { name: /AloStudio IG/ }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: /AloStudio Threads/ }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(dateInput.value).toBe(originalDateValue);

    // Now click "Guardar como set", fill name, and submit
    fireEvent.click(
      screen.getByRole("button", { name: /Guardar como set/i }),
    );
    fireEvent.change(screen.getByLabelText(/Nombre del set/i), {
      target: { value: "Set Viernes" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar set" }));

    await waitFor(() => expect(savedSetBody).not.toBeNull());
    expect(savedSetBody).toEqual({
      name: "Set Viernes",
      content: "Texto del set listo para publicar",
      media: [{ media_id: 102 }],
      targets: [
        { channel_id: 10, settings: { post_type: "reels" } },
        {
          channel_id: 20,
          content_override: "Versión corta en Threads",
        },
      ],
    });
  });
});
