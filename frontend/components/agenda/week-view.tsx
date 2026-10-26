"use client";

import { Package, Pencil, Trash2, User as UserIcon } from "lucide-react";

import type { Appointment, AppointmentStatus } from "@/lib/api/appointments";
import { cn } from "@/lib/utils";

import {
  APPOINTMENT_STATUS_OPTIONS,
  AppointmentStatusBadge,
} from "./status-badge";
import {
  formatLocalDateKey,
  formatTimeRange,
  groupAppointmentsByDay,
} from "./week-utils";

export function WeekView({
  weekStart,
  appointments,
  today = new Date(),
  onEdit,
  onStatusChange,
  onDelete,
}: {
  weekStart: Date;
  appointments: Appointment[];
  today?: Date;
  onEdit: (appointment: Appointment) => void;
  onStatusChange: (appointment: Appointment, status: AppointmentStatus) => void;
  onDelete: (appointment: Appointment) => void;
}) {
  const buckets = groupAppointmentsByDay(weekStart, appointments);
  const todayKey = formatLocalDateKey(today);

  return (
    <div
      className="grid grid-cols-1 gap-3 lg:grid-cols-7"
      data-testid="agenda-week-grid"
    >
      {buckets.map((day) => {
        const isToday = day.key === todayKey;
        return (
          <section
            key={day.key}
            aria-label={`${day.longName} ${day.dayNumber}`}
            data-day-key={day.key}
            className={cn(
              "flex min-h-48 flex-col rounded-xl border bg-surface shadow-sm",
              isToday ? "border-primary" : "border-border",
            )}
          >
            <header className="flex items-center justify-between border-b border-border px-3 py-2">
              <div className="flex items-baseline gap-1.5">
                <span className="text-xs font-semibold uppercase text-fg-muted">
                  {day.shortName}
                </span>
                <span
                  className={cn(
                    "text-sm font-semibold tabular-nums",
                    isToday ? "text-primary" : "text-fg",
                  )}
                >
                  {day.dayNumber}
                </span>
              </div>
              {isToday ? (
                <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-fg">
                  Hoy
                </span>
              ) : null}
            </header>

            <div className="flex-1 space-y-2 p-2">
              {day.items.length === 0 ? (
                <p className="py-6 text-center text-xs text-fg-muted">
                  Sin citas
                </p>
              ) : (
                day.items.map((appt) => {
                  const contactLabel =
                    appt.contact?.name?.trim() ||
                    appt.contact?.email?.trim() ||
                    appt.contact?.phone_number?.trim() ||
                    `Contacto #${appt.contact_id}`;

                  return (
                    <article
                      key={appt.id}
                      className="space-y-1.5 rounded-lg border border-border bg-surface-2 p-2.5 text-xs"
                    >
                      <div className="flex items-start justify-between gap-1">
                        <span className="font-semibold tabular-nums text-fg">
                          {formatTimeRange(appt.starts_at, appt.ends_at)}
                        </span>
                        <AppointmentStatusBadge status={appt.status} />
                      </div>

                      <p className="font-medium text-fg break-words">
                        {appt.title}
                      </p>

                      <p className="flex items-center gap-1 truncate text-fg-muted">
                        <UserIcon className="h-3 w-3 shrink-0" aria-hidden />
                        <span className="truncate">{contactLabel}</span>
                      </p>

                      {appt.product ? (
                        <p className="flex items-center gap-1 truncate text-fg-muted">
                          <Package className="h-3 w-3 shrink-0" aria-hidden />
                          <span className="truncate">{appt.product.name}</span>
                        </p>
                      ) : null}

                      <div className="flex items-center justify-between gap-1 pt-1">
                        <select
                          aria-label={`Estado de ${appt.title}`}
                          value={appt.status}
                          onChange={(e) =>
                            onStatusChange(
                              appt,
                              e.target.value as AppointmentStatus,
                            )
                          }
                          className="h-7 min-w-0 flex-1 rounded border border-border bg-surface px-1.5 text-xs text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {APPOINTMENT_STATUS_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          aria-label={`Editar ${appt.title}`}
                          title="Editar"
                          onClick={() => onEdit(appt)}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-fg-muted hover:bg-surface hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <Pencil className="h-3.5 w-3.5" aria-hidden />
                        </button>
                        <button
                          type="button"
                          aria-label={`Eliminar ${appt.title}`}
                          title="Eliminar"
                          onClick={() => onDelete(appt)}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-fg-muted hover:bg-surface hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <Trash2 className="h-3.5 w-3.5" aria-hidden />
                        </button>
                      </div>
                    </article>
                  );
                })
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
