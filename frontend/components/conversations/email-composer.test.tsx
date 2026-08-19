import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { EmailComposer } from "./email-composer";

let sent: Record<string, unknown> | null = null;

const server = setupServer(
  http.post("*/messages", async ({ request }) => {
    sent = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: 1 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  sent = null;
  server.resetHandlers();
});
afterAll(() => server.close());

function renderComposer(replyTo: string | null = "alice@externo.com") {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <EmailComposer accountId="1" displayId={7} replyTo={replyTo} />
    </QueryClientProvider>,
  );
}

const body = () => screen.getByLabelText("Tu respuesta");
const sendBtn = () => screen.getByRole("button", { name: /Enviar/ });

describe("EmailComposer", () => {
  it("says who the reply goes to", () => {
    renderComposer();
    expect(screen.getByText("alice@externo.com")).toBeInTheDocument();
  });

  it("sends the reply", async () => {
    renderComposer();
    fireEvent.change(body(), { target: { value: "Ya lo revisamos." } });
    fireEvent.click(sendBtn());

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent!.content).toBe("Ya lo revisamos.");
    expect(sent!.message_type).toBe("outgoing");
  });

  it("copies other people when asked", async () => {
    // The thing a chat composer has no concept of.
    renderComposer();
    fireEvent.click(screen.getByRole("button", { name: "CC / CCO" }));
    fireEvent.change(screen.getByLabelText("CC"), {
      target: { value: "jefe@externo.com" },
    });
    fireEvent.change(screen.getByLabelText("CCO"), {
      target: { value: "archivo@interno.com" },
    });
    fireEvent.change(body(), { target: { value: "Copiando al equipo." } });
    fireEvent.click(sendBtn());

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent!.cc_emails).toBe("jefe@externo.com");
    expect(sent!.bcc_emails).toBe("archivo@interno.com");
  });

  it("keeps the copy fields out of the way until they are wanted", () => {
    renderComposer();
    expect(screen.queryByLabelText("CC")).not.toBeInTheDocument();
  });

  it("omits empty copy fields rather than sending blanks", async () => {
    renderComposer();
    fireEvent.change(body(), { target: { value: "Sin copias." } });
    fireEvent.click(sendBtn());

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent!.cc_emails).toBeUndefined();
    expect(sent!.bcc_emails).toBeUndefined();
  });

  it("will not send an empty reply", () => {
    renderComposer();
    expect(sendBtn()).toBeDisabled();
  });

  it("clears itself after sending", async () => {
    renderComposer();
    fireEvent.change(body(), { target: { value: "Listo." } });
    fireEvent.click(sendBtn());
    await waitFor(() => expect(body()).toHaveValue(""));
  });

  it("surfaces a rejected send instead of losing the text", async () => {
    server.use(
      http.post("*/messages", () =>
        HttpResponse.json({ message: "no anda" }, { status: 422 }),
      ),
    );
    renderComposer();
    fireEvent.change(body(), { target: { value: "Texto importante" } });
    fireEvent.click(sendBtn());

    expect(await screen.findByRole("alert")).toHaveTextContent("no anda");
    // The reply survives the failure — retyping it is the worst outcome.
    expect(body()).toHaveValue("Texto importante");
  });
});
