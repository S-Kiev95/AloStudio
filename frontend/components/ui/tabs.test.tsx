import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SegmentedControl } from "./segmented-control";
import { NavTabs, Tabs, TabsList, TabsTrigger } from "./tabs";

describe("Tabs", () => {
  it("marks the active tab with aria-selected and neon-tab-active", () => {
    const onChange = vi.fn();
    render(
      <Tabs value="all" onValueChange={onChange}>
        <TabsList aria-label="Filtro">
          <TabsTrigger value="all">Todas</TabsTrigger>
          <TabsTrigger value="unread">No leídas</TabsTrigger>
        </TabsList>
      </Tabs>,
    );

    const all = screen.getByRole("tab", { name: "Todas" });
    const unread = screen.getByRole("tab", { name: "No leídas" });
    expect(all).toHaveAttribute("aria-selected", "true");
    expect(all.className).toContain("neon-tab-active");
    expect(unread).toHaveAttribute("aria-selected", "false");

    fireEvent.click(unread);
    expect(onChange).toHaveBeenCalledWith("unread");
  });

  it("renders NavTabs links with aria-current on the active route and single-row mobile scroll", () => {
    render(
      <NavTabs
        ariaLabel="CRM"
        items={[
          { href: "/a", label: "Conexión", active: true },
          { href: "/b", label: "Publicaciones", active: false },
        ]}
      />,
    );
    const nav = screen.getByRole("navigation", { name: "CRM" });
    expect(nav.className).toContain("flex-nowrap");
    expect(nav.className).toContain("overflow-x-auto");
    expect(nav.className).toContain("sm:flex-wrap");
    expect(screen.getByRole("link", { name: "Conexión" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("link", { name: "Publicaciones" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("supports ArrowRight and ArrowLeft keyboard navigation in TabsList", () => {
    const onChange = vi.fn();
    render(
      <Tabs value="all" onValueChange={onChange}>
        <TabsList aria-label="Filtro">
          <TabsTrigger value="all">Todas</TabsTrigger>
          <TabsTrigger value="unread">No leídas</TabsTrigger>
        </TabsList>
      </Tabs>,
    );

    const all = screen.getByRole("tab", { name: "Todas" });
    all.focus();
    fireEvent.keyDown(all, { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("unread");
  });
});

describe("SegmentedControl", () => {
  it("switches active segment with Focused Glass and Lit Text (no halo)", () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        value="week"
        onValueChange={onChange}
        options={[
          { value: "week", label: "Semana" },
          { value: "list", label: "Lista" },
        ]}
      />,
    );

    const week = screen.getByRole("button", { name: "Semana" });
    const list = screen.getByRole("button", { name: "Lista" });
    expect(week).toHaveAttribute("aria-pressed", "true");
    expect(week.className).toContain("bg-focused");
    expect(week.className).toContain("text-lit");
    expect(list).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(list);
    expect(onChange).toHaveBeenCalledWith("list");
  });
});
