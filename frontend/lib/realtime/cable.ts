/**
 * Minimal ActionCable client for the backend's `/cable` endpoint.
 *
 * Protocol (see app/core/cable.py):
 *   server → {type:"welcome"} · {type:"ping"} · {type:"confirm_subscription"}
 *            · {identifier, message:{event,data}}
 *   client → {command:"subscribe", identifier:"<json>"}
 *
 * Auth travels in the subscribe identifier (pubsub_token), so this
 * connects to the backend directly (no cookies needed). Auto-reconnects.
 */
export type CableMessage = { event: string; data: unknown };

export function createCable(
  url: string,
  identifier: Record<string, unknown>,
  onMessage: (msg: CableMessage) => void,
): () => void {
  const idStr = JSON.stringify(identifier);
  let ws: WebSocket | null = null;
  let closed = false;
  let retry: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    try {
      ws = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }
    ws.onmessage = (e) => {
      let frame: Record<string, unknown>;
      try {
        frame = JSON.parse(e.data as string);
      } catch {
        return;
      }
      if (frame.type === "welcome") {
        ws?.send(JSON.stringify({ command: "subscribe", identifier: idStr }));
        return;
      }
      // ping / confirm_subscription / reject_subscription → ignore.
      if (frame.type) return;
      if (frame.identifier === idStr && frame.message) {
        onMessage(frame.message as CableMessage);
      }
    };
    ws.onclose = scheduleReconnect;
    ws.onerror = () => ws?.close();
  }

  function scheduleReconnect() {
    if (closed || retry) return;
    retry = setTimeout(() => {
      retry = null;
      if (!closed) connect();
    }, 3000);
  }

  connect();

  return () => {
    closed = true;
    if (retry) clearTimeout(retry);
    ws?.close();
  };
}
