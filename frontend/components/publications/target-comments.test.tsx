import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { PublicationComment } from "@/lib/api/publications";

import { TargetComments } from "./target-comments";

const BASE = "*/api/v1/accounts/1/publications/21/targets/7/comments";

let comments: PublicationComment[] = [
  {
    id: "T1",
    author: "Ana",
    text: "¿Cuándo empieza?",
    published_at: "2026-11-26T18:00:00Z",
    like_count: 2,
    replies: [],
  },
];
let sent: unknown = null;

const server = setupServer(
  http.get(BASE, () => HttpResponse.json({ comments })),
  http.post(`${BASE}/T1/replies`, async ({ request }) => {
    sent = await request.json();
    comments = [
      {
        ...comments[0],
        replies: [
          {
            id: "R1",
            author: "Canal",
            text: "El lunes",
            published_at: null,
            like_count: 0,
            replies: [],
          },
        ],
      },
    ];
    return HttpResponse.json({ comments: [] });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderComments(canReply: boolean) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TargetComments accountId="1" publicationId={21} targetId={7} canReply={canReply} />
    </QueryClientProvider>,
  );
}

describe("TargetComments", () => {
  it("lee los comentarios al abrirlos y responde como el canal", async () => {
    renderComments(true);

    fireEvent.click(screen.getByRole("button", { name: "Ver comentarios" }));
    expect(await screen.findByText("¿Cuándo empieza?")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Responder" }));
    fireEvent.change(screen.getByLabelText("Escribí la respuesta del canal…"), {
      target: { value: "El lunes" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Responder" }).at(-1)!);

    await waitFor(() => expect(sent).toEqual({ text: "El lunes" }));
    expect(await screen.findByText("El lunes")).toBeVisible();
  });

  it("sin permiso de administrador no muestra Responder", async () => {
    renderComments(false);

    fireEvent.click(screen.getByRole("button", { name: "Ver comentarios" }));
    expect(await screen.findByText("¿Cuándo empieza?")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Responder" })).toBeNull();
  });

  it("muestra el aviso de YouTube cuando falla", async () => {
    server.use(
      http.get(BASE, () =>
        HttpResponse.json(
          { message: "Para ver y responder comentarios, volvé a conectar el canal de YouTube." },
          { status: 502 },
        ),
      ),
    );
    renderComments(true);

    fireEvent.click(screen.getByRole("button", { name: "Ver comentarios" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("volvé a conectar el canal");
  });
});
