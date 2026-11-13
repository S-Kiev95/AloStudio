"use client";

import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  List,
  Package,
  Pencil,
  Plus,
  Trash2,
  User as UserIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  addMonthsLocal,
  type CalendarPeriod,
  computePeriodBounds,
  formatCalendarRangeLabel,
  startOfLocalDay,
} from "@/components/publications/calendar-utils";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { selectClassName } from "@/components/ui/select";
import {
  type Appointment,
  type AppointmentStatus,
  useAppointments,
  useDeleteAppointment,
  useUpdateAppointment,
} from "@/lib/api/appointments";

import { AgendaHourlyGrid, AgendaMonthGrid, buildAgendaDays } from "./agenda-calendar";
import { AppointmentDialog } from "./appointment-dialog";
import {
  APPOINTMENT_STATUS_OPTIONS,
  AppointmentStatusBadge,
} from "./status-badge";
import {
  addDaysLocal,
  formatDateTimeLocal,
  formatLocalDateKey,
  startOfWeekMonday,
} from "./week-utils";
import { useLocale, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

type DisplayMode = "calendar" | "list";

const STATUS_FILTERS: {
  value: AppointmentStatus | undefined;
  label: MessageKey;
}[] = [
  { value: undefined, label: "agenda.filters.all" },
  { value: "scheduled", label: "agenda.filters.scheduled" },
  { value: "confirmed", label: "agenda.filters.confirmed" },
  { value: "done", label: "agenda.filters.done" },
  { value: "cancelled", label: "agenda.filters.cancelled" },
];

const NAV_BUTTON =
  "inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon";

export function AgendaView({ accountId, now: nowProp }: { accountId: string; now?: Date }) {
  const t = useT();
  const locale = useLocale();
  const [now, setNow] = useState<Date>(() => nowProp ?? new Date());
  useEffect(() => {
    if (nowProp) return;
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, [nowProp]);

  const [mode, setMode] = useState<DisplayMode>("calendar");
  const [period, setPeriod] = useState<CalendarPeriod>("week");
  const [cursor, setCursor] = useState<Date>(() => startOfWeekMonday(nowProp ?? new Date()));
  const [statusFilter, setStatusFilter] = useState<
    AppointmentStatus | undefined
  >(undefined);
  const [page, setPage] = useState(1);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Appointment | null>(null);
  const [presetStart, setPresetStart] = useState<Date | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const bounds = computePeriodBounds(period, cursor);

  const queryFilters =
    mode === "calendar"
      ? {
          from: bounds.start.toISOString(),
          to: bounds.end.toISOString(),
          status: statusFilter,
        }
      : {
          status: statusFilter,
          page,
        };

  const { data, isLoading, isError } = useAppointments(accountId, queryFilters);
  const updateMutation = useUpdateAppointment(accountId);
  const deleteMutation = useDeleteAppointment(accountId);

  function shiftCursor(direction: -1 | 1) {
    setCursor((prev) => {
      if (period === "day") return addDaysLocal(prev, direction);
      if (period === "week") return addDaysLocal(prev, direction * 7);
      return addMonthsLocal(prev, direction);
    });
  }

  function goToday() {
    const base = nowProp ?? new Date();
    setCursor(period === "week" ? startOfWeekMonday(base) : startOfLocalDay(base));
  }

  function openNew(at?: Date) {
    setEditing(null);
    setPresetStart(at ?? null);
    setDialogOpen(true);
  }

  function openEdit(appt: Appointment) {
    setEditing(appt);
    setPresetStart(null);
    setDialogOpen(true);
  }

  async function handleStatusChange(
    appointment: Appointment,
    newStatus: AppointmentStatus,
  ) {
    setActionError(null);
    try {
      await updateMutation.mutateAsync({
        id: appointment.id,
        patch: { status: newStatus },
      });
    } catch (err) {
      setActionError(
        (err as { message?: string })?.message ??
          t("agenda.statusFailed"),
      );
    }
  }

  async function handleDelete(appointment: Appointment) {
    if (!window.confirm(t("agenda.deleteConfirm", { title: appointment.title }))) return;
    setActionError(null);
    try {
      await deleteMutation.mutateAsync(appointment.id);
    } catch (err) {
      setActionError(
        (err as { message?: string })?.message ?? t("agenda.deleteFailed"),
      );
    }
  }

  const appointments = data ?? [];
  const todayKey = formatLocalDateKey(now);

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader title={t("agenda.title")} description={t("agenda.subtitle")} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {mode === "calendar" ? (
            <>
              <div className="inline-flex items-center rounded-control border border-glass bg-field p-0.5">
                <button
                  type="button"
                  aria-label={t("publications.calendar.prevPeriod")}
                  onClick={() => shiftCursor(-1)}
                  className={NAV_BUTTON}
                >
                  <ChevronLeft className="h-4 w-4" aria-hidden />
                </button>
                <span className="px-3 font-numeric text-sm font-medium tabular-nums text-fg">
                  {formatCalendarRangeLabel(period, cursor, locale)}
                </span>
                <button
                  type="button"
                  aria-label={t("publications.calendar.nextPeriod")}
                  onClick={() => shiftCursor(1)}
                  className={NAV_BUTTON}
                >
                  <ChevronRight className="h-4 w-4" aria-hidden />
                </button>
              </div>
              <Button type="button" size="sm" variant="simple" onClick={goToday}>
                {t("agenda.today")}
              </Button>
            </>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {mode === "calendar" ? (
            <SegmentedControl
              ariaLabel={t("publications.calendar.range")}
              size="sm"
              value={period}
              onValueChange={(next) => {
                setPeriod(next);
                if (next === "week") setCursor((c) => startOfWeekMonday(c));
              }}
              options={[
                { value: "day" as CalendarPeriod, label: t("publications.calendar.day") },
                { value: "week" as CalendarPeriod, label: t("agenda.week") },
                { value: "month" as CalendarPeriod, label: t("publications.calendar.month") },
              ]}
            />
          ) : null}
          <SegmentedControl
            ariaLabel={t("agenda.viewMode")}
            size="sm"
            value={mode}
            onValueChange={(next) => {
              setMode(next);
              if (next === "list") setPage(1);
            }}
            options={[
              {
                value: "calendar" as DisplayMode,
                label: (
                  <>
                    <CalendarDays className="h-3.5 w-3.5" aria-hidden />
                    {t("nav.calendar")}
                  </>
                ),
              },
              {
                value: "list" as DisplayMode,
                label: (
                  <>
                    <List className="h-3.5 w-3.5" aria-hidden />
                    {t("agenda.list")}
                  </>
                ),
              },
            ]}
          />
          <Button size="sm" onClick={() => openNew()}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("agenda.newAppointment")}
          </Button>
        </div>
      </div>

      {/* Filtro por estado */}
      <SegmentedControl
        ariaLabel={t("agenda.filterByStatus")}
        size="sm"
        value={statusFilter}
        onValueChange={(next) => {
          setStatusFilter(next);
          setPage(1);
        }}
        options={STATUS_FILTERS.map((o) => ({ ...o, label: t(o.label) }))}
      />

      {actionError ? (
        <p role="alert" className="text-sm text-danger">
          {actionError}
        </p>
      ) : null}

      {isLoading ? (
        <div className="rounded-md border border-glass bg-surface p-8 text-center text-sm text-fg-muted">
          {t("agenda.loading")}
        </div>
      ) : isError ? (
        <div
          role="alert"
          className="rounded-md border border-glass bg-surface p-8 text-center text-sm text-danger"
        >
          {t("agenda.loadFailed")}
        </div>
      ) : mode === "calendar" && period === "month" ? (
        <AgendaMonthGrid
          days={buildAgendaDays(bounds.start, 42, appointments, cursor.getMonth(), locale)}
          todayKey={todayKey}
          onCreateOn={(d) => openNew(new Date(d.getFullYear(), d.getMonth(), d.getDate(), 10))}
          onSelect={openEdit}
        />
      ) : mode === "calendar" ? (
        <AgendaHourlyGrid
          days={buildAgendaDays(bounds.start, period === "day" ? 1 : 7, appointments, undefined, locale)}
          todayKey={todayKey}
          now={now}
          showNowLine={now >= bounds.start && now < bounds.end}
          onCreateAt={(d, hour) => openNew(new Date(d.getFullYear(), d.getMonth(), d.getDate(), hour))}
          onSelect={openEdit}
        />
      ) : appointments.length === 0 ? (
        <div className="rounded-md border border-glass bg-surface p-8 text-center text-sm text-fg-muted">
          {t("agenda.emptyFilter")}
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-glass bg-surface">
          <ul className="divide-y divide-glass">
            {appointments.map((appt) => {
              const contactLabel =
                appt.contact?.name?.trim() ||
                appt.contact?.email?.trim() ||
                appt.contact?.phone_number?.trim() ||
                t("conversations.contact.fallbackName", { id: appt.contact_id });

              return (
                <li
                  key={appt.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-hover-glass"
                >
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-fg">
                        {appt.title}
                      </span>
                      <AppointmentStatusBadge status={appt.status} />
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
                      <span className="font-numeric font-medium tabular-nums text-fg">
                        {formatDateTimeLocal(appt.starts_at, locale)}
                      </span>
                      <Link
                        href={`/accounts/${accountId}/contacts/${appt.contact_id}`}
                        className="inline-flex items-center gap-1 hover:text-fg hover:underline"
                      >
                        <UserIcon className="h-3 w-3" aria-hidden />
                        {contactLabel}
                      </Link>
                      {appt.product ? (
                        <span className="inline-flex items-center gap-1">
                          <Package className="h-3 w-3" aria-hidden />
                          {appt.product.name}
                        </span>
                      ) : null}
                    </div>
                    {appt.notes ? (
                      <p className="text-xs text-fg-muted">{appt.notes}</p>
                    ) : null}
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      aria-label={t("agenda.statusOf", { title: appt.title })}
                      value={appt.status}
                      onChange={(e) =>
                        handleStatusChange(
                          appt,
                          e.target.value as AppointmentStatus,
                        )
                      }
                      className={selectClassName("sm")}
                    >
                      {APPOINTMENT_STATUS_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {t(opt.label)}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      aria-label={t("agenda.editItem", { title: appt.title })}
                      title={t("actions.edit")}
                      onClick={() => openEdit(appt)}
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                    >
                      <Pencil className="h-4 w-4" aria-hidden />
                    </button>
                    <button
                      type="button"
                      aria-label={t("agenda.deleteItem", { title: appt.title })}
                      title={t("actions.delete")}
                      onClick={() => handleDelete(appt)}
                      disabled={deleteMutation.isPending}
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>

          {page > 1 || appointments.length >= 50 ? (
            <div className="flex items-center justify-between border-t border-glass px-4 py-2.5 text-xs text-fg-muted">
              <span className="font-numeric tabular-nums">
                {t("actions.page", { n: page })}
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  {t("actions.previous")}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={appointments.length < 50}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {t("actions.next")}
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      )}

      <AppointmentDialog
        accountId={accountId}
        open={dialogOpen}
        onClose={() => {
          setDialogOpen(false);
          setEditing(null);
          setPresetStart(null);
        }}
        initial={editing}
        defaultStartsAt={presetStart}
      />
    </div>
  );
}
