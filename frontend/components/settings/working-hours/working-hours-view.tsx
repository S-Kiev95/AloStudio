"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useInboxes } from "@/lib/api/inboxes";
import {
  type WorkingHour,
  type WorkingHourInput,
  useBulkUpdateWorkingHours,
  useInboxWorkingHours,
} from "@/lib/api/working-hours";
import { cn } from "@/lib/utils";

const DAYS_ES = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function WorkingHoursView({ accountId }: { accountId: string }) {
  const inboxes = useInboxes(accountId);
  const [inboxId, setInboxId] = useState<number | null>(null);

  // Pick the first inbox by default when the list loads.
  useEffect(() => {
    if (inboxId === null && inboxes.data?.length) {
      setInboxId(inboxes.data[0].id);
    }
  }, [inboxId, inboxes.data]);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-fg">Horarios laborales</h2>
        <div className="flex items-center gap-2">
          <label htmlFor="wh-inbox" className="text-sm text-fg-muted">
            Bandeja
          </label>
          <select
            id="wh-inbox"
            className={cn(selectClass, "w-auto min-w-44")}
            value={inboxId ?? ""}
            onChange={(e) => setInboxId(Number(e.target.value) || null)}
            disabled={inboxes.isLoading}
          >
            <option value="">Elegí una bandeja…</option>
            {inboxes.data?.map((ib) => (
              <option key={ib.id} value={ib.id}>
                {ib.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {inboxes.isLoading ? (
        <p className="text-sm text-fg-muted">Cargando bandejas…</p>
      ) : inboxes.isError ? (
        <p role="alert" className="text-sm text-danger">
          No se pudieron cargar las bandejas.
        </p>
      ) : (inboxes.data?.length ?? 0) === 0 ? (
        <p className="text-sm text-fg-muted">
          No hay bandejas conectadas todavía.
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
        (e as { message?: string })?.message ?? "No se pudo guardar el horario.",
      );
    }
  }

  if (isLoading) {
    return <p className="text-sm text-fg-muted">Cargando horario…</p>;
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        No se pudo cargar el horario.
      </p>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Horario semanal</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {saved ? (
          <p className="text-sm text-success">Cambios guardados.</p>
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
            Guardar
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
  const disabled = row.closed_all_day || row.open_all_day;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface p-3">
      <p className="w-24 shrink-0 text-sm font-medium text-fg">
        {DAYS_ES[row.day_of_week] ?? `Día ${row.day_of_week}`}
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
        />
        Cerrado
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
        />
        24 horas
      </label>

      <div className="ml-auto flex items-center gap-2">
        <TimeField
          label="Abre"
          hour={row.open_hour}
          minutes={row.open_minutes}
          disabled={disabled}
          onChange={(hour, minutes) =>
            onChange({ open_hour: hour, open_minutes: minutes })
          }
        />
        <span className="text-fg-muted">–</span>
        <TimeField
          label="Cierra"
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
        className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-fg disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
