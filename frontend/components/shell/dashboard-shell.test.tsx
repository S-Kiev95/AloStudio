import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardShell } from "./dashboard-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/accounts/1/conversations",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "dark", setTheme: vi.fn() }),
}));

vi.mock("@/lib/api/inboxes", () => ({
  useHasWhatsappInbox: () => false,
}));

vi.mock("@/lib/api/help-assistant", () => ({
  useHelpAssistant: () => ({ data: null }),
  useAskHelp: () => ({ mutate: vi.fn(), isPending: false }),
  useAllowFastHelp: () => ({ mutate: vi.fn(), isPending: false }),
  helpProblemKey: () => "helpAssistant.problems.failed",
}));

vi.mock("@/lib/api/notifications", () => ({
  NOTIFICATION_TYPE_LABELS: {},
  notificationHref: () => null,
  useUnreadCount: () => ({ data: 0 }),
  useNotifications: () => ({ data: { payload: [] }, isLoading: false }),
  useMarkNotificationRead: () => ({ mutate: vi.fn() }),
  useMarkAllNotificationsRead: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteNotification: () => ({ mutate: vi.fn() }),
}));

vi.mock("@/lib/realtime/use-cable", () => ({
  useCable: () => {},
}));

const PROFILE = {
  id: 1,
  name: "Sofía Costa",
  email: "sofia@ctc.edu.uy",
  availableName: "Sofía Costa",
  pubsubToken: null,
  activeAccountId: 1,
  locale: "es",
  accounts: [{ id: 1, name: "Instituto CTC", role: "administrator" }],
};

describe("DashboardShell — barra superior móvil y cajón", () => {
  it("mantiene el cartel neón sin recorte max-lg:truncate y cierra el cajón con Escape", () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <DashboardShell accountId="1" profile={PROFILE}>
          <div>Contenido</div>
        </DashboardShell>
      </QueryClientProvider>,
    );

    const heading = screen.getByRole("heading", { level: 1, name: "Bandeja" });
    expect(heading.className).not.toContain("max-lg:truncate");

    // Open mobile drawer and verify Escape closes it.
    fireEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    expect(
      screen.getAllByRole("button", { name: "Cerrar menú" }).length,
    ).toBeGreaterThan(0);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(
      screen.queryAllByRole("button", { name: "Cerrar menú" }),
    ).toHaveLength(0);
  });
});
