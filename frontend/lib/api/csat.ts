import { useQuery } from "@tanstack/react-query";

import type { Agent } from "./account";
import { apiFetch } from "./fetcher";

/** A single CSAT survey response (mirrors backend's presenter). */
export type CsatResponse = {
  id: number;
  rating: number; // 1..5
  feedback_message: string | null;
  csat_review_notes: string | null;
  review_notes_updated_at: number | null;
  review_notes_updated_by?: Agent | null;
  account_id: number;
  message_id: number;
  contact: {
    id: number;
    name: string | null;
    email: string | null;
    phone_number: string | null;
  } | null;
  conversation_id: number | null; // display_id
  assigned_agent?: Agent | null;
  created_at: number | null;
};

export type CsatMetrics = {
  total_count: number;
  ratings_count: Record<string, number>; // backend keys come out as strings
  total_sent_messages_count: number;
};

export type CsatFilters = {
  rating?: number;
  since?: number;
  until?: number;
  page?: number;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/csat_survey_responses`;
}

export function useCsatResponses(accountId: string, filters: CsatFilters = {}) {
  const { rating, since, until, page = 1 } = filters;
  return useQuery({
    queryKey: [
      "csat-responses",
      accountId,
      rating ?? null,
      since ?? null,
      until ?? null,
      page,
    ],
    queryFn: () => {
      const sp = new URLSearchParams();
      if (rating !== undefined) sp.set("rating", String(rating));
      if (since !== undefined) sp.set("since", String(since));
      if (until !== undefined) sp.set("until", String(until));
      sp.set("page", String(page));
      return apiFetch<CsatResponse[]>(`${base(accountId)}?${sp}`);
    },
  });
}

export function useCsatMetrics(
  accountId: string,
  range: { since?: number; until?: number },
) {
  return useQuery({
    queryKey: ["csat-metrics", accountId, range.since ?? null, range.until ?? null],
    queryFn: () => {
      const sp = new URLSearchParams();
      if (range.since !== undefined) sp.set("since", String(range.since));
      if (range.until !== undefined) sp.set("until", String(range.until));
      const qs = sp.toString();
      return apiFetch<CsatMetrics>(
        `${base(accountId)}/metrics${qs ? `?${qs}` : ""}`,
      );
    },
  });
}
