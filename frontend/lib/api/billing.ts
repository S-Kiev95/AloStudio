import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Paid plans on a multitenant install (F2 paso 3), charged through Polar.
 *  The plans are Polar's recurring products; the subscription is written
 *  only from Polar's webhooks. */

export type SubscriptionStatus =
  | "none"
  | "incomplete"
  | "trialing"
  | "active"
  | "past_due"
  | "canceled"
  | "unpaid";

export type BillingStatus = {
  status: SubscriptionStatus | string;
  has_access: boolean;
  plan_name?: string | null;
  product_id?: string | null;
  /** Unix seconds. */
  current_period_end?: number | null;
  cancel_at_period_end?: boolean;
};

export type BillingPlan = {
  id: string;
  name: string;
  description: string | null;
  amount: number | null;
  currency: string | null;
  interval: string | null;
  trial_days: number | null;
};

export const BILLING_KEY = ["billing"];

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/billing`;
}

export function useBillingStatus(
  accountId: string,
  { enabled = true, untilPaid = false }: { enabled?: boolean; untilPaid?: boolean } = {},
) {
  return useQuery({
    queryKey: [...BILLING_KEY, accountId],
    queryFn: () => apiFetch<BillingStatus>(base(accountId)),
    enabled,
    retry: false,
    // Back from Polar's checkout: its webhook may land a few seconds after
    // the browser does, so ask again until the plan shows up.
    refetchInterval: (query) =>
      untilPaid && query.state.data?.has_access === false ? 3_000 : false,
  });
}

export function useBillingPlans(accountId: string, enabled = true) {
  return useQuery({
    queryKey: [...BILLING_KEY, accountId, "plans"],
    queryFn: async () =>
      (await apiFetch<{ plans: BillingPlan[] }>(`${base(accountId)}/plans`))
        .plans,
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/** Polar's payment page for that plan. */
export async function startCheckout(
  accountId: string,
  productId: string,
): Promise<void> {
  const { url } = await apiFetch<{ url: string }>(
    `${base(accountId)}/checkout`,
    { method: "POST", body: JSON.stringify({ product_id: productId }) },
  );
  window.location.href = url;
}

/** Polar's customer portal: card, invoices, change plan, cancel. */
export async function openBillingPortal(accountId: string): Promise<void> {
  const { url } = await apiFetch<{ url: string }>(`${base(accountId)}/portal`, {
    method: "POST",
  });
  window.location.href = url;
}
