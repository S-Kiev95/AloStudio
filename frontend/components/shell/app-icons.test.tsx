import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  type AppIconComponent,
  type IconAnimate,
  AgentIcon,
  BarsIcon,
  BookIcon,
  CalendarIcon,
  ClockIcon,
  HomeIcon,
  HourglassIcon,
  InboxIcon,
  InstagramNavIcon,
  MediaIcon,
  MegaphoneIcon,
  MessagesIcon,
  PeopleIcon,
  SidebarCollapseIcon,
  SidebarExpandIcon,
  StatsIcon,
  UnassignedIcon,
  WhatsappNavIcon,
} from "./app-icons";

const ALL_ICONS: { name: string; component: AppIconComponent }[] = [
  { name: "home", component: HomeIcon },
  { name: "calendar", component: CalendarIcon },
  { name: "agent", component: AgentIcon },
  { name: "stats", component: StatsIcon },
  { name: "media", component: MediaIcon },
  { name: "inbox", component: InboxIcon },
  { name: "people", component: PeopleIcon },
  { name: "book", component: BookIcon },
  { name: "megaphone", component: MegaphoneIcon },
  { name: "bars", component: BarsIcon },
  { name: "clock", component: ClockIcon },
  { name: "unassigned", component: UnassignedIcon },
  { name: "hourglass", component: HourglassIcon },
  { name: "messages", component: MessagesIcon },
  { name: "instagram", component: InstagramNavIcon },
  { name: "whatsapp", component: WhatsappNavIcon },
  { name: "sidebar-collapse", component: SidebarCollapseIcon },
  { name: "sidebar-expand", component: SidebarExpandIcon },
];

describe("app-icons — set de íconos animados", () => {
  it.each(ALL_ICONS)(
    "renderiza $name con clases base y modo hover por defecto",
    ({ name, component: Icon }) => {
      const { container } = render(<Icon className="h-5 w-5" aria-hidden />);
      const svg = container.querySelector("svg");
      expect(svg).not.toBeNull();
      expect(svg).toHaveAttribute("viewBox", "0 0 24 24");
      expect(svg).toHaveAttribute("data-icon-name", name);
      expect(svg).toHaveAttribute("data-icon-animate", "hover");
      expect(svg).toHaveClass("app-icon", `app-icon-${name}`, "app-icon-hover", "h-5", "w-5");
    },
  );

  it.each<IconAnimate>(["loop", "hover", "none"])(
    "aplica las clases y atributo correctos para animate=%s",
    (mode) => {
      for (const { name, component: Icon } of ALL_ICONS) {
        const { container, unmount } = render(<Icon animate={mode} aria-hidden />);
        const svg = container.querySelector("svg");
        expect(svg).toHaveAttribute("data-icon-animate", mode);
        expect(svg).toHaveClass("app-icon", `app-icon-${name}`, `app-icon-${mode}`);
        unmount();
      }
    },
  );

  it("dibuja la arena del reloj de arena con clipPaths únicos por instancia", () => {
    const { container } = render(
      <>
        <HourglassIcon animate="loop" aria-hidden />
        <HourglassIcon animate="hover" aria-hidden />
      </>,
    );

    const svgs = container.querySelectorAll("svg[data-icon-name='hourglass']");
    expect(svgs).toHaveLength(2);
    expect(svgs[0]).toHaveClass("app-icon-loop");
    expect(svgs[1]).toHaveClass("app-icon-hover");

    const clipIds = Array.from(container.querySelectorAll("clipPath")).map((el) =>
      el.getAttribute("id"),
    );
    expect(clipIds).toHaveLength(4);
    expect(new Set(clipIds).size).toBe(4);
    expect(container.querySelectorAll(".app-icon-hg-sand-top")).toHaveLength(2);
    expect(container.querySelectorAll(".app-icon-hg-sand-bottom")).toHaveLength(2);
    expect(container.querySelectorAll(".app-icon-hg-stream")).toHaveLength(2);
  });

  it("separa las agujas minutero y horario en ClockIcon", () => {
    const { container } = render(<ClockIcon animate="loop" aria-hidden />);
    expect(container.querySelector(".app-icon-clock-min")).not.toBeNull();
    expect(container.querySelector(".app-icon-clock-hour")).not.toBeNull();
  });

  it("desactiva todas las animaciones de .app-icon bajo prefers-reduced-motion: reduce", () => {
    const css = readFileSync(
      resolve(__dirname, "../../app/globals.css"),
      "utf-8",
    );
    const reducedBlockStart = css.indexOf("@media (prefers-reduced-motion: reduce)");
    expect(reducedBlockStart).toBeGreaterThan(-1);
    const reducedBlock = css.slice(reducedBlockStart);
    expect(reducedBlock).toContain(".app-icon,");
    expect(reducedBlock).toContain(".app-icon *,");
    expect(reducedBlock).toContain("animation: none !important;");
    expect(css).toContain("transform-box: fill-box;");
  });
});
