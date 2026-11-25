"use client";

import { usePathname } from "next/navigation";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { openBillingPortal, useBillingStatus } from "@/lib/api/billing";
import { usePublicInstallation } from "@/lib/api/installation";
import { useIsAccountAdmin } from "@/lib/api/profile";
import { INTL_TAGS } from "@/lib/i18n/config";
import { useLocale, useT } from "@/lib/i18n/provider";

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
    const until = multitenant ? status.data?.access_until : null;
    return (
      <>
        {until ? <PastDueBanner accountId={accountId} until={until} /> : null}
        {children}
      </>
    );
  }
  return <ChoosePlan accountId={accountId} />;
}

/** A renewal charge failed: the account stays open for a few days while
 *  Polar retries; the admin updates the card in Polar's portal. */
function PastDueBanner({ accountId, until }: { accountId: string; until: number }) {
  const t = useT();
  const locale = useLocale();
  const isAdmin = useIsAccountAdmin(accountId);
  const [opening, setOpening] = useState(false);
  const date = new Date(until * 1000).toLocaleDateString(INTL_TAGS[locale], {
    day: "numeric",
    month: "long",
  });

  return (
    <div
      role="alert"
      className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-control border border-warning bg-surface-2 px-4 py-3 text-sm text-fg"
    >
      <span>{t(isAdmin ? "billing.pastDue.admin" : "billing.pastDue.agent", { date })}</span>
      {isAdmin ? (
        <Button
          type="button"
          size="sm"
          loading={opening}
          onClick={() => {
            setOpening(true);
            void openBillingPortal(accountId).catch(() => setOpening(false));
          }}
        >
          {t("billing.pastDue.update")}
        </Button>
      ) : null}
    </div>
  );
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
