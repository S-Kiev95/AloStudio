import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Inbox row — all channels (Instagram + others). */
export type Inbox = {
  id: number;
  channel_id: number;
  name: string;
  channel_type: string;
};

/**
 * All inboxes for the account (any channel type). The backend response is
 * ``{payload: [...]}`` — we unwrap.
 */
export function useInboxes(accountId: string) {
  return useQuery({
    queryKey: ["inboxes", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: Inbox[] }>(
        `/api/v1/accounts/${accountId}/inboxes`,
      );
      return res.payload;
    },
    staleTime: 60_000,
  });
}
