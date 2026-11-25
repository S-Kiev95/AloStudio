"use client";

import { X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  type Payment,
  type PaymentMethod,
  type PaymentPreview,
  useContactStatement,
  useCreatePayment,
  usePreviewPayment,
  useUpdatePayment,
} from "@/lib/api/crm";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { animateDialogIn } from "@/lib/motion/neon-motion";
import { cn } from "@/lib/utils";

import { formatMoney } from "./money";

const METHODS: PaymentMethod[] = ["cash", "transfer", "card", "other"];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function parsePositiveAmount(raw: string): number | null {
  const cleaned = raw.trim().replace(",", ".");
  if (!cleaned) return null;
  const n = Number(cleaned);
  if (Number.isNaN(n) || !Number.isFinite(n) || n <= 0) return null;
  return Math.round(n * 100) / 100;
}

/** Dialog to record or edit a client payment, supporting automatic (oldest due
 *  first) or manual sale-by-sale allocation with a live resulting balance preview. */
export function PaymentDialog({
  accountId,
  contactId,
  contactName,
  open,
  onClose,
  initial,
  defaultCurrency,
  defaultOpportunityId,
  defaultAmount,
}: {
  accountId: string;
  contactId: number;
  contactName?: string | null;
  open: boolean;
  onClose: () => void;
  initial?: Payment | null;
  defaultCurrency?: string | null;
  defaultOpportunityId?: number | null;
  defaultAmount?: number | null;
}) {
  const t = useT();
  const intlTag = useIntlTag();
  const dialogRef = useRef<HTMLDialogElement>(null);

  const statement = useContactStatement(accountId, contactId, open);
  const createPayment = useCreatePayment(accountId);
  const updatePayment = useUpdatePayment(accountId);
  const previewMut = usePreviewPayment(accountId);
  const previewMutate = previewMut.mutate;
  const submitting = createPayment.isPending || updatePayment.isPending;

  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("");
  const [paidOn, setPaidOn] = useState(todayIso);
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [note, setNote] = useState("");
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [manualAmounts, setManualAmounts] = useState<Record<number, string>>({});
  const [preview, setPreview] = useState<PaymentPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open) {
      if (!el.open) {
        if (typeof el.showModal === "function") el.showModal();
        else el.setAttribute("open", "");
      }
      return animateDialogIn(el);
    } else if (el.open) {
      if (typeof el.close === "function") el.close();
      else el.removeAttribute("open");
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setPreview(null);
    setPreviewError(null);
    if (initial) {
      setAmount(String(initial.amount));
      setCurrency(initial.currency ?? "");
      setPaidOn(initial.paid_on);
      setMethod(initial.method);
      setNote(initial.note ?? "");
      setMode("manual");
      const map: Record<number, string> = {};
      for (const a of initial.allocations) {
        const prev = Number(map[a.opportunity_id] ?? "0");
        map[a.opportunity_id] = String(Math.round((prev + a.amount) * 100) / 100);
      }
      setManualAmounts(map);
    } else {
      setAmount(defaultAmount && defaultAmount > 0 ? String(defaultAmount) : "");
      setCurrency(defaultCurrency ?? "");
      setPaidOn(todayIso());
      setMethod("cash");
      setNote("");
      if (defaultOpportunityId && defaultAmount && defaultAmount > 0) {
        setMode("manual");
        setManualAmounts({ [defaultOpportunityId]: String(defaultAmount) });
      } else {
        setMode("auto");
        setManualAmounts({});
      }
    }
  }, [open, initial, defaultCurrency, defaultOpportunityId, defaultAmount]);

  // Fill currency once from the contact's statement if none was pre-filled.
  useEffect(() => {
    if (!open || initial || defaultCurrency) return;
    const fallbackCur =
      statement.data?.balances.find((b) => b.owed_total > 0)?.currency ??
      statement.data?.sales[0]?.currency ??
      "";
    if (fallbackCur) {
      setCurrency((curr) => (curr ? curr : fallbackCur));
    }
  }, [open, initial, defaultCurrency, statement.data]);

  const normalizedCurrency = currency.trim().toUpperCase() || null;

  const openSales = useMemo(() => {
    const sales = statement.data?.sales ?? [];
    const existingByOpp = new Map<number, number>();
    if (initial) {
      for (const a of initial.allocations) {
        existingByOpp.set(a.opportunity_id, (existingByOpp.get(a.opportunity_id) ?? 0) + a.amount);
      }
    }
    return sales
      .filter((s) => (s.currency ?? null) === normalizedCurrency)
      .map((s) => ({
        ...s,
        available_owed: Math.round((s.owed_amount + (existingByOpp.get(s.id) ?? 0)) * 100) / 100,
      }))
      .filter((s) => s.available_owed > 0);
  }, [statement.data?.sales, normalizedCurrency, initial]);

  const parsedAmount = parsePositiveAmount(amount);

  const manualAllocList = useMemo(() => {
    const out: { opportunity_id: number; amount: number }[] = [];
    for (const [oppIdStr, valStr] of Object.entries(manualAmounts)) {
      const v = parsePositiveAmount(valStr);
      if (v !== null) out.push({ opportunity_id: Number(oppIdStr), amount: v });
    }
    return out;
  }, [manualAmounts]);

  // Live preview of resulting balance before saving.
  useEffect(() => {
    if (!open || parsedAmount === null) {
      setPreview(null);
      setPreviewError(null);
      return;
    }
    const timer = setTimeout(() => {
      previewMutate(
        {
          contact_id: contactId,
          amount: parsedAmount,
          currency: normalizedCurrency,
          allocation_mode: mode,
          allocations: mode === "manual" ? manualAllocList : undefined,
          exclude_payment_id: initial?.id ?? null,
        },
        {
          onSuccess: (data) => {
            setPreview(data);
            setPreviewError(null);
          },
          onError: (err) => {
            setPreview(null);
            setPreviewError((err as { message?: string })?.message ?? null);
          },
        },
      );
    }, 120);
    return () => clearTimeout(timer);
  }, [
    open,
    contactId,
    parsedAmount,
    normalizedCurrency,
    mode,
    manualAllocList,
    initial?.id,
    previewMutate,
  ]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (parsedAmount === null) {
      setError(t("collections.payment.amountInvalid"));
      return;
    }
    try {
      if (initial) {
        await updatePayment.mutateAsync({
          id: initial.id,
          patch: {
            amount: parsedAmount,
            paid_on: paidOn,
            method,
            note: note.trim() || null,
            allocation_mode: mode,
            allocations: mode === "manual" ? manualAllocList : undefined,
          },
        });
      } else {
        await createPayment.mutateAsync({
          contact_id: contactId,
          amount: parsedAmount,
          currency: normalizedCurrency,
          paid_on: paidOn,
          method,
          note: note.trim() || null,
          allocation_mode: mode,
          allocations: mode === "manual" ? manualAllocList : undefined,
        });
      }
      onClose();
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("collections.payment.saveFailed"));
    }
  }

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="payment-dialog-title"
      className="glass-dialog w-full max-w-lg rounded-panel p-0 text-fg backdrop:bg-backdrop"
    >
      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="payment-dialog-title" className="text-lg font-medium text-fg">
              {initial ? t("collections.payment.edit") : t("collections.payment.register")}
            </h2>
            {contactName ? <p className="text-xs text-fg-muted">{contactName}</p> : null}
          </div>
          <button
            type="button"
            aria-label={t("actions.closeDialog")}
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        <div className="grid grid-cols-[1fr_6rem] gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="pay-amount" required>
              {t("collections.payment.amount")}
            </Label>
            <Input
              id="pay-amount"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="tabular-nums"
              placeholder="0.00" // i18n-ignore
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pay-currency">{t("collections.payment.currency")}</Label>
            <Input
              id="pay-currency"
              value={currency}
              maxLength={8}
              disabled={Boolean(initial)}
              onChange={(e) => setCurrency(e.target.value)}
              placeholder="UYU" // i18n-ignore
            />
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="pay-date">{t("collections.payment.paidOn")}</Label>
            <Input
              id="pay-date"
              type="date"
              value={paidOn}
              onChange={(e) => setPaidOn(e.target.value)}
              className="tabular-nums"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pay-method">{t("collections.payment.method")}</Label>
            <select
              id="pay-method"
              value={method}
              onChange={(e) => setMethod(e.target.value as PaymentMethod)}
              className={selectClassName()}
            >
              {METHODS.map((m) => (
                <option key={m} value={m}>
                  {t(`collections.payment.methods.${m}`)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="pay-note">{t("collections.payment.note")}</Label>
          <Textarea
            id="pay-note"
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("collections.payment.notePlaceholder")}
          />
        </div>

        <div className="space-y-2 border-t border-glass pt-3">
          <Label>{t("collections.payment.allocationMode")}</Label>
          <SegmentedControl
            ariaLabel={t("collections.payment.allocationMode")}
            size="sm"
            value={mode}
            onValueChange={setMode}
            options={[
              { value: "auto", label: t("collections.payment.modeAuto") },
              { value: "manual", label: t("collections.payment.modeManual") },
            ]}
          />

          {mode === "manual" ? (
            openSales.length === 0 ? (
              <p className="text-xs text-fg-muted">{t("collections.payment.noOpenSales")}</p>
            ) : (
              <ul className="max-h-44 space-y-2 overflow-y-auto rounded-md border border-glass bg-surface-2 p-2.5">
                {openSales.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-2 text-xs">
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-fg">{s.title}</p>
                      <p className="font-numeric tabular-nums text-fg-muted">
                        {t("collections.payment.saleOwed", {
                          amount: formatMoney(s.available_owed, s.currency, intlTag),
                        })}
                        {s.days_overdue > 0 ? (
                          <span className="ml-1.5 text-danger">
                            · {t("collections.daysOverdue", { days: s.days_overdue })}
                          </span>
                        ) : null}
                      </p>
                    </div>
                    <Input
                      aria-label={t("collections.payment.amountForSale", { title: s.title })}
                      inputMode="decimal"
                      value={manualAmounts[s.id] ?? ""}
                      onChange={(e) =>
                        setManualAmounts((prev) => ({ ...prev, [s.id]: e.target.value }))
                      }
                      className="h-8 w-28 text-right tabular-nums"
                      placeholder="0.00" // i18n-ignore
                    />
                  </li>
                ))}
              </ul>
            )
          ) : null}
        </div>

        {previewError ? (
          <p role="alert" className="text-xs text-danger">
            {previewError}
          </p>
        ) : null}

        {preview ? (
          <section
            aria-label={t("collections.payment.previewTitle")}
            className="space-y-2 rounded-md border border-glass bg-surface-2 p-3 text-xs"
          >
            <p className="font-medium text-fg">{t("collections.payment.previewTitle")}</p>
            {preview.allocations.length > 0 ? (
              <ul className="space-y-1 text-fg-muted">
                {preview.allocations.map((a, idx) => (
                  <li key={`${a.opportunity_id}-${a.installment_id ?? idx}`} className="flex justify-between gap-2">
                    <span className="truncate">
                      {a.opportunity_title}
                      {a.installment_number
                        ? ` · ${t("collections.billing.installmentNumber", { n: a.installment_number })}`
                        : ""}
                    </span>
                    <span className="shrink-0 font-numeric tabular-nums text-fg">
                      {formatMoney(a.amount, preview.currency, intlTag)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-fg-muted">{t("collections.payment.noOpenSales")}</p>
            )}
            <div className="grid grid-cols-3 gap-2 border-t border-glass pt-2">
              <div>
                <span className="block text-fg-muted">{t("collections.payment.beforeOwed")}</span>
                <span className="font-numeric font-medium tabular-nums text-fg">
                  {formatMoney(preview.balance_before.owed_total, preview.currency, intlTag)}
                </span>
              </div>
              <div>
                <span className="block text-fg-muted">{t("collections.payment.afterOwed")}</span>
                <span
                  className={cn(
                    "font-numeric font-medium tabular-nums",
                    preview.balance_after.owed_total === 0 ? "text-success" : "text-fg",
                  )}
                >
                  {formatMoney(preview.balance_after.owed_total, preview.currency, intlTag)}
                </span>
              </div>
              <div>
                <span className="block text-fg-muted">{t("collections.payment.afterCredit")}</span>
                <span
                  className={cn(
                    "font-numeric font-medium tabular-nums",
                    preview.balance_after.credit_balance > 0 ? "text-success" : "text-fg-muted",
                  )}
                >
                  {formatMoney(preview.balance_after.credit_balance, preview.currency, intlTag)}
                </span>
              </div>
            </div>
          </section>
        ) : null}

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
            {t("actions.cancel")}
          </Button>
          <Button type="submit" loading={submitting} disabled={Boolean(previewError)}>
            {t("collections.payment.save")}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
