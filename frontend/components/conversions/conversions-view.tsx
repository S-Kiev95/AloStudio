"use client";

import { Megaphone } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useClosingSettings } from "@/lib/api/closing";
import {
  CONVERSION_EVENTS,
  type ConversionEventName,
  type ConversionRules,
  CRM_TRIGGERS,
  type CrmTrigger,
  conversionProblem,
  useConnectDataset,
  useConversionEvents,
  useConversionSettings,
  useSaveConversionSettings,
} from "@/lib/api/conversions";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

const NONE = "";

/** Ajustes → Conversions API (F17): tell Meta which ad conversations
 *  became leads or sales. */
export function ConversionsView({ accountId }: { accountId: string }) {
  const t = useT();
  const settings = useConversionSettings(accountId);
  const closing = useClosingSettings(accountId);
  const save = useSaveConversionSettings(accountId);
  const connect = useConnectDataset(accountId);
  const [enabled, setEnabled] = useState(false);
  const [currency, setCurrency] = useState("USD");
  const [rules, setRules] = useState<ConversionRules | null>(null);
  const [saved, setSaved] = useState(false);
  const [connecting, setConnecting] = useState<{
    inboxId: number;
    key: string;
    meta: string | null;
  } | null>(null);

  useEffect(() => {
    const data = settings.data;
    if (!data) return;
    setEnabled(data.enabled);
    setCurrency(data.currency);
    setRules(data.rules);
  }, [settings.data]);

  const reasons = closing.data?.enabled ? closing.data.categories : [];

  function edited() {
    setSaved(false);
  }

  function setCrm(trigger: CrmTrigger, event: string) {
    edited();
    setRules((r) => (r ? { ...r, [trigger]: (event || null) as ConversionEventName | null } : r));
  }

  function setClosing(reason: string, event: string, value: number | null) {
    edited();
    setRules((r) => {
      if (!r) return r;
      const closingRules = { ...r.closing };
      if (event) closingRules[reason] = { event: event as ConversionEventName, value };
      else delete closingRules[reason];
      return { ...r, closing: closingRules };
    });
  }

  async function submit() {
    if (!rules) return;
    edited();
    try {
      await save.mutateAsync({ enabled, currency, rules });
      setSaved(true);
    } catch {
      // shown below from save.error
    }
  }

  async function connectInbox(inboxId: number) {
    setConnecting(null);
    try {
      await connect.mutateAsync(inboxId);
    } catch (err) {
      setConnecting({ inboxId, ...conversionProblem(err) });
    }
  }

  const eventOptions = (
    <>
      <option value={NONE}>{t("conversions.none")}</option>
      {CONVERSION_EVENTS.map((event) => (
        <option key={event} value={event}>
          {t(`conversions.events.${event}`)}
        </option>
      ))}
    </>
  );
  const saveProblem = save.error ? conversionProblem(save.error) : null;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Megaphone className="h-4 w-4 text-fg-muted" aria-hidden />
            {t("conversions.title")}
          </CardTitle>
          <p className="mt-1 text-sm text-fg-muted">{t("conversions.intro")}</p>
          <p className="mt-2 text-xs text-fg-muted">{t("conversions.requirements")}</p>
        </CardHeader>
        <CardContent className="space-y-5">
          {settings.isLoading || !rules ? (
            <p className="text-sm text-fg-muted">{t("common.loading")}</p>
          ) : (
            <>
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 accent-neon"
                  checked={enabled}
                  onChange={() => {
                    edited();
                    setEnabled((v) => !v);
                  }}
                />
                <span>
                  <span className="block text-sm font-medium text-fg">
                    {t("conversions.enabled")}
                  </span>
                  <span className="block text-xs text-fg-muted">
                    {t("conversions.enabledHint")}
                  </span>
                </span>
              </label>

              <div className="space-y-1.5">
                <Label htmlFor="conversions-currency">{t("conversions.currency")}</Label>
                <Input
                  id="conversions-currency"
                  className="max-w-[8rem]"
                  value={currency}
                  maxLength={3}
                  onChange={(e) => {
                    edited();
                    setCurrency(e.target.value.toUpperCase());
                  }}
                />
                <p className="text-xs text-fg-muted">{t("conversions.currencyHint")}</p>
              </div>

              <fieldset className="space-y-2 border-t border-glass pt-4">
                <legend className="text-sm font-medium text-fg">{t("conversions.numbers")}</legend>
                {settings.data?.inboxes.length ? (
                  <ul className="space-y-2">
                    {settings.data.inboxes.map((inbox) => (
                      <li key={inbox.inbox_id} className="space-y-1">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-sm text-fg">
                            {inbox.name}
                            <span
                              className={cn(
                                "ml-2 text-xs",
                                inbox.dataset_id ? "text-success" : "text-fg-muted",
                              )}
                            >
                              {inbox.dataset_id
                                ? t("conversions.connected", { id: inbox.dataset_id })
                                : t("conversions.notConnected")}
                            </span>
                          </span>
                          <Button
                            variant="secondary"
                            size="sm"
                            loading={connect.isPending && connect.variables === inbox.inbox_id}
                            onClick={() => void connectInbox(inbox.inbox_id)}
                          >
                            {inbox.dataset_id ? t("conversions.reconnect") : t("conversions.connect")}
                          </Button>
                        </div>
                        {connecting?.inboxId === inbox.inbox_id ? (
                          <p role="alert" className="text-xs text-danger">
                            {translateOr(t, connecting.key, t("conversions.problems.failed"))}
                            {connecting.meta ? ` (${connecting.meta})` : ""}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-fg-muted">{t("conversions.numbersEmpty")}</p>
                )}
              </fieldset>

              <fieldset className="space-y-3 border-t border-glass pt-4">
                <legend className="text-sm font-medium text-fg">
                  {t("conversions.rulesTitle")}
                </legend>
                {CRM_TRIGGERS.map((trigger) => (
                  <div key={trigger} className="grid gap-1.5 sm:grid-cols-[1fr_19rem] sm:items-center">
                    <Label htmlFor={`conversions-${trigger}`}>{t(`conversions.crm.${trigger}`)}</Label>
                    <Select
                      id={`conversions-${trigger}`}
                      value={rules[trigger] ?? NONE}
                      onChange={(e) => setCrm(trigger, e.target.value)}
                    >
                      {eventOptions}
                    </Select>
                  </div>
                ))}

                <p className="pt-2 text-sm font-medium text-fg">{t("conversions.closingTitle")}</p>
                {reasons.length ? (
                  reasons.map((reason, i) => {
                    const rule = rules.closing[reason];
                    return (
                      <div
                        key={reason}
                        className="grid gap-1.5 sm:grid-cols-[1fr_19rem_7rem] sm:items-center"
                      >
                        <Label htmlFor={`conversions-closing-${i}`}>{reason}</Label>
                        <Select
                          id={`conversions-closing-${i}`}
                          value={rule?.event ?? NONE}
                          onChange={(e) => setClosing(reason, e.target.value, rule?.value ?? null)}
                        >
                          {eventOptions}
                        </Select>
                        {rule?.event === "Purchase" ? (
                          <Input
                            type="number"
                            min={0}
                            aria-label={t("conversions.valueFor", { reason })}
                            placeholder={t("conversions.value")}
                            value={rule.value ?? ""}
                            onChange={(e) =>
                              setClosing(
                                reason,
                                rule.event,
                                e.target.value === "" ? null : Number(e.target.value),
                              )
                            }
                          />
                        ) : (
                          <span aria-hidden />
                        )}
                      </div>
                    );
                  })
                ) : (
                  <p className="text-xs text-fg-muted">
                    {t("conversions.closingOff")}{" "}
                    <Link
                      href={`/accounts/${accountId}/settings/closing_notes`}
                      className="text-lit underline-offset-2 hover:underline"
                    >
                      {t("conversions.closingLink")}
                    </Link>
                  </p>
                )}
              </fieldset>

              <div className="flex flex-wrap items-center gap-3">
                <Button size="sm" onClick={() => void submit()} loading={save.isPending}>
                  {t("conversions.save")}
                </Button>
                {saved ? (
                  <span role="status" className="text-sm text-success">
                    {t("conversions.saved")}
                  </span>
                ) : null}
                {saveProblem ? (
                  <span role="alert" className="text-sm text-danger">
                    {translateOr(t, saveProblem.key, t("conversions.problems.failed"))}
                  </span>
                ) : null}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <EventsLog accountId={accountId} />
    </div>
  );
}

function EventsLog({ accountId }: { accountId: string }) {
  const t = useT();
  const tag = useIntlTag();
  const events = useConversionEvents(accountId);
  const when = new Intl.DateTimeFormat(tag, { dateStyle: "short", timeStyle: "short" });
  const rows = events.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("conversions.log.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {events.isLoading ? (
          <p className="text-sm text-fg-muted">{t("common.loading")}</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-fg-muted">{t("conversions.log.empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-fg-muted">
                <tr>
                  <th className="py-2 pr-3 font-medium">{t("conversions.log.when")}</th>
                  <th className="py-2 pr-3 font-medium">{t("conversions.log.conversation")}</th>
                  <th className="py-2 pr-3 font-medium">{t("conversions.log.event")}</th>
                  <th className="py-2 pr-3 font-medium">{t("conversions.log.value")}</th>
                  <th className="py-2 font-medium">{t("conversions.log.status")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-glass">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="py-2 pr-3 text-fg-muted">{when.format(new Date(row.created_at))}</td>
                    <td className="py-2 pr-3">
                      <Link
                        href={`/accounts/${accountId}/conversations/${row.conversation_id}`}
                        className="text-lit underline-offset-2 hover:underline"
                      >
                        #{row.conversation_id}
                      </Link>
                    </td>
                    <td className="py-2 pr-3 text-fg">
                      {t(`conversions.events.${row.event_name}`)}
                      {row.detail ? (
                        <span className="block text-xs text-fg-muted">{row.detail}</span>
                      ) : null}
                    </td>
                    <td className="py-2 pr-3 font-numeric tabular-nums text-fg">
                      {row.value !== null
                        ? new Intl.NumberFormat(tag, {
                            style: "currency",
                            currency: row.currency || "USD",
                          }).format(row.value)
                        : "—"}
                    </td>
                    <td className="py-2">
                      <span
                        className={cn(
                          row.status === "sent" && "text-success",
                          row.status === "failed" && "text-danger",
                          row.status === "pending" && "text-fg-muted",
                        )}
                      >
                        {t(`conversions.log.statuses.${row.status}`)}
                      </span>
                      {row.error ? (
                        <span className="block text-xs text-fg-muted">{row.error}</span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
