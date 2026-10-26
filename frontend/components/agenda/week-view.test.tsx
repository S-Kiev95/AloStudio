import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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

import type { Appointment } from "@/lib/api/appointments";

import { AgendaView } from "./agenda-view";
import { addDaysLocal, startOfWeekMonday } from "./week-utils";
import { WeekView } from "./week-view";

function makeAppointment(
  overrides: Partial<Appointment> & { id: number; starts_at: string },
): Appointment {
  return {
    account_id: 1,
    contact_id: 10,
    product_id: null,
    title: `Cita #${overrides.id}`,
    description: null,
    ends_at: null,
    status: "scheduled",
    notes: null,
    created_by_id: 1,
    created_at: "2026-10-19T12:00:00Z",
    updated_at: "2026-10-19T12:00:00Z",
    contact: {
      id: 10,
      name: "Ana Lovelace",
      email: "ana@example.com",
      phone_number: "+59899111111",
    },
    product: null,
    ...overrides,
  };
}

let lastAppointmentsUrl: URL | null = null;

const server = setupServer(
  http.get("*/appointments", ({ request }) => {
    const url = new URL(request.url);
    lastAppointmentsUrl = url;
    const monday = startOfWeekMonday(new Date());
    const wednesdayMorning = new Date(
      monday.getFullYear(),
      monday.getMonth(),
      monday.getDate() + 2,
      10,
      30,
      0,
      0,
    );
    const items = [
      makeAppointment({
        id: 101,
        title: "Consulta de control",
        starts_at: wednesdayMorning.toISOString(),
        status: "confirmed",
        product: {
          id: 5,
          name: "Sesión integral",
          price: 1200,
          currency: "UYU",
        },
      }),
    ];
    const statusFilter = url.searchParams.get("status");
    const filtered = statusFilter
      ? items.filter((a) => a.status === statusFilter)
      : items;
    return HttpResponse.json(filtered);
  }),
  http.get("*/contacts", () =>
    HttpResponse.json({ meta: { count: 0, current_page: 1 }, payload: [] }),
  ),
  http.get("*/products", () => HttpResponse.json([])),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  lastAppointmentsUrl = null;
});
afterAll(() => server.close());

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("WeekView", () => {
  // Monday 2026-10-19 in local browser timezone
  const weekMonday = new Date(2026, 9, 19, 0, 0, 0, 0);
  const wednesdayToday = addDaysLocal(weekMonday, 2); // Miércoles 21

  it("renders Monday-to-Sunday columns and groups appointments by local day in chronological order", () => {
    const mondayAfternoon = new Date(2026, 9, 19, 15, 0, 0, 0).toISOString();
    const mondayMorning = new Date(2026, 9, 19, 9, 0, 0, 0).toISOString();
    const wednesdayNoon = new Date(2026, 9, 21, 12, 0, 0, 0).toISOString();
    const sundayMorning = new Date(2026, 9, 25, 11, 0, 0, 0).toISOString();
    const nextWeekMonday = new Date(2026, 9, 26, 10, 0, 0, 0).toISOString();

    const appointments: Appointment[] = [
      makeAppointment({
        id: 2,
        title: "Turno tarde lunes",
        starts_at: mondayAfternoon,
        status: "confirmed",
      }),
      makeAppointment({
        id: 1,
        title: "Turno mañana lunes",
        starts_at: mondayMorning,
        status: "scheduled",
        product: {
          id: 7,
          name: "Limpieza facial",
          price: 950,
          currency: "UYU",
        },
      }),
      makeAppointment({
        id: 3,
        title: "Seguimiento miércoles",
        starts_at: wednesdayNoon,
        status: "done",
        contact: {
          id: 11,
          name: null,
          email: null,
          phone_number: "+59899333444",
        },
      }),
      makeAppointment({
        id: 4,
        title: "Guardia domingo",
        starts_at: sundayMorning,
        status: "cancelled",
      }),
      makeAppointment({
        id: 5,
        title: "Fuera de esta semana",
        starts_at: nextWeekMonday,
      }),
    ];

    render(
      <WeekView
        weekStart={weekMonday}
        today={wednesdayToday}
        appointments={appointments}
        onEdit={vi.fn()}
        onStatusChange={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const grid = screen.getByTestId("agenda-week-grid");
    const sections = within(grid).getAllByRole("region");
    expect(sections).toHaveLength(7);

    expect(sections.map((s) => s.getAttribute("aria-label"))).toEqual([
      "Lunes 19",
      "Martes 20",
      "Miércoles 21",
      "Jueves 22",
      "Viernes 23",
      "Sábado 24",
      "Domingo 25",
    ]);

    // Monday has both appointments sorted chronologically (09:00 before 15:00)
    const mondayCards = within(sections[0]).getAllByRole("article");
    expect(mondayCards).toHaveLength(2);
    expect(within(mondayCards[0]).getByText("Turno mañana lunes")).toBeInTheDocument();
    expect(within(mondayCards[0]).getByText("Limpieza facial")).toBeInTheDocument();
    expect(
      within(mondayCards[0]).getByText("Programada", { selector: "span" }),
    ).toBeInTheDocument();
    expect(within(mondayCards[1]).getByText("Turno tarde lunes")).toBeInTheDocument();
    expect(
      within(mondayCards[1]).getByText("Confirmada", { selector: "span" }),
    ).toBeInTheDocument();

    // Tuesday is empty
    expect(within(sections[1]).getByText("Sin citas")).toBeInTheDocument();

    // Wednesday is marked as "Hoy" and falls back to phone number when contact name is null
    expect(within(sections[2]).getByText("Hoy")).toBeInTheDocument();
    expect(within(sections[2]).getByText("Seguimiento miércoles")).toBeInTheDocument();
    expect(within(sections[2]).getByText("+59899333444")).toBeInTheDocument();
    expect(
      within(sections[2]).getByText("Realizada", { selector: "span" }),
    ).toBeInTheDocument();

    // Sunday has its appointment; next week's appointment is excluded
    expect(within(sections[6]).getByText("Guardia domingo")).toBeInTheDocument();
    expect(
      within(sections[6]).getByText("Cancelada", { selector: "span" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Fuera de esta semana")).not.toBeInTheDocument();
  });

  it("invokes callbacks when changing status, editing, or deleting an appointment", () => {
    const onEdit = vi.fn();
    const onStatusChange = vi.fn();
    const onDelete = vi.fn();

    const appt = makeAppointment({
      id: 42,
      title: "Revisión mensual",
      starts_at: new Date(2026, 9, 19, 10, 0, 0, 0).toISOString(),
      status: "scheduled",
    });

    render(
      <WeekView
        weekStart={weekMonday}
        today={wednesdayToday}
        appointments={[appt]}
        onEdit={onEdit}
        onStatusChange={onStatusChange}
        onDelete={onDelete}
      />,
    );

    fireEvent.change(screen.getByLabelText("Estado de Revisión mensual"), {
      target: { value: "confirmed" },
    });
    expect(onStatusChange).toHaveBeenCalledWith(appt, "confirmed");

    fireEvent.click(screen.getByRole("button", { name: "Editar Revisión mensual" }));
    expect(onEdit).toHaveBeenCalledWith(appt);

    fireEvent.click(screen.getByRole("button", { name: "Eliminar Revisión mensual" }));
    expect(onDelete).toHaveBeenCalledWith(appt);
  });
});

describe("AgendaView", () => {
  it("loads the current week in weekly view, navigates weeks, and filters by status", async () => {
    renderWithQuery(<AgendaView accountId="1" />);

    expect(await screen.findByText("Consulta de control")).toBeInTheDocument();
    expect(screen.getByText("Sesión integral")).toBeInTheDocument();
    expect(lastAppointmentsUrl?.searchParams.get("from")).toBeTruthy();
    expect(lastAppointmentsUrl?.searchParams.get("to")).toBeTruthy();

    const initialFrom = lastAppointmentsUrl?.searchParams.get("from");
    fireEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
    await waitFor(() =>
      expect(lastAppointmentsUrl?.searchParams.get("from")).not.toBe(initialFrom),
    );

    fireEvent.click(screen.getByRole("button", { name: "Programadas" }));
    await waitFor(() =>
      expect(lastAppointmentsUrl?.searchParams.get("status")).toBe("scheduled"),
    );
  });
});
