"use client";

import { useState } from "react";

import { formatMoney } from "@/components/crm/money";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/errors";
import { type BillingPlan, startCheckout, useBillingPlans } from "@/lib/api/billing";
import { INTL_TAGS } from "@/lib/i18n/config";
import { useLocale, useT } from "@/lib/i18n/provider";

/** Polar's recurring products, cheapest first; choosing one opens Polar's
 *  payment page (the free trial, if the plan has one, starts there). */
export function PlanPicker({ accountId }: { accountId: string }) {
  const t = useT();
  const plans = useBillingPlans(accountId);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function choose(plan: BillingPlan) {
    setError(null);
    setStarting(plan.id);
    try {
      await startCheckout(accountId, plan.id);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("billing.plans.checkoutFailed"),
      );
      setStarting(null);
    }
  }

  if (plans.isLoading) {
    return <p className="text-sm text-fg-muted">{t("common.loading")}</p>;
  }
  if (plans.isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        {t("billing.plans.loadFailed")}
      </p>
    );
  }
  if (!plans.data?.length) {
    return <p className="text-sm text-fg-muted">{t("billing.plans.empty")}</p>;
  }

  return (
    <div className="space-y-3">
      {error ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-surface-2 px-3 py-2 text-sm text-danger"
        >
          {error}
        </p>
      ) : null}
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {plans.data.map((plan) => (
          <li key={plan.id}>
            <PlanCard
              plan={plan}
              starting={starting === plan.id}
              disabled={starting !== null}
              onChoose={() => void choose(plan)}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

function PlanCard({
  plan,
  starting,
  disabled,
  onChoose,
}: {
  plan: BillingPlan;
  starting: boolean;
  disabled: boolean;
  onChoose: () => void;
}) {
  const t = useT();
  const locale = useLocale();
  const price =
    plan.amount === null ? null : formatMoney(plan.amount, plan.currency, INTL_TAGS[locale]);
  return (
    <div className="flex h-full flex-col gap-3 rounded-md border border-glass bg-surface p-5">
      <div className="space-y-1">
        <h3 className="text-lg font-medium text-fg">{plan.name}</h3>
        {price ? (
          <p className="text-sm text-fg">
            {plan.interval === "year"
              ? t("billing.plans.perYear", { price })
              : t("billing.plans.perMonth", { price })}
          </p>
        ) : null}
        <p className="text-xs text-fg-muted">
          {plan.trial_days
            ? t("billing.plans.trial", { days: plan.trial_days })
            : t("billing.plans.noTrial")}
        </p>
      </div>
      {plan.description ? (
        <p className="flex-1 text-sm text-fg-muted">{plan.description}</p>
      ) : (
        <div className="flex-1" />
      )}
      <Button
        type="button"
        size="sm"
        loading={starting}
        disabled={disabled}
        onClick={onChoose}
      >
        {t("billing.plans.choose", { name: plan.name })}
      </Button>
    </div>
  );
}
