import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

import { ProfileView } from "./profile-view";

// The avatar picker presigns + PUTs the file through the uploads helper;
// stub it so the test doesn't hit MinIO.
vi.mock("@/lib/api/uploads", () => ({
  uploadAttachment: vi.fn(async () => ({
    external_url: "https://cdn.example.com/a.png",
    file_type: "image",
  })),
}));

let putBody: unknown = null;
let currentAvatar: string | null = null;

function profilePayload() {
  return {
    data: {
      id: 1,
      name: "Me",
      email: "me@example.com",
      account_id: 7,
      accounts: [{ id: 7, name: "WS" }],
      avatar_url: currentAvatar,
      custom_attributes: {},
    },
  };
}

const server = setupServer(
  http.get("*/api/v1/profile", () => HttpResponse.json(profilePayload())),
  http.put("*/api/v1/profile", async ({ request }) => {
    putBody = await request.json();
    const b = putBody as { profile?: { avatar_url?: string } };
    if (b.profile && "avatar_url" in b.profile) {
      currentAvatar = b.profile.avatar_url || null;
    }
    return HttpResponse.json(profilePayload());
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  putBody = null;
  currentAvatar = null;
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ProfileView avatar", () => {
  it("uploads a picked image and PUTs the resulting URL", async () => {
    wrap(<ProfileView />);
    // Form hydrated once the profile loads.
    await screen.findByDisplayValue("Me");

    const input = screen.getByLabelText("Subir foto de perfil");
    const file = new File(["x"], "me.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() =>
      expect(putBody).toEqual({
        profile: { avatar_url: "https://cdn.example.com/a.png" },
      }),
    );
    // The uploaded avatar renders.
    const img = (await screen.findByAltText(
      "Foto de perfil",
    )) as HTMLImageElement;
    expect(img.src).toContain("https://cdn.example.com/a.png");
  });
});
