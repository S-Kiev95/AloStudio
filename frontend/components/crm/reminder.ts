import type { Translate } from "@/lib/i18n/translate";

import { formatMoney } from "./money";

export type ReminderCurrencyAmount = {
  currency: string | null;
  owed_total: number;
  overdue_total: number;
};

/** Builds a pre-filled reminder draft (never sent automatically). */
export function buildReminderText(
  t: Translate,
  intlTag: string,
  opts: {
    contactName: string | null;
    currencies: ReminderCurrencyAmount[];
    nextDueOn: string | null;
  },
): string {
  const name = opts.contactName?.trim() || "";
  const overdueItems = opts.currencies.filter((c) => c.overdue_total > 0);
  const source = overdueItems.length > 0 ? overdueItems : opts.currencies.filter((c) => c.owed_total > 0);
  const amount = source
    .map((c) => formatMoney(overdueItems.length > 0 ? c.overdue_total : c.owed_total, c.currency, intlTag))
    .join(" / ");

  if (opts.nextDueOn) {
    const dueDate = new Date(`${opts.nextDueOn}T00:00:00`).toLocaleDateString(intlTag, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
    return t("collections.reminder.templateWithDue", { name, amount, dueDate });
  }
  return t("collections.reminder.templateNoDue", { name, amount });
}

export function buildWhatsappReminderHref(
  accountId: string,
  displayId: number,
  draft: string,
): string {
  const sp = new URLSearchParams({ draft });
  return `/accounts/${accountId}/conversations/${displayId}?${sp.toString()}`;
}
