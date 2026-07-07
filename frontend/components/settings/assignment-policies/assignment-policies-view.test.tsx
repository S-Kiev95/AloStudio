import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
} from "vitest";

import { AssignmentPoliciesView } from "./assignment-policies-view";

const policies = [
  {
    id: 1,
    name: "Equilibrada",
    description: null,
    enabled: true,
    assignment_order: "round_robin",
    conversation_priority: "earliest_created",
    fair_distribution_limit: 100,
    fair_distribution_window: 3600,
  },
  {
    id: 2,
    name: "Espera larga",
    description: "prioriza la más vieja",
    enabled: false,
    assignment_order: "round_robin",
    conversation_priority: "longest_waiting",
    fair_distribution_limit: 5,
    fair_distribution_window: 1800,
  },
];

const created: unknown[] = [];

const server = setupServer(
  http.get("*/assignment_policies", () => HttpResponse.json(policies)),
  http.post("*/assignment_policies", async ({ request }) => {
    const body = await request.json();
    created.push(body);
    return HttpResponse.json({
      id: 3,
      name: "Nueva",
      description: null,
      enabled: true,
      assignment_order: "round_robin",
      conversation_priority: "earliest_created",
      fair_distribution_limit: 100,
      fair_distribution_window: 3600,
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  created.length = 0;
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("AssignmentPoliciesView", () => {
  it("lists policies with a priority + fair-distribution summary", async () => {
    wrap(<AssignmentPoliciesView accountId="1" />);
    expect(await screen.findByText("Equilibrada")).toBeInTheDocument();
    expect(screen.getByText(/La creada primero/)).toBeInTheDocument();
    expect(screen.getByText(/100 conv\. \/ 3600s/)).toBeInTheDocument();
    // A disabled policy carries the "Inactiva" badge.
    expect(screen.getByText("Inactiva")).toBeInTheDocument();
  });

  it("creates a policy, wrapping the body in assignment_policy", async () => {
    wrap(<AssignmentPoliciesView accountId="1" />);
    await screen.findByText("Equilibrada");

    fireEvent.click(screen.getByRole("button", { name: /Nueva política/i }));
    fireEvent.change(screen.getByLabelText(/Nombre/), {
      target: { value: "Round robin" },
    });
    fireEvent.change(screen.getByLabelText(/Prioridad de conversación/), {
      target: { value: "longest_waiting" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Crear política/i }),
    );

    await waitFor(() => expect(created).toHaveLength(1));
    expect(created[0]).toEqual({
      assignment_policy: {
        name: "Round robin",
        description: null,
        enabled: true,
        conversation_priority: "longest_waiting",
        fair_distribution_limit: 100,
        fair_distribution_window: 3600,
      },
    });
  });

  it("blocks submit when the fair-distribution limit is not positive", async () => {
    wrap(<AssignmentPoliciesView accountId="1" />);
    await screen.findByText("Equilibrada");

    fireEvent.click(screen.getByRole("button", { name: /Nueva política/i }));
    fireEvent.change(screen.getByLabelText(/Nombre/), {
      target: { value: "Bad" },
    });
    fireEvent.change(screen.getByLabelText(/Límite por agente/), {
      target: { value: "0" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Crear política/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /mayor que 0/,
    );
    expect(created).toHaveLength(0);
  });
});
