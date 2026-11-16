import { type QueryClient, useQuery } from "@tanstack/react-query";

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
  /** The plan's monthly AI cap and the credit that extends it. */
  usage?: { cap: number; spent: number; currency: string; credit_balance: number };
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
    // the browser does, so ask again until the plan shows up — for a
    // minute at most, in case the webhook never comes.
    refetchInterval: (query) =>
      untilPaid &&
      query.state.data?.has_access === false &&
      query.state.dataUpdateCount < POLL_ATTEMPTS
        ? 3_000
        : false,
  });
}

const POLL_ATTEMPTS = 20;

/** After a 402: the plan ran out mid-session, so the gate has to look
 *  again. Only the account's status (not the plans), and only while it
 *  still says the account has access. */
export function refreshBillingStatus(qc: QueryClient): void {
  for (const query of qc.getQueryCache().findAll({ queryKey: BILLING_KEY })) {
    const data = query.state.data as BillingStatus | undefined;
    if (query.queryKey.length === 2 && data?.has_access !== false) {
      void qc.invalidateQueries({ queryKey: query.queryKey, exact: true });
    }
  }
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

export type CreditTier = { from: number; share: number };

export type BillingCredits = {
  balance: number;
  currency: string;
  minimum: number;
  /** Highest threshold first, as the backend checks them. */
  tiers: CreditTier[];
  purchases: Array<{ id: number; paid: number; credit: number; refunded: boolean; paid_at: number }>;
};

export function useBillingCredits(
  accountId: string,
  { enabled = true, untilPaid = false }: { enabled?: boolean; untilPaid?: boolean } = {},
) {
  return useQuery({
    queryKey: [...BILLING_KEY, accountId, "credits"],
    queryFn: () => apiFetch<BillingCredits>(`${base(accountId)}/credits`),
    enabled,
    retry: false,
    // Back from Polar: order.paid may land a few seconds after the browser.
    refetchInterval: (query) =>
      untilPaid && query.state.dataUpdateCount < POLL_ATTEMPTS ? 3_000 : false,
  });
}

/** USD of credit an amount buys, with the backend's tiers (0 under the
 *  minimum). In whole cents, half a cent up, exactly as the backend
 *  credits it (``credit_for`` in billing/service.py). */
export function creditFor(amount: number, tiers: CreditTier[]): number {
  const cents = Math.round(amount * 100);
  const tier = tiers.find((t) => cents >= Math.round(t.from * 100));
  return tier ? Math.round(cents * tier.share) / 100 : 0;
}

/** Polar's payment page for that much credit (USD, before taxes). */
export async function startCreditsCheckout(accountId: string, amount: number): Promise<void> {
  const { url } = await apiFetch<{ url: string }>(`${base(accountId)}/credits/checkout`, {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
  window.location.href = url;
}
