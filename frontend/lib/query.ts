import { QueryClient } from "@tanstack/react-query";

/**
 * One QueryClient per browser session. Conservative defaults — the
 * dashboard leans on realtime (ActionCable) for freshness, so we don't
 * aggressively refetch on focus.
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  });
}
