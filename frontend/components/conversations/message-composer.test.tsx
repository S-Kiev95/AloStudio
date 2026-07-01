import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
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
