"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api/errors";
import { useBillingPlans, useBillingStatus } from "@/lib/api/billing";
import { usePublicInstallation } from "@/lib/api/installation";
import { useT } from "@/lib/i18n/provider";

import { PlanPicker } from "./plan-picker";

/**
 * F2 multitenant: an account without an active or trialing plan sees
 * "Elegí un plan" instead of the page (the API answers it 402 anyway).
 * Ajustes → Facturación stays reachable, to pay or check the state.
 * Does nothing on a single-tenant install (CTC, Enterprise).
 */
export function SubscriptionGate({
  accountId,
  children,
}: {
  accountId: string;
  children: ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const multitenant = Boolean(usePublicInstallation().data?.multitenant);
  const status = useBillingStatus(accountId, { enabled: multitenant });

  const onBilling = pathname.startsWith(`/accounts/${accountId}/settings/billing`);
  if (!multitenant || onBilling || !status.data || status.data.has_access) {
    return <>{children}</>;
  }
  return <ChoosePlan accountId={accountId} />;
}

function ChoosePlan({ accountId }: { accountId: string }) {
  const t = useT();
  // Choosing a plan is admin-only: a 401 here means an agent.
  const plans = useBillingPlans(accountId);
  const notAdmin =
    plans.error instanceof ApiError && plans.error.status === 401;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-medium text-fg">{t("billing.choose.title")}</h2>
        <p className="text-sm text-fg-muted">
          {notAdmin ? t("billing.choose.notAdmin") : t("billing.choose.subtitle")}
        </p>
      </div>
      {notAdmin ? null : <PlanPicker accountId={accountId} />}
    </div>
  );
}
