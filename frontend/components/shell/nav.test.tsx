import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CrmTabs } from "@/components/crm/crm-tabs";

import { activeNavItemKey, NAV_ITEMS } from "./nav";
import { SidebarNav } from "./sidebar-nav";

let mockPathname = "/accounts/1/publications";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

describe("Navigation and CRM tabs", () => {
  it("lists main sidebar items in the expected order", () => {
    expect(NAV_ITEMS.map((i) => i.label)).toEqual([
      "Inicio",
      "Calendario",
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
});
