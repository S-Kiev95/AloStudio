"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useBillingStatus } from "@/lib/api/billing";
import { usePublicInstallation } from "@/lib/api/installation";
import { useIsAccountAdmin } from "@/lib/api/profile";
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
  const t = useT();
  const pathname = usePathname() ?? "";
  const installation = usePublicInstallation();
  const multitenant = Boolean(installation.data?.multitenant);
  const status = useBillingStatus(accountId, { enabled: multitenant });

  const billingHref = `/accounts/${accountId}/settings/billing`;
  if (pathname === billingHref || pathname.startsWith(`${billingHref}/`)) {
    return <>{children}</>;
  }
  // Until we know, show nothing: the page would fire requests that a
  // multitenant account without a plan answers 402.
  if (installation.isLoading || (multitenant && status.isLoading)) {
    return <p className="text-sm text-fg-muted">{t("common.loading")}</p>;
  }
  if (!multitenant || !status.data || status.data.has_access) {
    return <>{children}</>;
  }
  return <ChoosePlan accountId={accountId} />;
}

function ChoosePlan({ accountId }: { accountId: string }) {
  const t = useT();
  const isAdmin = useIsAccountAdmin(accountId);

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-medium text-fg">{t("billing.choose.title")}</h2>
        <p className="text-sm text-fg-muted">
          {isAdmin ? t("billing.choose.subtitle") : t("billing.choose.notAdmin")}
        </p>
      </div>
      {isAdmin ? <PlanPicker accountId={accountId} /> : null}
    </div>
  );
}
