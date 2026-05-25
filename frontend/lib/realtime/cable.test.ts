import { afterEach, describe, expect, it, vi } from "vitest";

import { createCable, type CableMessage } from "./cable";

class FakeWS {
  static instances: FakeWS[] = [];
  url: string;
  sent: string[] = [];
  closed = false;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWS.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.closed = true;
    this.onclose?.();
  }
  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

afterEach(() => {
  FakeWS.instances = [];
  vi.unstubAllGlobals();
});

describe("createCable", () => {
  function setup() {
    vi.stubGlobal("WebSocket", FakeWS as unknown as typeof WebSocket);
    const identifier = { channel: "RoomChannel", pubsub_token: "TKN" };
    const idStr = JSON.stringify(identifier);
    const received: CableMessage[] = [];
    const dispose = createCable("ws://x/cable", identifier, (m) =>
      received.push(m),
    );
    return { ws: FakeWS.instances[0], idStr, received, dispose };
  }

  it("subscribes with the identifier after the welcome frame", () => {
    const { ws, idStr, dispose } = setup();
    ws.emit({ type: "welcome" });
    expect(ws.sent).toHaveLength(1);
    expect(JSON.parse(ws.sent[0])).toEqual({
      command: "subscribe",
      identifier: idStr,
    });
    dispose();
  });

  it("routes channel messages and ignores ping/confirm", () => {
    const { ws, idStr, received, dispose } = setup();
    ws.emit({ type: "welcome" });
    ws.emit({ type: "ping", message: 123 });
    ws.emit({ type: "confirm_subscription", identifier: idStr });
    ws.emit({
      identifier: idStr,
      message: { event: "message.created", data: { id: 1 } },
    });
    expect(received).toEqual([{ event: "message.created", data: { id: 1 } }]);
    dispose();
  });

  it("closes the socket on dispose", () => {
    const { ws, dispose } = setup();
    dispose();
    expect(ws.closed).toBe(true);
  });
});
