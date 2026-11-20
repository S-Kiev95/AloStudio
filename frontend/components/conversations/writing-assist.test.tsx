import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { useState } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { I18nProvider } from "@/lib/i18n/provider";

import { WritingAssist } from "./writing-assist";

let enabled = true;
let asked: Array<Record<string, unknown>> = [];

const server = setupServer(
  http.get("*/writing_assist", () =>
    HttpResponse.json({
      enabled,
      actions: ["improve", "fix", "formal", "friendly", "shorter", "translate", "summarize"],
      languages: ["es", "en", "pt"],
      text_max: 4000,
    }),
  ),
  http.post("*/writing_assist", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    asked.push(body);
    const text =
      body.action === "summarize"
        ? "- Lucía quiere inglés de noche."
        : body.action === "translate"
          ? "Hi Lucía!"
          : "¡Hola, Lucía!";
    return HttpResponse.json({ text });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  enabled = true;
  asked = [];
});
afterAll(() => server.close());

/** Holds the draft the way the composer does. */
function Composer({ initial }: { initial: string }) {
  const [draft, setDraft] = useState(initial);
  const [note, setNote] = useState(false);
  return (
    <>
      <textarea aria-label="Borrador" value={draft} onChange={(e) => setDraft(e.target.value)} />
      <output aria-label="Modo">{note ? "nota" : "respuesta"}</output>
      <WritingAssist
        accountId="1"
        displayId={12}
        draft={draft}
        onDraft={(text, asNote) => {
          setDraft(text);
          if (asNote) setNote(true);
        }}
      />
    </>
  );
}

function renderComposer(initial = "hola lucia", locale?: "pt") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = <Composer initial={initial} />;
  render(
    <QueryClientProvider client={qc}>
      {locale ? <I18nProvider locale={locale}>{ui}</I18nProvider> : ui}
    </QueryClientProvider>,
  );
  return qc;
}

describe("WritingAssist", () => {
  it("shows nothing while the installation has it off", async () => {
    enabled = false;
    const qc = renderComposer();
    await waitFor(() =>
      expect(qc.getQueryState(["writingAssist", "1"])?.status).toBe("success"),
    );
    expect(screen.queryByRole("button", { name: "IA" })).not.toBeInTheDocument();
  });

  it("improves the draft and gives the old one back", async () => {
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "IA" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Mejorar el texto" }));

    const box = screen.getByLabelText("Borrador");
    await waitFor(() => expect(box).toHaveValue("¡Hola, Lucía!"));
    expect(asked).toEqual([{ action: "improve", text: "hola lucia" }]);
    expect(screen.getByLabelText("Modo")).toHaveTextContent("respuesta");

    fireEvent.click(screen.getByRole("button", { name: "Deshacer" }));
    expect(box).toHaveValue("hola lucia");
    expect(screen.queryByRole("button", { name: "Deshacer" })).not.toBeInTheDocument();
  });

  it("translates into the language picked", async () => {
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "IA" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Traducir a…" }));
    expect(screen.getByRole("menuitem", { name: "Português" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: "English" }));

    await waitFor(() => expect(screen.getByLabelText("Borrador")).toHaveValue("Hi Lucía!"));
    expect(asked).toEqual([{ action: "translate", text: "hola lucia", language: "en" }]);
  });

  it("summarizes the conversation into a private note, in the interface's language", async () => {
    renderComposer("", "pt");
    fireEvent.click(await screen.findByRole("button", { name: "IA" }));
    // Nothing written: only the summary is on offer.
    expect(screen.getByRole("menuitem", { name: "Melhorar o texto" })).toBeDisabled();
    expect(screen.getByText("Escreva algo para melhorar ou traduzir.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: /Resumir a conversa/ }));

    await waitFor(() =>
      expect(screen.getByLabelText("Borrador")).toHaveValue("- Lucía quiere inglés de noche."),
    );
    expect(asked).toEqual([{ action: "summarize", conversation_id: 12, language: "pt" }]);
    expect(screen.getByLabelText("Modo")).toHaveTextContent("nota");
  });

  it("says why it could not", async () => {
    server.use(
      http.post("*/writing_assist", () =>
        HttpResponse.json(
          { message: "budget", code: "writing_assist.budget" },
          { status: 422 },
        ),
      ),
    );
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "IA" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Más corto" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Se llegó al tope de gasto en IA de este mes.",
    );
    expect(screen.getByLabelText("Borrador")).toHaveValue("hola lucia");
  });
});
