import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { PostReplyPicker } from "./post-reply-picker";

const SHIPPING = {
  id: 1,
  trigger: "hacen envíos?",
  reply: "Sí, a todo el país.",
  enabled: true,
  indexed: true,
  selected: false,
};
const PRICE = {
  id: 2,
  trigger: "cuánto sale?",
  reply: "20 dólares.",
  enabled: true,
  indexed: true,
  selected: true,
};

let sent: { reply_ids: number[] } | null = null;

function library(...rows: unknown[]) {
  return http.get("*/instagram_comment_replies", () =>
    HttpResponse.json(rows),
  );
}

const server = setupServer(
  library(SHIPPING, PRICE),
  http.put("*/comment_replies", async ({ request }) => {
    sent = (await request.json()) as { reply_ids: number[] };
    return HttpResponse.json({ post_id: 7, reply_ids: sent.reply_ids });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  sent = null;
  server.resetHandlers();
});
afterAll(() => server.close());

function renderPicker() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PostReplyPicker accountId="1" postId={7} />
    </QueryClientProvider>,
  );
}

const box = (name: RegExp) => screen.getByRole("checkbox", { name });

describe("PostReplyPicker", () => {
  it("shows the whole library, not only what is picked", async () => {
    // The unpicked ones are the point — you cannot add what is not listed.
    renderPicker();
    expect(await screen.findByText("hacen envíos?")).toBeInTheDocument();
    expect(screen.getByText("cuánto sale?")).toBeInTheDocument();
  });

  it("reflects what the publication already offers", async () => {
    renderPicker();
    await screen.findByText("hacen envíos?");
    expect(box(/cuánto sale/)).toHaveAttribute("aria-checked", "true");
    expect(box(/hacen envíos/)).toHaveAttribute("aria-checked", "false");
  });

  it("sends the resulting set, not the change", async () => {
    renderPicker();
    await screen.findByText("hacen envíos?");
    fireEvent.click(box(/hacen envíos/));
    fireEvent.click(screen.getByRole("button", { name: /Guardar selección/ }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect([...sent!.reply_ids].sort()).toEqual([1, 2]);
  });

  it("can clear a pick", async () => {
    renderPicker();
    await screen.findByText("hacen envíos?");
    fireEvent.click(box(/cuánto sale/));
    fireEvent.click(screen.getByRole("button", { name: /Guardar selección/ }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent!.reply_ids).toEqual([]);
  });

  it("says that picking none means all, which is easy to read backwards", async () => {
    server.use(library({ ...SHIPPING }, { ...PRICE, selected: false }));
    renderPicker();
    expect(await screen.findByText(/puede usar las 2/)).toBeInTheDocument();
  });

  it("counts what is picked once something is", async () => {
    renderPicker();
    expect(await screen.findByText(/usa 1 de 2/)).toBeInTheDocument();
  });

  it("offers to save only after something changed", async () => {
    renderPicker();
    await screen.findByText("hacen envíos?");
    expect(
      screen.queryByRole("button", { name: /Guardar selección/ }),
    ).not.toBeInTheDocument();

    fireEvent.click(box(/hacen envíos/));
    expect(
      screen.getByRole("button", { name: /Guardar selección/ }),
    ).toBeInTheDocument();
  });

  it("discards an edit without sending it", async () => {
    renderPicker();
    await screen.findByText("hacen envíos?");
    fireEvent.click(box(/hacen envíos/));
    fireEvent.click(screen.getByRole("button", { name: /Descartar/ }));

    expect(box(/hacen envíos/)).toHaveAttribute("aria-checked", "false");
    expect(sent).toBeNull();
  });

  it("warns that picking an unindexed answer changes nothing", async () => {
    server.use(library({ ...SHIPPING, indexed: false }));
    renderPicker();
    expect(
      await screen.findByText(/no se va a usar aunque la elijas/),
    ).toBeInTheDocument();
  });

  it("points at where answers are written when there are none", async () => {
    server.use(library());
    renderPicker();
    expect(
      await screen.findByText(/Todavía no cargaste respuestas preparadas/),
    ).toBeInTheDocument();
  });

  it("surfaces a rejected save instead of failing quietly", async () => {
    server.use(
      http.put("*/comment_replies", () =>
        HttpResponse.json({ message: "nope" }, { status: 422 }),
      ),
    );
    renderPicker();
    await screen.findByText("hacen envíos?");
    fireEvent.click(box(/hacen envíos/));
    fireEvent.click(screen.getByRole("button", { name: /Guardar selección/ }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
