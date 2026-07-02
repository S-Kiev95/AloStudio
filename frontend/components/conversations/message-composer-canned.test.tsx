import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MessageComposer } from "./message-composer";

// The composer pulls the account's canned responses on mount; feed a
// fixed list so the "/" quick-insert has something to match.
vi.mock("@/lib/api/canned-responses", () => ({
  useCannedResponses: () => ({
    data: [
      { id: 1, short_code: "saludo", content: "Hola, ¿cómo puedo ayudarte?" },
      { id: 2, short_code: "despedida", content: "¡Que tengas un buen día!" },
    ],
  }),
}));

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("MessageComposer canned responses", () => {
  it("filters by the typed /short_code and inserts the content on click", () => {
    wrap(<MessageComposer accountId="1" displayId={1} />);
    const textarea = screen.getByLabelText("Respuesta") as HTMLTextAreaElement;

    // Typing "/sal" narrows the picker to the matching short_code.
    fireEvent.change(textarea, { target: { value: "/sal" } });
    expect(screen.getByText("/saludo")).toBeInTheDocument();
    expect(screen.queryByText("/despedida")).not.toBeInTheDocument();

    // Selecting it replaces the draft with the response body and closes
    // the picker (the content now has spaces, so "/token" no longer matches).
    fireEvent.click(screen.getByRole("button", { name: /saludo/i }));
    expect(textarea.value).toBe("Hola, ¿cómo puedo ayudarte?");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("shows every response when the draft is just '/'", () => {
    wrap(<MessageComposer accountId="1" displayId={1} />);
    const textarea = screen.getByLabelText("Respuesta");

    fireEvent.change(textarea, { target: { value: "/" } });
    expect(screen.getByText("/saludo")).toBeInTheDocument();
    expect(screen.getByText("/despedida")).toBeInTheDocument();
  });
});
