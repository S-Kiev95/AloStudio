import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CrmTabs } from "./crm-tabs";

let pathname = "/accounts/4/products";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

describe("CrmTabs", () => {
  it("renderiza las pestañas Contactos, Productos y Agenda sin alterar sus rutas y marca la activa", () => {
    pathname = "/accounts/4/products";
    render(<CrmTabs accountId="4" />);

    const contacts = screen.getByRole("link", { name: "Contactos" });
    const products = screen.getByRole("link", { name: "Productos" });
    const agenda = screen.getByRole("link", { name: "Agenda" });

    expect(contacts).toHaveAttribute("href", "/accounts/4/contacts");
    expect(products).toHaveAttribute("href", "/accounts/4/products");
    expect(agenda).toHaveAttribute("href", "/accounts/4/agenda");

    expect(products).toHaveAttribute("aria-current", "page");
    expect(contacts).not.toHaveAttribute("aria-current");
    expect(agenda).not.toHaveAttribute("aria-current");
  });
});
