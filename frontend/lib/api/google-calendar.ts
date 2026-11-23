import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** The signed-in user's Google Calendar (F17): their appointments and CRM
 *  tasks with a date go to their primary calendar. */
export type GoogleCalendarStatus = {
  /** The installation has Google's client id and secret. */
  available: boolean;
  connected: boolean;
  email: string | null;
  last_synced_at: string | null;
  /** ``revoked`` when Google no longer accepts the access. */
  problem: string | null;
};

const BASE = "/api/v1/profile/google_calendar";
const KEY = ["googleCalendar"] as const;
/** Where the callback sends the user back. */
export const RETURN_KEY = "alostudio:google-calendar-return";

export function useGoogleCalendar() {
  return useQuery({ queryKey: KEY, queryFn: () => apiFetch<GoogleCalendarStatus>(BASE) });
}

export async function googleCalendarAuthorizeUrl(): Promise<string> {
  return (await apiFetch<{ url: string }>(`${BASE}/authorize_url`)).url;
}

export function useConnectGoogleCalendar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { code: string; state: string }) =>
      apiFetch<GoogleCalendarStatus>(BASE, { method: "POST", body: JSON.stringify(input) }),
    onSuccess: (status) => qc.setQueryData(KEY, status),
  });
}

export function useDisconnectGoogleCalendar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<GoogleCalendarStatus>(BASE, { method: "DELETE" }),
    onSuccess: (status) => qc.setQueryData(KEY, status),
  });
}

export function googleCalendarProblemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("google_calendar.")) {
    return `googleCalendar.problems.${code.slice(16)}`;
  }
  return "googleCalendar.problems.failed";
}
