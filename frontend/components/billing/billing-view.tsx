"use client";

import { notFound, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import {
  type BillingStatus,
  openBillingPortal,
  useBillingStatus,
} from "@/lib/api/billing";
import { usePublicInstallation } from "@/lib/api/installation";
import { useIsAccountAdmin } from "@/lib/api/profile";
import { INTL_TAGS } from "@/lib/i18n/config";
import { useLocale, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

import { PlanPicker } from "./plan-picker";

const STATUS_LABEL: Record<string, MessageKey> = {
  none: "billing.statuses.none",
  incomplete: "billing.statuses.incomplete",
  trialing: "billing.statuses.trialing",
  active: "billing.statuses.active",
  past_due: "billing.statuses.past_due",
  canceled: "billing.statuses.canceled",
  unpaid: "billing.statuses.unpaid",
};

/** Ajustes → Facturación (F2 multitenant): the plan, until when it is
 *  paid, Polar's portal, and the plans while there is no active one. */
export function BillingView({ accountId }: { accountId: string }) {
  const t = useT();
  const installation = usePublicInstallation();
  // Polar sends the browser back here with `checkout_id`; the status is
  // asked again for a minute (see useBillingStatus), and so long the note.
  const returning = Boolean(useSearchParams().get("checkout_id"));
  const [recent, setRecent] = useState(returning);
  useEffect(() => {
    if (!returning) return;
    const timer = window.setTimeout(() => setRecent(false), 60_000);
    return () => window.clearTimeout(timer);
  }, [returning]);
  const multitenant = Boolean(installation.data?.multitenant);
  const status = useBillingStatus(accountId, {
    enabled: multitenant,
    untilPaid: returning,
  });
  const notAdmin = !useIsAccountAdmin(accountId);
  const waiting = recent && status.data?.has_access === false;

  // Paid plans only exist on a multitenant install.
  if (installation.data && !multitenant) notFound();

  return (
    <div className="max-w-4xl space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-medium text-fg">{t("billing.title")}</h2>
        <p className="text-sm text-fg-muted">{t("billing.subtitle")}</p>
      </div>

      {waiting ? (
        <p role="status" className="text-sm text-fg-muted">
          {t("billing.confirming")}
        </p>
      ) : null}

      {installation.isLoading || status.isLoading ? (
        <p className="text-sm text-fg-muted">{t("common.loading")}</p>
      ) : status.isError || !status.data ? (
        <p role="alert" className="text-sm text-danger">
          {t("billing.loadFailed")}
        </p>
      ) : (
        <StatusCard
          accountId={accountId}
          status={status.data}
          canManage={!notAdmin}
        />
      )}

      {notAdmin ? (
        <p className="text-sm text-fg-muted">{t("billing.adminOnly")}</p>
      ) : status.data && !status.data.has_access ? (
        <section className="space-y-3">
          <h3 className="text-lg font-medium text-fg">{t("billing.plans.title")}</h3>
          <PlanPicker accountId={accountId} />
        </section>
      ) : null}
    </div>
  );
}

function StatusCard({
  accountId,
  status,
  canManage,
}: {
  accountId: string;
  status: BillingStatus;
  canManage: boolean;
}) {
  const t = useT();
  const locale = useLocale();
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const label = STATUS_LABEL[status.status];
  const date = status.current_period_end
    ? new Date(status.current_period_end * 1000).toLocaleDateString(
        INTL_TAGS[locale],
        { day: "numeric", month: "long", year: "numeric" },
      )
    : null;
  const period = !date
    ? null
    : status.status === "trialing"
      ? t("billing.trialEndsOn", { date })
      : status.cancel_at_period_end || status.status === "canceled"
        ? t("billing.endsOn", { date })
        : status.has_access
          ? t("billing.renewsOn", { date })
          : null;
  // Polar only has a customer once a checkout went through.
  const hasCustomer = status.status !== "none";

  async function portal() {
    setError(null);
    setOpening(true);
    try {
      await openBillingPortal(accountId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("billing.portalFailed"));
      setOpening(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("billing.plan")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-lg font-medium text-fg">
            {status.plan_name ?? t("billing.noPlan")}
          </span>
          <span
            className={
              status.has_access ? "text-sm text-success" : "text-sm text-danger"
            }
          >
            {label ? t(label) : status.status}
          </span>
        </div>
        {period ? <p className="text-sm text-fg-muted">{period}</p> : null}
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {canManage && hasCustomer ? (
          <div className="space-y-1 border-t border-glass pt-3">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              loading={opening}
              onClick={() => void portal()}
            >
              {t("billing.portal")}
            </Button>
            <p className="text-xs text-fg-muted">{t("billing.portalHint")}</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
