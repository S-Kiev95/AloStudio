import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { refreshBillingStatus } from "./api/billing";
import { ApiError } from "./api/errors";

/** A 402 means the account's plan ran out (F2 multitenant): ask for the
 *  billing status again, so the shell swaps the page for "elegí un plan". */
function isPaymentRequired(error: unknown): boolean {
  return error instanceof ApiError && error.status === 402;
}

/**
 * One QueryClient per browser session. Conservative defaults — the
 * dashboard leans on realtime (ActionCable) for freshness, so we don't
 * aggressively refetch on focus.
 */
export function makeQueryClient(): QueryClient {
  const onError = (error: unknown) => {
    if (isPaymentRequired(error)) refreshBillingStatus(client);
  };
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // Retrying won't bring the plan back.
        retry: (failureCount, error) =>
          !isPaymentRequired(error) && failureCount < 1,
        refetchOnWindowFocus: false,
      },
    },
  });
  return client;
}
