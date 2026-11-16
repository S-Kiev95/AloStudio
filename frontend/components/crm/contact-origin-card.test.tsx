import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { Contact } from "@/lib/api/contacts";

import { ContactOriginCard } from "./contact-origin-card";

let sent: unknown = null;
const server = setupServer(
  http.put("*/crm/contacts/7/origin", async ({ request }) => {
    sent = await request.json();
    return HttpResponse.json({ origin: null });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  sent = null;
});
afterAll(() => server.close());

const contact = (origin: Contact["origin"]): Contact => ({
  id: 7,
  name: "Lucía",
  email: null,
  phone_number: null,
  blocked: false,
  identifier: null,
  thumbnail: "",
  availability_status: "offline",
  additional_attributes: {},
  custom_attributes: {},
  origin,
});

function renderCard(c: Contact) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ContactOriginCard accountId="1" contact={c} />
    </QueryClientProvider>,
  );
}

describe("ContactOriginCard", () => {
  it("says which ad brought the person", () => {
    renderCard(
      contact({
        source: "ad",
        channel: "whatsapp",
        detail: "Inscripciones 2027",
        ad_id: "123",
        conversation_id: 4,
        at: 1_700_000_000,
      }),
    );
    expect(screen.getByText("Anuncio · WhatsApp")).toBeInTheDocument();
    expect(screen.getByText("Inscripciones 2027")).toBeInTheDocument();
  });

  it("sets an origin by hand", async () => {
    renderCard(contact(null));
    expect(screen.getByText("Todavía no se sabe cómo llegó.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Indicar origen" }));
    fireEvent.change(screen.getByLabelText("Cómo llegó"), { target: { value: "referral" } });
    fireEvent.change(screen.getByLabelText("Detalle"), { target: { value: "La recomendó Juan" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() =>
      expect(sent).toEqual({ source: "referral", channel: null, detail: "La recomendó Juan" }),
    );
  });
});
