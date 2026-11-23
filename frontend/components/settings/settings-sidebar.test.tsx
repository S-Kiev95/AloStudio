import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SETTINGS_GROUP_ORDER, SETTINGS_ITEMS, SettingsSidebar } from "./settings-sidebar";

const push = vi.fn();
let pathname = "/accounts/1/settings/inboxes";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push }),
}));

beforeEach(() => {
  pathname = "/accounts/1/settings/inboxes";
  push.mockClear();
});

describe("SettingsSidebar agrupado y responsive", () => {
  it("organiza los 29 ajustes en los 6 grupos temáticos y marca el activo", () => {
    render(<SettingsSidebar accountId="1" />);

    expect(SETTINGS_ITEMS).toHaveLength(29);
    expect(SETTINGS_GROUP_ORDER).toHaveLength(6);

    expect(screen.getByText("Cuenta y equipo")).toBeInTheDocument();
    expect(screen.getByText("Canales y bandeja")).toBeInTheDocument();
    expect(screen.getByText("Automatización e IA")).toBeInTheDocument();
    expect(screen.getByText("CRM y ventas")).toBeInTheDocument();
    expect(screen.getByText("Publicación")).toBeInTheDocument();
    expect(screen.getByText("Integraciones y sistema")).toBeInTheDocument();

    expect(
      screen.getByRole("link", { name: "Bandejas de entrada" }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("filtra ajustes sin distinguir tildes ni mayúsculas y muestra estado vacío", () => {
    render(<SettingsSidebar accountId="1" />);
    const search = screen.getByRole("searchbox", { name: "Buscar ajuste…" });

    fireEvent.change(search, { target: { value: "automatizacion" } });
    expect(
      screen.getByRole("link", { name: "Automatización" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Bandejas de entrada" }),
    ).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: "zzzz-no-existe" } });
    expect(
      screen.getByText("No hay ajustes que coincidan."),
    ).toBeInTheDocument();
  });

  it("ofrece un selector agrupado en celular que navega a la sección elegida", () => {
    render(<SettingsSidebar accountId="1" />);
    const select = screen.getByRole("combobox", { name: "Sección de ajustes" });
    expect(select).toHaveValue("inboxes");

    fireEvent.change(select, { target: { value: "webhooks" } });
    expect(push).toHaveBeenCalledWith("/accounts/1/settings/webhooks");
  });
});
