/**
 * Asking the call dock to place a call (F7).
 *
 * The dock lives in the shell and owns the call's audio, so a call goes on
 * while the agent moves around the panel. A button anywhere (the
 * conversation header) only asks it to dial.
 */
export type DialRequest = {
  /** The conversation's number in the panel (``display_id``). */
  conversationId: number;
  contactName: string;
  thumbnail?: string | null;
};

const bus = typeof window !== "undefined" ? new EventTarget() : null;
const EVENT = "dial";

export function requestDial(request: DialRequest): void {
  bus?.dispatchEvent(new CustomEvent<DialRequest>(EVENT, { detail: request }));
}

export function onDialRequest(handler: (request: DialRequest) => void): () => void {
  if (!bus) return () => undefined;
  const listener = (event: Event) => handler((event as CustomEvent<DialRequest>).detail);
  bus.addEventListener(EVENT, listener);
  return () => bus.removeEventListener(EVENT, listener);
}
