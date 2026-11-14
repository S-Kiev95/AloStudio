import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ROLE_ADMINISTRATOR } from "@/lib/api/account";
import type { Message } from "@/lib/api/conversations";

import { CatalogPanel } from "./catalog-panel";
import { CommerceMessage, isCommerceMessage } from "./commerce-message";
import { ProductPicker } from "./product-picker";

vi.mock("next/navigation", () => ({
  useParams: () => ({ accountId: "1" }),
}));

let sent: Record<string, unknown> | null = null;
let linked = false;

const server = setupServer(
  http.get("*/api/v1/profile", () =>
    HttpResponse.json({
      data: {
        id: 1,
        name: "Admin",
        email: "admin@alostudio.test",
        accounts: [{ id: 1, name: "AloStudio", role: ROLE_ADMINISTRATOR }],
      },
    }),
  ),
  http.get("*/api/v1/accounts/1/whatsapp/catalog/products", () =>
    HttpResponse.json({
      catalog_id: "777",
      products: [
        { id: 1, name: "Excel", price: 1200, currency: "UYU", retailer_id: "alo-1" },
        { id: 2, name: "Inglés", price: 900, currency: "UYU", retailer_id: "alo-2" },
      ],
    }),
  ),
  http.post("*/api/v1/accounts/1/conversations/9/whatsapp/products", async ({ request }) => {
    sent = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: 50 });
  }),
  http.get("*/api/v1/accounts/1/inboxes/7/whatsapp/commerce", () =>
    HttpResponse.json({
      account_catalog_id: "777",
      linked_catalog_ids: linked ? ["777"] : [],
      catalog_linked: linked,
      is_catalog_visible: false,
      is_cart_enabled: true,
      products_ready: 2,
    }),
  ),
  http.post("*/api/v1/accounts/1/inboxes/7/whatsapp/commerce/link", () => {
    linked = true;
    return HttpResponse.json({
      account_catalog_id: "777",
      linked_catalog_ids: ["777"],
      catalog_linked: true,
      is_catalog_visible: false,
      is_cart_enabled: true,
      products_ready: 2,
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  sent = null;
  linked = false;
});
afterAll(() => server.close());

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const baseMessage = {
  id: 1,
  content: "texto",
  message_type: 0,
  content_type: "text",
  status: "sent",
  created_at: 1,
  private: false,
} as unknown as Message;

describe("catalogue on WhatsApp", () => {
  it("sends the picked products as a list with a title", async () => {
    const onClose = vi.fn();
    wrap(<ProductPicker accountId="1" displayId={9} onClose={onClose} />);
    fireEvent.click(await screen.findByLabelText("Excel"));
    fireEvent.click(screen.getByLabelText("Inglés"));
    expect(screen.getByText(/2 productos/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Título de la lista"), {
      target: { value: "Cursos de marzo" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Enviar/ }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(sent).toEqual({ product_ids: [1, 2], header: "Cursos de marzo" });
  });

  it("shows an order with its total and the opportunity it opened", () => {
    const order = {
      ...baseMessage,
      content_attributes: {
        whatsapp_order: {
          catalog_id: "777",
          items: [
            {
              retailer_id: "alo-1",
              product_id: 1,
              name: "Excel",
              quantity: 2,
              item_price: 1200,
              currency: "UYU",
            },
          ],
          total: 2400,
          currency: "UYU",
          note: "¿Hay cupo?",
          opportunity_id: 3,
        },
      },
    } as Message;
    expect(isCommerceMessage(order)).toBe(true);
    expect(isCommerceMessage(baseMessage)).toBe(false);
    render(<CommerceMessage message={order} />);
    expect(screen.getByText("2 × Excel")).toBeInTheDocument();
    expect(screen.getAllByText(/UYU 2\.400/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /oportunidad/ })).toHaveAttribute(
      "href",
      "/accounts/1/opportunities",
    );
  });

  it("links the catalogue to the number", async () => {
    wrap(<CatalogPanel accountId="1" inboxId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: /Conectar catálogo/ }));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /Conectar catálogo/ })).toBeNull(),
    );
    expect(screen.getByLabelText(/Carrito de compras/)).toBeChecked();
  });
});
