"use client";

import { useState } from "react";

import { formatMoney } from "@/components/crm/money";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/errors";
import {
  type BillingCredits,
  creditFor,
  startCreditsCheckout,
  useBillingCredits,
} from "@/lib/api/billing";
import { INTL_TAGS } from "@/lib/i18n/config";
import { useLocale, useT } from "@/lib/i18n/provider";
import { shortDate } from "@/lib/time";

/** AI credit (F2 multitenant): the balance that keeps AI running past the
 *  plan's cap, buying more for any amount from the minimum, and past
 *  top-ups. Admins only. */
export function CreditsSection({
  accountId,
  returning,
}: {
  accountId: string;
  /** Back from Polar's checkout for credit. */
  returning: boolean;
}) {
  const t = useT();
  const credits = useBillingCredits(accountId, { untilPaid: returning });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("billing.credits.title")}</CardTitle>
        <p className="text-sm text-fg-muted">{t("billing.credits.hint")}</p>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        {returning ? (
          <p role="status" className="text-sm text-fg-muted">
            {t("billing.credits.confirming")}
          </p>
        ) : null}
        {credits.isLoading ? (
          <p className="text-sm text-fg-muted">{t("common.loading")}</p>
        ) : credits.isError || !credits.data ? (
          <p role="alert" className="text-sm text-danger">
            {t("billing.credits.loadFailed")}
          </p>
        ) : (
          <>
            <Balance data={credits.data} />
            <BuyForm accountId={accountId} data={credits.data} />
            <History data={credits.data} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

function useMoney() {
  const tag = INTL_TAGS[useLocale()];
  return (value: number, currency: string) => formatMoney(value, currency, tag);
}

function Balance({ data }: { data: BillingCredits }) {
  const t = useT();
  const money = useMoney();
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-sm text-fg">{t("billing.credits.balance")}</span>
      <span className="text-lg font-medium text-fg">{money(data.balance, data.currency)}</span>
    </div>
  );
}

function BuyForm({ accountId, data }: { accountId: string; data: BillingCredits }) {
  const t = useT();
  const money = useMoney();
  const [amount, setAmount] = useState(String(Math.max(data.minimum, 20)));
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Whole cents: what Polar charges.
  const value = Math.round(Number(amount.replace(",", ".")) * 100) / 100;
  const valid = Number.isFinite(value) && value >= data.minimum;
  const credit = valid ? creditFor(value, data.tiers) : 0;
  // The cheapest tier above this amount: it pays to say what it'd give.
  const next = [...data.tiers].reverse().find((tier) => tier.from > value);

  async function buy() {
    setError(null);
    setStarting(true);
    try {
      await startCreditsCheckout(accountId, value);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("billing.credits.buyFailed"));
      setStarting(false);
    }
  }

  return (
    <div className="space-y-2 border-t border-glass pt-3">
      <Label htmlFor="credits-amount">{t("billing.credits.amount")}</Label>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          id="credits-amount"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-32"
        />
        <Button
          type="button"
          size="sm"
          loading={starting}
          disabled={!valid || starting}
          onClick={() => void buy()}
        >
          {t("billing.credits.buy")}
        </Button>
      </div>
      <p className="text-sm text-fg">
        {valid
          ? t("billing.credits.receive", { credit: money(credit, data.currency) })
          : t("billing.credits.minimum", { amount: money(data.minimum, data.currency) })}
      </p>
      {valid && next ? (
        <p className="text-xs text-fg-muted">
          {t("billing.credits.nextTier", {
            amount: money(next.from, data.currency),
            credit: money(creditFor(next.from, data.tiers), data.currency),
          })}
        </p>
      ) : null}
      <p className="text-xs text-fg-muted">{t("billing.credits.taxes")}</p>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function History({ data }: { data: BillingCredits }) {
  const t = useT();
  const money = useMoney();
  const locale = useLocale();
  if (!data.purchases.length) return null;
  return (
    <div className="space-y-1 border-t border-glass pt-3">
      <h4 className="text-sm font-medium text-fg">{t("billing.credits.history")}</h4>
      <ul className="space-y-1 text-sm text-fg-muted">
        {data.purchases.map((p) => (
          <li key={p.id} className="flex justify-between gap-2">
            <span>{shortDate(p.paid_at, locale)}</span>
            <span>
              {t("billing.credits.paidFor", {
                paid: money(p.paid, data.currency),
                credit: money(p.credit, data.currency),
              })}
              {p.refunded ? ` · ${t("billing.credits.refunded")}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
