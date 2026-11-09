import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { describe, expect, it, vi } from "vitest";

import { usePendingMessages } from "@/lib/api/conversations";

import { PendingMessageBubble } from "./message-bubble";
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

function ChatWithPending() {
  const pending = usePendingMessages("1", 1);
  return (
    <>
      {pending.map((p) => (
        <PendingMessageBubble
          key={p.mutationId}
          accountId="1"
          displayId={1}
          pending={p}
        />
      ))}
      <MessageComposer accountId="1" displayId={1} />
    </>
  );
}

describe("MessageComposer instant send", () => {
  it("shows each message at once and sends them in order, one at a time", async () => {
    const sent: unknown[] = [];
    const answers: Array<() => void> = [];
    const server = setupServer(
      http.get("*/canned_responses", () => HttpResponse.json([])),
      http.post("*/conversations/1/messages", async ({ request }) => {
        sent.push(((await request.json()) as { content: string }).content);
        await new Promise<void>((resolve) => answers.push(resolve));
        return HttpResponse.json({ id: sent.length });
      }),
    );
    server.listen({ onUnhandledRequest: "bypass" });
    try {
      wrap(<ChatWithPending />);
      const box = screen.getByLabelText("Respuesta");
      for (const text of ["Hola", "Cómo estás"]) {
        fireEvent.change(box, { target: { value: text } });
        fireEvent.keyDown(box, { key: "Enter" });
        expect(box).toHaveValue("");
        expect(await screen.findByText(text)).toBeInTheDocument();
      }
      await waitFor(() => expect(sent).toEqual(["Hola"]));

      answers[0]();
      await waitFor(() => expect(sent).toEqual(["Hola", "Cómo estás"]));
      await waitFor(() => expect(screen.queryByText("Hola")).toBeNull());

      answers[1]();
      await waitFor(() => expect(screen.queryByText("Cómo estás")).toBeNull());
    } finally {
      server.close();
    }
  });

  it("keeps a failed message to retry or discard", async () => {
    let attempts = 0;
    const server = setupServer(
      http.get("*/canned_responses", () => HttpResponse.json([])),
      http.post("*/conversations/1/messages", () => {
        attempts += 1;
        return attempts === 1
          ? HttpResponse.json({ message: "Fuera de la ventana" }, { status: 422 })
          : HttpResponse.json({ id: 2 });
      }),
    );
    server.listen({ onUnhandledRequest: "bypass" });
    try {
      wrap(<ChatWithPending />);
      const box = screen.getByLabelText("Respuesta");
      fireEvent.change(box, { target: { value: "Hola" } });
      fireEvent.keyDown(box, { key: "Enter" });
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Fuera de la ventana",
      );

      fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
      await waitFor(() => expect(attempts).toBe(2));
      await waitFor(() => expect(screen.queryByText("Hola")).toBeNull());
    } finally {
      server.close();
    }
  });
});

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

  it("encuentra el botón Enviar fuera del cuadro de texto, abajo a la derecha en la fila de acciones, está deshabilitado sin texto y envía con texto", async () => {
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
      const sendBtn = screen.getByRole("button", { name: "Enviar" });
      const privateBtn = screen.getByRole("button", { name: "Nota privada" });

      expect(sendBtn).toBeDisabled();
      expect(sendBtn).toHaveAttribute("title", "Enviar");
      expect(sendBtn).toHaveTextContent("");
      expect(sendBtn).toHaveClass("rounded-full", "ml-auto");
      expect(box).not.toHaveClass("pr-12");
      expect(box).not.toHaveClass("py-[13px]");
      expect(privateBtn.parentElement).toContainElement(sendBtn);
      expect(privateBtn.parentElement).not.toContainElement(box);

      fireEvent.change(box, { target: { value: "Respuesta desde el botón" } });
      expect(sendBtn).not.toBeDisabled();

      fireEvent.click(sendBtn);
      await waitFor(() => expect(sent).toHaveLength(1));
      expect(box).toHaveValue("");
      expect(sendBtn).toBeDisabled();
    } finally {
      server.close();
    }
  });

  it("crece con líneas vacías (Shift+Enter) sin mostrar scroll hasta superar el alto máximo", () => {
    wrap(<MessageComposer accountId="1" displayId={1} />);
    const box = screen.getByLabelText("Respuesta") as HTMLTextAreaElement;

    let mockedScrollHeight = 60;
    Object.defineProperty(box, "scrollHeight", {
      configurable: true,
      get: () => mockedScrollHeight,
    });
    Object.defineProperty(box, "offsetHeight", {
      configurable: true,
      get: () => mockedScrollHeight + 2,
    });
    Object.defineProperty(box, "clientHeight", {
      configurable: true,
      get: () => mockedScrollHeight,
    });

    // 2 lines (Shift+Enter on empty): grows including 2px border, no scrollbar
    fireEvent.change(box, { target: { value: "\n" } });
    expect(box.style.height).toBe("62px");
    expect(box.style.overflowY).toBe("hidden");

    // 6 lines (140px scrollHeight + 2px border = 142px <= 144px): still no scrollbar
    mockedScrollHeight = 140;
    fireEvent.change(box, { target: { value: "\n\n\n\n\n" } });
    expect(box.style.height).toBe("142px");
    expect(box.style.overflowY).toBe("hidden");

    // 7 lines (160px scrollHeight + 2px border = 162px > 144px): caps at 144px and enables scroll
    mockedScrollHeight = 160;
    fireEvent.change(box, { target: { value: "\n\n\n\n\n\n" } });
    expect(box.style.height).toBe("144px");
    expect(box.style.overflowY).toBe("auto");
  });
});
