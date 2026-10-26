"use client";

import {
  Calendar as CalendarIcon,
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
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  type Appointment,
  type AppointmentStatus,
  useAppointments,
  useDeleteAppointment,
  useUpdateAppointment,
} from "@/lib/api/appointments";
import { cn } from "@/lib/utils";

import { AppointmentDialog } from "./appointment-dialog";
import {
  APPOINTMENT_STATUS_OPTIONS,
  AppointmentStatusBadge,
} from "./status-badge";
import {
  addDaysLocal,
  endOfWeekExclusive,
  formatDateTimeLocal,
  formatWeekRangeLabel,
  startOfWeekMonday,
} from "./week-utils";
import { WeekView } from "./week-view";

type ViewMode = "week" | "list";

const STATUS_FILTERS: {
  key: AppointmentStatus | undefined;
  label: string;
}[] = [
  { key: undefined, label: "Todas" },
  { key: "scheduled", label: "Programadas" },
  { key: "confirmed", label: "Confirmadas" },
  { key: "done", label: "Realizadas" },
  { key: "cancelled", label: "Canceladas" },
];

export function AgendaView({ accountId }: { accountId: string }) {
  const [mode, setMode] = useState<ViewMode>("week");
  const [weekStart, setWeekStart] = useState<Date>(() =>
    startOfWeekMonday(new Date()),
  );
  const [statusFilter, setStatusFilter] = useState<
    AppointmentStatus | undefined
  >(undefined);
  const [page, setPage] = useState(1);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Appointment | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const weekEnd = endOfWeekExclusive(weekStart);

  const queryFilters =
    mode === "week"
      ? {
          from: weekStart.toISOString(),
          to: weekEnd.toISOString(),
          status: statusFilter,
        }
      : {
          status: statusFilter,
          page,
        };

  const { data, isLoading, isError } = useAppointments(accountId, queryFilters);
  const updateMutation = useUpdateAppointment(accountId);
  const deleteMutation = useDeleteAppointment(accountId);

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
          "No se pudo actualizar el estado.",
      );
    }
  }

  async function handleDelete(appointment: Appointment) {
    if (!window.confirm(`¿Eliminar la cita "${appointment.title}"?`)) return;
    setActionError(null);
    try {
      await deleteMutation.mutateAsync(appointment.id);
    } catch (err) {
      setActionError(
        (err as { message?: string })?.message ?? "No se pudo eliminar la cita.",
      );
    }
  }

  const appointments = data ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-fg">Agenda</h1>
          <p className="text-sm text-fg-muted">
            Citas y turnos programados con tus contactos.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4" aria-hidden />
          Nueva cita
        </Button>
      </div>

      {/* Controles de vista y navegación semanal */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1 rounded-lg border border-border bg-surface p-1">
          <button
            type="button"
            aria-pressed={mode === "week"}
            onClick={() => setMode("week")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              mode === "week"
                ? "bg-surface-2 font-semibold text-fg"
                : "text-fg-muted hover:text-fg",
            )}
          >
            <CalendarIcon className="h-4 w-4" aria-hidden />
            Semana
          </button>
          <button
            type="button"
            aria-pressed={mode === "list"}
            onClick={() => {
              setMode("list");
              setPage(1);
            }}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              mode === "list"
                ? "bg-surface-2 font-semibold text-fg"
                : "text-fg-muted hover:text-fg",
            )}
          >
            <List className="h-4 w-4" aria-hidden />
            Lista
          </button>
        </div>

        {mode === "week" ? (
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              aria-label="Semana anterior"
              onClick={() => setWeekStart((w) => addDaysLocal(w, -7))}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => setWeekStart(startOfWeekMonday(new Date()))}
            >
              Hoy
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              aria-label="Semana siguiente"
              onClick={() => setWeekStart((w) => addDaysLocal(w, 7))}
            >
              <ChevronRight className="h-4 w-4" aria-hidden />
            </Button>
            <span className="ml-1 text-sm font-medium tabular-nums text-fg">
              {formatWeekRangeLabel(weekStart)}
            </span>
          </div>
        ) : null}
      </div>

      {/* Filtro por estado */}
      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            aria-pressed={statusFilter === f.key}
            onClick={() => {
              setStatusFilter(f.key);
              setPage(1);
            }}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              statusFilter === f.key
                ? "bg-surface-2 font-semibold text-fg"
                : "border border-border bg-surface text-fg hover:bg-surface-2",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {actionError ? (
        <p role="alert" className="text-sm text-danger">
          {actionError}
        </p>
      ) : null}

      {isLoading ? (
        <div className="rounded-xl border border-border bg-surface p-8 text-center text-sm text-fg-muted shadow-sm">
          Cargando citas…
        </div>
      ) : isError ? (
        <div
          role="alert"
          className="rounded-xl border border-border bg-surface p-8 text-center text-sm text-danger shadow-sm"
        >
          No se pudieron cargar las citas.
        </div>
      ) : mode === "week" ? (
        <WeekView
          weekStart={weekStart}
          appointments={appointments}
          onEdit={(appt) => {
            setEditing(appt);
            setDialogOpen(true);
          }}
          onStatusChange={handleStatusChange}
          onDelete={handleDelete}
        />
      ) : appointments.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface p-8 text-center text-sm text-fg-muted shadow-sm">
          No hay citas para el filtro seleccionado.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
          <ul className="divide-y divide-border">
            {appointments.map((appt) => {
              const contactLabel =
                appt.contact?.name?.trim() ||
                appt.contact?.email?.trim() ||
                appt.contact?.phone_number?.trim() ||
                `Contacto #${appt.contact_id}`;

              return (
                <li
                  key={appt.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-surface-2"
                >
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-fg">
                        {appt.title}
                      </span>
                      <AppointmentStatusBadge status={appt.status} />
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
                      <span className="font-medium tabular-nums text-fg">
                        {formatDateTimeLocal(appt.starts_at)}
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
                      aria-label={`Estado de ${appt.title}`}
                      value={appt.status}
                      onChange={(e) =>
                        handleStatusChange(
                          appt,
                          e.target.value as AppointmentStatus,
                        )
                      }
                      className="h-9 rounded-md border border-border bg-surface px-2 text-xs text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
                      onClick={() => {
                        setEditing(appt);
                        setDialogOpen(true);
                      }}
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Pencil className="h-4 w-4" aria-hidden />
                    </button>
                    <button
                      type="button"
                      aria-label={`Eliminar ${appt.title}`}
                      title="Eliminar"
                      onClick={() => handleDelete(appt)}
                      disabled={deleteMutation.isPending}
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>

          {page > 1 || appointments.length >= 50 ? (
            <div className="flex items-center justify-between border-t border-border px-4 py-2.5 text-xs text-fg-muted">
              <span>Página {page}</span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Anterior
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={appointments.length < 50}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Siguiente
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
        }}
        initial={editing}
      />
    </div>
  );
}
