import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CrmTabs } from "@/components/crm/crm-tabs";
import type { Profile } from "@/lib/auth/profile";

import {
  DashboardShell,
  SIDEBAR_COLLAPSED_STORAGE_KEY,
} from "./dashboard-shell";
import { activeNavItemKey, NAV_ITEMS } from "./nav";
import { SidebarNav } from "./sidebar-nav";

let mockPathname = "/accounts/1/publications";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/realtime/use-cable", () => ({
  useCable: () => {},
}));

vi.mock("./notification-bell", () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}));

const MOCK_PROFILE: Profile = {
  id: 1,
  name: "Ada Lovelace",
  availableName: "Ada Lovelace",
  email: "ada@example.com",
  pubsubToken: "tok",
  activeAccountId: 1,
  accounts: [{ id: 1, name: "AloStudio Demo", role: "administrator" }],
};

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("Navigation and CRM tabs", () => {
  it("lists main sidebar items in the expected order with Agente right after Calendario", () => {
    expect(NAV_ITEMS.map((i) => i.label)).toEqual([
      "Inicio",
      "Calendario",
      "Agente",
      "Estadísticas",
      "Medios",
      "Bandeja",
      "CRM",
      "Instagram",
      "Help Center",
      "Campañas",
      "Reportes",
      "Ajustes",
    ]);
  });

  it("renders Agente link and activates it on /agent and /agent/[threadId]", () => {
    expect(activeNavItemKey("/accounts/1/agent", "1")).toBe("agent");
    expect(activeNavItemKey("/accounts/1/agent/7", "1")).toBe("agent");

    mockPathname = "/accounts/1/agent/7";
    render(<SidebarNav accountId="1" />);
    const agentLink = screen.getByRole("link", { name: "Agente" });
    expect(agentLink).toHaveAttribute("href", "/accounts/1/agent");
    expect(agentLink).toHaveAttribute("aria-current", "page");
  });

  it("activates Medios and Estadísticas without marking Calendario", () => {
    expect(activeNavItemKey("/accounts/1/publications", "1")).toBe("calendar");
    expect(activeNavItemKey("/accounts/1/publications/media", "1")).toBe("media");
    expect(activeNavItemKey("/accounts/1/publications/analytics", "1")).toBe(
      "analytics",
    );

    mockPathname = "/accounts/1/publications/media";
    render(<SidebarNav accountId="1" />);
    expect(screen.getByRole("link", { name: "Medios" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("link", { name: "Calendario" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("activates CRM across Contactos, Productos and Agenda routes and renders CrmTabs", () => {
    expect(activeNavItemKey("/accounts/1/contacts", "1")).toBe("crm");
    expect(activeNavItemKey("/accounts/1/contacts/new", "1")).toBe("crm");
    expect(activeNavItemKey("/accounts/1/products", "1")).toBe("crm");
    expect(activeNavItemKey("/accounts/1/agenda", "1")).toBe("crm");

    mockPathname = "/accounts/1/agenda";
    render(<CrmTabs accountId="1" />);
    expect(screen.getByRole("link", { name: "Contactos" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(screen.getByRole("link", { name: "Productos" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(screen.getByRole("link", { name: "Agenda" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("colapsa y abre la barra lateral con el botón, cambia aria-expanded, mantiene nombres accesibles y recuerda en localStorage", () => {
    mockPathname = "/accounts/1/conversations";
    const { unmount } = render(
      <DashboardShell accountId="1" profile={MOCK_PROFILE}>
        <div>Contenido</div>
      </DashboardShell>,
    );

    const collapseBtn = screen.getByRole("button", {
      name: "Colapsar barra lateral",
    });
    expect(collapseBtn).toHaveAttribute("aria-expanded", "true");

    const wordmark = screen.getByRole("link", { name: "AloStudio" });
    expect(wordmark.querySelectorAll("span")).toHaveLength(9);

    fireEvent.click(collapseBtn);

    const expandBtn = screen.getByRole("button", {
      name: "Expandir barra lateral",
    });
    expect(expandBtn).toHaveAttribute("aria-expanded", "false");
    expect(
      window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY),
    ).toBe("1");

    // Muestra solo la "A" de AloStudio arriba
    const collapsedWordmark = screen.getByRole("link", { name: "AloStudio" });
    const letterSpans = collapsedWordmark.querySelectorAll("span");
    expect(letterSpans).toHaveLength(1);
    expect(letterSpans[0]).toHaveTextContent("A");

    // Todos los ítems del menú (incluido Ajustes) siguen accesibles con title y el activo se distingue
    const nav = screen.getByRole("navigation", { name: "Principal" });
    for (const item of NAV_ITEMS) {
      const link = within(nav).getByRole("link", { name: item.label });
      expect(link).toHaveAttribute("title", item.label);
      expect(link).toHaveTextContent("");
    }
    expect(
      within(nav).getByRole("link", { name: "Bandeja" }),
    ).toHaveAttribute("aria-current", "page");

    // Al desmontar y volver a montar recuerda el estado colapsado
    unmount();
    render(
      <DashboardShell accountId="1" profile={MOCK_PROFILE}>
        <div>Contenido</div>
      </DashboardShell>,
    );

    const rememberedExpandBtn = screen.getByRole("button", {
      name: "Expandir barra lateral",
    });
    expect(rememberedExpandBtn).toHaveAttribute("aria-expanded", "false");

    // Vuelve a abrir
    fireEvent.click(rememberedExpandBtn);
    const reopenedCollapseBtn = screen.getByRole("button", {
      name: "Colapsar barra lateral",
    });
    expect(reopenedCollapseBtn).toHaveAttribute("aria-expanded", "true");
    expect(
      window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY),
    ).toBe("0");
  });
});
