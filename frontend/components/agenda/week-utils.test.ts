import { describe, expect, it } from "vitest";

import { describeScheduledFor } from "./week-utils";

describe("describeScheduledFor", () => {
  const now = new Date(2026, 10, 2, 1, 0); // lunes 2/11, 01:00

  it("spells out an early-morning time later today", () => {
    expect(describeScheduledFor("2026-11-02T02:00", now)).toEqual({
      text: "Se publica hoy, lunes 2/11, a las 02:00 de la madrugada (en 1 hora).",
      past: false,
    });
  });

  it("names tomorrow and the afternoon", () => {
    expect(describeScheduledFor("2026-11-03T14:30", now)?.text).toBe(
      "Se publica mañana, martes 3/11, a las 14:30 de la tarde (en 38 horas).",
    );
  });

  it("flags a time that already passed", () => {
    expect(describeScheduledFor("2026-11-02T00:30", now)).toEqual({
      text: "Esa hora ya pasó: hoy, lunes 2/11, a las 00:30 de la madrugada.",
      past: true,
    });
  });

  it("returns null for an empty value", () => {
    expect(describeScheduledFor("", now)).toBeNull();
  });
});
