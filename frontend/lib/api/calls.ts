import {
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** A voice call (F7). Today only WhatsApp carries them. */
export type CallStatus =
  | "ringing"
  | "connecting"
  | "in_progress"
  | "completed"
  | "missed"
  | "failed";

export type Call = {
  id: number;
  status: CallStatus;
  direction: "inbound" | "outbound";
  provider: string;
  inbox_id: number;
  inbox_name: string | null;
  conversation_id: number;
  conversation_display_id: number | null;
  contact: {
    id: number;
    name: string | null;
    phone_number: string | null;
    thumbnail?: string;
  } | null;
  from_number: string | null;
  answered_by: { id: number; name: string } | null;
  /** Still ringing and with the caller's offer: an agent can take it. */
  can_answer: boolean;
  created_at: string;
  answered_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  /** Only on GET /calls/:id, for the browser that answers. */
  sdp_offer?: string | null;
};

export const ACTIVE_CALL_STATUSES: readonly CallStatus[] = [
  "ringing",
  "connecting",
  "in_progress",
];

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/calls`;
}

export function activeCallsKey(accountId: string) {
  return ["calls", accountId, "active"] as const;
}

/** Calls ringing or under way in my inboxes. The cable keeps it current;
 *  the poll covers a missed event. */
export function useActiveCalls(accountId: string, enabled = true) {
  return useQuery({
    queryKey: activeCallsKey(accountId),
    queryFn: () =>
      apiFetch<{ payload: Call[] }>(`${base(accountId)}/active`).then(
        (r) => r.payload,
      ),
    enabled,
    refetchInterval: 15_000,
  });
}

/** A ``call.updated`` from the cable, applied at once: the request that
 *  started the call may not have committed when the event arrives, so
 *  asking the server again could miss it. */
export function upsertActiveCall(
  qc: QueryClient,
  accountId: string,
  call: Call,
): void {
  qc.setQueryData<Call[]>(activeCallsKey(accountId), (prev) => {
    const rest = (prev ?? []).filter((c) => c.id !== call.id);
    return ACTIVE_CALL_STATUSES.includes(call.status) ? [...rest, call] : rest;
  });
  qc.setQueryData<Call>(callKey(accountId, call.id), (prev) => ({ ...prev, ...call }));
}

export function callKey(accountId: string, id: number) {
  return ["calls", accountId, "one", id] as const;
}

/** One call, kept current while I am on it: the cable writes every change
 *  here, and the poll catches an end whose event got lost. */
export function useCall(accountId: string, id: number | null) {
  return useQuery({
    queryKey: callKey(accountId, id ?? 0),
    queryFn: () => apiFetch<Call>(`${base(accountId)}/${id}`),
    enabled: id !== null,
    refetchInterval: 10_000,
  });
}

/** The answering steps, in order: read the offer, open the audio path with
 *  the browser's answer, confirm, and later hang up. */
export function callApi(accountId: string) {
  const post = (id: number, step: string, sdp?: string) =>
    apiFetch<Call>(`${base(accountId)}/${id}/${step}`, {
      method: "POST",
      body: sdp === undefined ? undefined : JSON.stringify({ sdp }),
    });
  return {
    get: (id: number) => apiFetch<Call>(`${base(accountId)}/${id}`),
    preAccept: (id: number, sdp: string) => post(id, "pre_accept", sdp),
    accept: (id: number, sdp: string) => post(id, "accept", sdp),
    hangup: (id: number) => post(id, "hangup"),
    /** For when the page is closing: the request outlives it. */
    hangupOnUnload: (id: number) => {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";
      void fetch(`${apiBase}${base(accountId)}/${id}/hangup`, {
        method: "POST",
        keepalive: true,
        headers: { "Content-Type": "application/json" },
      }).catch(() => undefined);
    },
  };
}

/** The number's call settings on Meta (admins). */
export type CallSettings = {
  enabled: boolean;
  call_icon_visible: boolean;
  callback_requests: boolean;
  business_hours: boolean;
  restrictions: Array<{ type?: string; reason?: string; expiration?: number }> | null;
};

export type CallSettingsInput = Omit<CallSettings, "restrictions">;

function settingsKey(accountId: string, inboxId: number) {
  return ["calls", accountId, "settings", inboxId] as const;
}

export function useCallSettings(accountId: string, inboxId: number) {
  return useQuery({
    queryKey: settingsKey(accountId, inboxId),
    queryFn: () => apiFetch<CallSettings>(`${base(accountId)}/settings/${inboxId}`),
    retry: false,
  });
}

export function useSaveCallSettings(accountId: string, inboxId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CallSettingsInput) =>
      apiFetch<CallSettings>(`${base(accountId)}/settings/${inboxId}`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: (saved) => qc.setQueryData(settingsKey(accountId, inboxId), saved),
  });
}
