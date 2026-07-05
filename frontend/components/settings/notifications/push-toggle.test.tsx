import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock the push helpers so the component test never touches real browser
// push APIs (service worker / PushManager / Notification).
vi.mock("@/lib/api/push", () => ({
  useVapidKey: () => ({ data: { public_key: "PUBKEY", enabled: true } }),
  pushSupported: () => true,
  currentPushSubscription: vi.fn(async () => null),
  subscribeToPush: vi.fn(async () => {}),
  unsubscribeFromPush: vi.fn(async () => {}),
}));

import * as push from "@/lib/api/push";

import { PushToggle } from "./push-toggle";

describe("PushToggle", () => {
  it("subscribes on Activar and flips to Desactivar", async () => {
    render(<PushToggle />);

    // Effect resolves "not subscribed" → the enable button shows.
    const activar = await screen.findByRole("button", { name: "Activar" });
    fireEvent.click(activar);

    await waitFor(() =>
      expect(push.subscribeToPush).toHaveBeenCalledWith("PUBKEY"),
    );
    expect(
      await screen.findByRole("button", { name: "Desactivar" }),
    ).toBeInTheDocument();
  });
});
