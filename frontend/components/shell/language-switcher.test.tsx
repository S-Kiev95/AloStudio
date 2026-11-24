import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/lib/i18n/provider";

import { LanguageSwitcher } from "./language-switcher";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

beforeEach(() => {
  refresh.mockClear();
  document.cookie = "alo_locale=; path=/; max-age=0";
});

describe("LanguageSwitcher", () => {
  it("lists all 7 languages with lang attributes and switches locale on click", () => {
    render(
      <I18nProvider locale="es">
        <LanguageSwitcher />
      </I18nProvider>,
    );

    const trigger = screen.getByRole("combobox", { name: "Idioma" });
    expect(trigger).toHaveTextContent("Español");

    fireEvent.click(trigger);

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(7);
    expect(screen.getByRole("option", { name: "日本語" })).toHaveAttribute(
      "lang",
      "ja",
    );
    expect(screen.getByRole("option", { name: "한국어" })).toHaveAttribute(
      "lang",
      "ko",
    );

    fireEvent.click(screen.getByRole("option", { name: "English" }));

    expect(document.cookie).toContain("alo_locale=en");
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("switches language via keyboard navigation", () => {
    render(
      <I18nProvider locale="es">
        <LanguageSwitcher />
      </I18nProvider>,
    );

    const trigger = screen.getByRole("combobox", { name: "Idioma" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "Enter" });

    expect(document.cookie).toContain("alo_locale=pt");
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});
