import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Listbox, type ListboxOption } from "./listbox";

const LANG_OPTIONS: readonly ListboxOption[] = [
  { value: "es", label: "Español", lang: "es" },
  { value: "en", label: "English", lang: "en" },
  { value: "pt", label: "Português", lang: "pt" },
  { value: "fr", label: "Français", lang: "fr" },
  { value: "de", label: "Deutsch", lang: "de" },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Listbox", () => {
  it("exposes WAI-ARIA select-only combobox attributes and option lang tags", () => {
    const onChange = vi.fn();
    render(
      <Listbox
        id="lang"
        value="es"
        onChange={onChange}
        options={LANG_OPTIONS}
        aria-label="Idioma"
      />,
    );

    const trigger = screen.getByRole("combobox", { name: "Idioma" });
    expect(trigger).toHaveAttribute("aria-haspopup", "listbox");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveAttribute("aria-controls", "lang-listbox");
    expect(trigger).not.toHaveAttribute("aria-activedescendant");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const listbox = screen.getByRole("listbox", { name: "Idioma" });
    expect(listbox).toHaveAttribute("id", "lang-listbox");

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(5);
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    expect(options[0]).toHaveAttribute("lang", "es");
    expect(options[1]).toHaveAttribute("aria-selected", "false");
    expect(options[1]).toHaveAttribute("lang", "en");
    expect(trigger).toHaveAttribute(
      "aria-activedescendant",
      options[0]?.getAttribute("id"),
    );
  });

  it("opens with Enter, Space, and ArrowDown, navigates with arrows/Home/End, and selects with Enter", () => {
    const onChange = vi.fn();
    render(
      <Listbox
        value="es"
        onChange={onChange}
        options={LANG_OPTIONS}
        aria-label="Idioma"
      />,
    );

    const trigger = screen.getByRole("combobox", { name: "Idioma" });
    trigger.focus();

    // Open with ArrowDown
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    // Move down twice (es -> en -> pt)
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const ptOption = screen.getByRole("option", { name: "Português" });
    expect(trigger).toHaveAttribute(
      "aria-activedescendant",
      ptOption.getAttribute("id"),
    );

    // End jumps to last option (Deutsch)
    fireEvent.keyDown(trigger, { key: "End" });
    const deOption = screen.getByRole("option", { name: "Deutsch" });
    expect(trigger).toHaveAttribute(
      "aria-activedescendant",
      deOption.getAttribute("id"),
    );

    // ArrowUp moves to Français
    fireEvent.keyDown(trigger, { key: "ArrowUp" });
    const frOption = screen.getByRole("option", { name: "Français" });
    expect(trigger).toHaveAttribute(
      "aria-activedescendant",
      frOption.getAttribute("id"),
    );

    // Home jumps back to Español
    fireEvent.keyDown(trigger, { key: "Home" });
    const esOption = screen.getByRole("option", { name: "Español" });
    expect(trigger).toHaveAttribute(
      "aria-activedescendant",
      esOption.getAttribute("id"),
    );

    // Move to English and select with Enter
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith("en");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(document.activeElement).toBe(trigger);

    // Re-open with Space and close with Escape
    fireEvent.keyDown(trigger, { key: " " });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    // Re-open with Enter
    fireEvent.keyDown(trigger, { key: "Enter" });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });

  it("jumps to matching options when typing letters (typeahead)", () => {
    const onChange = vi.fn();
    render(
      <Listbox
        value="es"
        onChange={onChange}
        options={LANG_OPTIONS}
        aria-label="Idioma"
      />,
    );

    const trigger = screen.getByRole("combobox", { name: "Idioma" });
    trigger.focus();

    // Typing "p" while closed opens and jumps to Português
    fireEvent.keyDown(trigger, { key: "p" });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(trigger).toHaveAttribute(
      "aria-activedescendant",
      screen.getByRole("option", { name: "Português" }).getAttribute("id"),
    );

    // Typing "f" falls back to Français
    fireEvent.keyDown(trigger, { key: "f" });
    expect(trigger).toHaveAttribute(
      "aria-activedescendant",
      screen.getByRole("option", { name: "Français" }).getAttribute("id"),
    );

    fireEvent.keyDown(trigger, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("fr");
  });

  it("closes on Escape returning focus without changing value, on Tab, and on outside click", () => {
    const onChange = vi.fn();
    render(
      <div>
        <Listbox
          value="es"
          onChange={onChange}
          options={LANG_OPTIONS}
          aria-label="Idioma"
        />
        <button type="button">Afuera</button>
      </div>,
    );

    const trigger = screen.getByRole("combobox", { name: "Idioma" });
    const outside = screen.getByRole("button", { name: "Afuera" });

    // Escape closes and keeps focus on trigger
    fireEvent.click(trigger);
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(onChange).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(trigger);

    // Outside click closes without selecting
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    fireEvent.mouseDown(outside);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(onChange).not.toHaveBeenCalled();

    // Tab closes the menu
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(trigger, { key: "Tab" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("selects an option on click and skips disabled options on keyboard navigation", () => {
    const onChange = vi.fn();
    render(
      <Listbox
        value="a"
        onChange={onChange}
        options={[
          { value: "a", label: "Alpha" },
          { value: "b", label: "Beta", disabled: true },
          { value: "c", label: "Gamma" },
        ]}
        aria-label="Opciones"
      />,
    );

    const trigger = screen.getByRole("combobox", { name: "Opciones" });
    fireEvent.click(trigger);

    // Disabled option cannot be clicked
    const beta = screen.getByRole("option", { name: "Beta" });
    expect(beta).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(beta);
    expect(onChange).not.toHaveBeenCalled();
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    // ArrowDown skips Beta and lands on Gamma
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const gamma = screen.getByRole("option", { name: "Gamma" });
    expect(trigger).toHaveAttribute(
      "aria-activedescendant",
      gamma.getAttribute("id"),
    );

    // Clicking Gamma selects and closes
    fireEvent.click(gamma);
    expect(onChange).toHaveBeenCalledWith("c");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("flips above the trigger when there is not enough space below", () => {
    const onChange = vi.fn();
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 400,
    });
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      top: 350,
      bottom: 390,
      left: 20,
      right: 220,
      width: 200,
      height: 40,
      x: 20,
      y: 350,
      toJSON: () => ({}),
    });

    render(
      <Listbox
        value="es"
        onChange={onChange}
        options={LANG_OPTIONS}
        aria-label="Idioma"
      />,
    );

    fireEvent.click(screen.getByRole("combobox", { name: "Idioma" }));
    const listbox = screen.getByRole("listbox", { name: "Idioma" });
    expect(listbox.style.bottom).toBe("56px");
    expect(listbox.style.top).toBe("");
  });
});
