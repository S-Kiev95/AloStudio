import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AnalyticsChannel, Channel } from "@/lib/api/publications";

import { ChannelInsights } from "./channel-insights";
import { formatDurationMs } from "./publication-detail-dialog";

const CHANNEL: Channel = {
  id: 10,
  network: "instagram",
  name: "AloStudio IG",
  username: "alostudio",
  avatar_url: null,
  status: "active",
  status_message: null,
  inbox_id: 3,
};

function entry(extra: Partial<AnalyticsChannel>): AnalyticsChannel {
  return {
    channel: CHANNEL,
    posts: 2,
    metrics: {},
    followers: 400,
    followers_change: 4,
    series: [],
    ...extra,
  };
}

describe("ChannelInsights", () => {
  it("muestra la actividad, los desgloses y el público por dimensión", () => {
    render(
      <ChannelInsights
        entry={entry({
          activity: { accounts_engaged: 45, follows: 12, unfollows: 3 },
          breakdowns: {
            views_by_surface: { reels: 500, stories: 120 },
            profile_taps_by_button: { call: 4 },
          },
          audience: {
            followers: {
              country: { UY: 300, AR: 100 },
              gender: { F: 250, M: 170 },
            },
          },
        })}
      />,
    );

    expect(screen.getByText("Actividad de la cuenta")).toBeInTheDocument();
    expect(screen.getByText("Cuentas que interactuaron")).toBeInTheDocument();
    expect(screen.getByText("45")).toBeInTheDocument();
    expect(screen.getByText("Seguidores ganados")).toBeInTheDocument();
    expect(screen.getByText("Reels")).toBeInTheDocument();
    expect(screen.getByText("Llamar")).toBeInTheDocument();
    // Countries by name, the biggest first.
    expect(screen.getByText("Uruguay")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Género" }));
    expect(screen.getByText("Mujeres")).toBeInTheDocument();
  });

  it("avisa cuando Instagram todavía no da el público", () => {
    render(<ChannelInsights entry={entry({ activity: { follows: 1 }, audience: {} })} />);
    expect(
      screen.getByText("Instagram muestra el público desde los 100 seguidores."),
    ).toBeInTheDocument();
  });

  it("no muestra nada para una red que no informa estas cifras", () => {
    const { container } = render(<ChannelInsights entry={entry({})} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("formatea duraciones en milisegundos", () => {
    expect(formatDurationMs(7300, "es-UY")).toBe("7,3 s");
    expect(formatDurationMs(250_000, "es-UY")).toBe("4 min 10 s");
    expect(formatDurationMs(7_500_000, "es-UY")).toBe("2 h 5 min");
  });
});
