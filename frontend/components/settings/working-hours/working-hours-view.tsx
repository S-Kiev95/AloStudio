"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { selectClassName } from "@/components/ui/select";
import { useInboxes } from "@/lib/api/inboxes";
import {
  type WorkingHour,
  type WorkingHourInput,
  useBulkUpdateWorkingHours,
  useInboxWorkingHours,
} from "@/lib/api/working-hours";
import { cn } from "@/lib/utils";
import { useLocale, useT } from "@/lib/i18n/provider";
import { weekdayName } from "@/components/agenda/week-utils";
import type { Locale } from "@/lib/i18n/config";

/** Day name for the backend's day_of_week (0 = Sunday). 2024-01-07 was a Sunday. */
function dayName(dayOfWeek: number, locale: Locale): string {
  return weekdayName(new Date(2024, 0, 7 + dayOfWeek), "long", locale);
}

export function WorkingHoursView({ accountId }: { accountId: string }) {
  const t = useT();
  const inboxes = useInboxes(accountId);
  const [inboxId, setInboxId] = useState<number | null>(null);

  // Pick the first inbox by default when the list loads.
  useEffect(() => {
    if (inboxId === null && inboxes.data?.length) {
      setInboxId(inboxes.data[0].id);
    }
  }, [inboxId, inboxes.data]);

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-medium text-fg">{t("settings.items.working_hours")}</h2>
        <div className="flex items-center gap-2">
          <label htmlFor="wh-inbox" className="text-sm text-fg-muted">
            {t("conversations.filters.attr.inbox")}
          </label>
          <select
            id="wh-inbox"
            className={cn(selectClassName(), "w-auto min-w-44")}
            value={inboxId ?? ""}
            onChange={(e) => setInboxId(Number(e.target.value) || null)}
            disabled={inboxes.isLoading}
          >
            <option value="">{t("campaigns.form.pickInboxPlaceholder")}</option>
            {inboxes.data?.map((ib) => (
              <option key={ib.id} value={ib.id}>
                {ib.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {inboxes.isLoading ? (
        <p className="text-sm text-fg-muted">{t("contacts.inboxes.loading")}</p>
      ) : inboxes.isError ? (
        <p role="alert" className="text-sm text-danger">
          {t("settingsHours.inboxesLoadFailed")}
        </p>
      ) : (inboxes.data?.length ?? 0) === 0 ? (
        <p className="text-sm text-fg-muted">
          {t("settingsHours.noInboxes")}
        </p>
      ) : inboxId ? (
        <Schedule accountId={accountId} inboxId={inboxId} />
      ) : null}
    </div>
  );
}

function Schedule({
  accountId,
  inboxId,
}: {
  accountId: string;
  inboxId: number;
}) {
  const t = useT();
  const { data, isLoading, isError } = useInboxWorkingHours(accountId, inboxId);
  const bulkUpdate = useBulkUpdateWorkingHours(accountId, inboxId);

  const [schedule, setSchedule] = useState<WorkingHourInput[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Hydrate the editor when the server data loads / changes inbox.
  useEffect(() => {
    if (!data) return;
    setSchedule(
      data
        .slice()
        .sort((a, b) => a.day_of_week - b.day_of_week)
        .map(toInput),
    );
  }, [data]);

  function updateRow(dow: number, patch: Partial<WorkingHourInput>) {
    setSchedule((prev) =>
      prev.map((r) => (r.day_of_week === dow ? { ...r, ...patch } : r)),
    );
  }

  async function save() {
    setError(null);
    setSaved(false);
    try {
      await bulkUpdate.mutateAsync(schedule);
      setSaved(true);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsHours.saveFailed"),
      );
    }
  }

  if (isLoading) {
    return <p className="text-sm text-fg-muted">{t("settingsHours.loading")}</p>;
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        {t("settingsHours.loadFailed")}
      </p>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settingsHours.weekly")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {saved ? (
          <p className="text-sm text-success">{t("common.changesSaved")}</p>
        ) : null}

        <div className="space-y-2">
          {schedule.map((row) => (
            <DayRow
              key={row.day_of_week}
              row={row}
              onChange={(patch) => updateRow(row.day_of_week, patch)}
            />
          ))}
        </div>

        <div className="flex justify-end">
          <Button onClick={save} loading={bulkUpdate.isPending}>
            {t("actions.save")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function DayRow({
  row,
  onChange,
}: {
  row: WorkingHourInput;
  onChange: (patch: Partial<WorkingHourInput>) => void;
}) {
  const t = useT();
  const locale = useLocale();
  const disabled = row.closed_all_day || row.open_all_day;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-glass bg-surface-2/40 p-3">
      <p className="w-24 shrink-0 text-sm font-medium text-fg">
        {dayName(row.day_of_week, locale)}
      </p>

      <label className="flex items-center gap-1.5 text-sm text-fg">
        <input
          type="checkbox"
          checked={row.closed_all_day}
          onChange={(e) =>
            onChange({
              closed_all_day: e.target.checked,
              open_all_day: e.target.checked ? false : row.open_all_day,
            })
          }
          className="h-4 w-4 rounded border-glass accent-neon"
        />
        {t("settingsHours.closed")}
      </label>

      <label className="flex items-center gap-1.5 text-sm text-fg">
        <input
          type="checkbox"
          checked={row.open_all_day}
          onChange={(e) =>
            onChange({
              open_all_day: e.target.checked,
              closed_all_day: e.target.checked ? false : row.closed_all_day,
            })
          }
          className="h-4 w-4 rounded border-glass accent-neon"
        />
        {t("settingsHours.allDay")}
      </label>

      <div className="ml-auto flex items-center gap-2">
        <TimeField
          label={t("settingsHours.opens")}
          hour={row.open_hour}
          minutes={row.open_minutes}
          disabled={disabled}
          onChange={(hour, minutes) =>
            onChange({ open_hour: hour, open_minutes: minutes })
          }
        />
        <span className="text-fg-muted">–</span>
        <TimeField
          label={t("settingsHours.closes")}
          hour={row.close_hour}
          minutes={row.close_minutes}
          disabled={disabled}
          onChange={(hour, minutes) =>
            onChange({ close_hour: hour, close_minutes: minutes })
          }
        />
      </div>
    </div>
  );
}

function TimeField({
  label,
  hour,
  minutes,
  disabled,
  onChange,
}: {
  label: string;
  hour: number | null;
  minutes: number | null;
  disabled?: boolean;
  onChange: (hour: number | null, minutes: number | null) => void;
}) {
  const value =
    hour !== null && minutes !== null
      ? `${String(hour).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`
      : "";
  return (
    <label className="flex items-center gap-1.5 text-xs text-fg-muted">
      {label}
      <input
        type="time"
        value={value}
        disabled={disabled}
        onChange={(e) => {
          const raw = e.target.value;
          if (!raw) return onChange(null, null);
          const [h, m] = raw.split(":");
          onChange(Number(h), Number(m));
        }}
        className="glass-field h-9 rounded-control border border-glass bg-field px-2.5 font-numeric text-sm tabular-nums text-fg disabled:opacity-50"
      />
    </label>
  );
}

function toInput(wh: WorkingHour): WorkingHourInput {
  return {
    day_of_week: wh.day_of_week,
    closed_all_day: wh.closed_all_day,
    open_all_day: wh.open_all_day,
    open_hour: wh.open_hour,
    open_minutes: wh.open_minutes,
    close_hour: wh.close_hour,
    close_minutes: wh.close_minutes,
  };
}
