import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { ConversationFilters } from "./conversation-filters";

const server = setupServer(
  http.get("*/agents", () => HttpResponse.json([{ id: 7, name: "Ana" }])),
  http.get("*/inboxes", () => HttpResponse.json({ payload: [] })),
  http.get("*/teams", () => HttpResponse.json([])),
  http.get("*/labels", () => HttpResponse.json({ payload: [] })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const noop = () => {};

describe("ConversationFilters", () => {
  it("builds an equal_to condition from the default row", () => {
    const onApply = vi.fn();
    wrap(
      <ConversationFilters
        accountId="1"
        initial={[]}
        initialMatch="AND"
        onApply={onApply}
        onClear={noop}
        onCancel={noop}
        onSaveView={noop}
      />,
    );

    fireEvent.change(screen.getByLabelText("Valor"), {
      target: { value: "open" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(onApply).toHaveBeenCalledWith(
      [
        {
          attribute_key: "status",
          filter_operator: "equal_to",
          values: ["open"],
          query_operator: "AND",
        },
      ],
      "AND",
    );
  });

  it("omits the value for is_present operators", () => {
    const onApply = vi.fn();
    wrap(
      <ConversationFilters
        accountId="1"
        initial={[]}
        initialMatch="AND"
        onApply={onApply}
        onClear={noop}
        onCancel={noop}
        onSaveView={noop}
      />,
    );

    fireEvent.change(screen.getByLabelText("Atributo"), {
      target: { value: "assignee_id" },
    });
    fireEvent.change(screen.getByLabelText("Operador"), {
      target: { value: "is_present" },
    });
    // The value control disappears for valueless operators.
    expect(screen.queryByLabelText("Valor")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
    expect(onApply).toHaveBeenCalledWith(
      [
        {
          attribute_key: "assignee_id",
          filter_operator: "is_present",
          values: [],
          query_operator: "AND",
        },
      ],
      "AND",
    );
  });

  it("saves the current filter as a named view", () => {
    const onSaveView = vi.fn();
    wrap(
      <ConversationFilters
        accountId="1"
        initial={[]}
        initialMatch="AND"
        onApply={noop}
        onClear={noop}
        onCancel={noop}
        onSaveView={onSaveView}
      />,
    );

    fireEvent.change(screen.getByLabelText("Valor"), {
      target: { value: "open" },
    });
    fireEvent.change(screen.getByLabelText("Nombre de la vista"), {
      target: { value: "Abiertas" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar vista" }));

    expect(onSaveView).toHaveBeenCalledWith(
      "Abiertas",
      [
        {
          attribute_key: "status",
          filter_operator: "equal_to",
          values: ["open"],
          query_operator: "AND",
        },
      ],
      "AND",
    );
  });
});
