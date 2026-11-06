import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { describe, expect, it, vi } from "vitest";

import { MessageComposer } from "./message-composer";

vi.mock("@/lib/api/uploads", () => ({
  uploadAttachment: vi.fn(async (_accountId: string, file: File) => ({
    external_url: `http://store.test/${file.name}`,
    file_type: "file",
  })),
}));

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("MessageComposer attachments", () => {
  it("Enter envía y Shift+Enter deja escribir otra línea", async () => {
    const sent: unknown[] = [];
    const server = setupServer(
      http.get("*/canned_responses", () => HttpResponse.json([])),
      http.post("*/conversations/1/messages", async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json({ id: 1 });
      }),
    );
    server.listen({ onUnhandledRequest: "bypass" });
    try {
      wrap(<MessageComposer accountId="1" displayId={1} />);
      const box = screen.getByLabelText("Respuesta");
      fireEvent.change(box, { target: { value: "Hola" } });

      fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
      expect(sent).toEqual([]);

      fireEvent.keyDown(box, { key: "Enter" });
      await waitFor(() => expect(sent).toHaveLength(1));
    } finally {
      server.close();
    }
  });

  it("uploads several picked files and shows one chip per file", async () => {
    const { container } = wrap(
      <MessageComposer accountId="1" displayId={1} />,
    );
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;

    const f1 = new File(["a"], "uno.txt", { type: "text/plain" });
    const f2 = new File(["b"], "dos.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [f1, f2] } });

    expect(await screen.findByText("uno.txt")).toBeInTheDocument();
    expect(await screen.findByText("dos.pdf")).toBeInTheDocument();

    // Removing one leaves the other.
    fireEvent.click(screen.getByLabelText("Quitar uno.txt"));
    expect(screen.queryByText("uno.txt")).not.toBeInTheDocument();
    expect(screen.getByText("dos.pdf")).toBeInTheDocument();
  });
});
