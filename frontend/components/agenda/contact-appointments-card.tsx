"use client";

import { CalendarPlus, Package, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type Appointment,
  type AppointmentContact,
  type AppointmentStatus,
  useAppointments,
  useDeleteAppointment,
  useUpdateAppointment,
} from "@/lib/api/appointments";

import { AppointmentDialog } from "./appointment-dialog";
import {
  APPOINTMENT_STATUS_OPTIONS,
  AppointmentStatusBadge,
} from "./status-badge";
import { formatDateTimeLocal } from "./week-utils";

export function ContactAppointmentsCard({
  accountId,
  contact,
}: {
  accountId: string;
  contact: AppointmentContact;
}) {
  const [sinceIso] = useState(() => new Date().toISOString());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Appointment | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, isError } = useAppointments(accountId, {
    contact_id: contact.id,
    from: sinceIso,
  });
  const updateMutation = useUpdateAppointment(accountId);
  const deleteMutation = useDeleteAppointment(accountId);

  const upcoming = data ?? [];

  async function handleStatusChange(
    appt: Appointment,
    newStatus: AppointmentStatus,
  ) {
    setError(null);
    try {
      await updateMutation.mutateAsync({
        id: appt.id,
        patch: { status: newStatus },
      });
    } catch (err) {
      setError(
        (err as { message?: string })?.message ??
          "No se pudo cambiar el estado.",
      );
    }
  }

  async function handleDelete(appt: Appointment) {
    if (!window.confirm(`¿Eliminar la cita "${appt.title}"?`)) return;
    setError(null);
    try {
      await deleteMutation.mutateAsync(appt.id);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ??
          "No se pudo eliminar la cita.",
      );
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>Próximas citas</CardTitle>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
        >
          <CalendarPlus className="h-4 w-4" aria-hidden />
          Agendar cita
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}

        {isLoading ? (
          <p className="text-sm text-fg-muted">Cargando citas…</p>
        ) : isError ? (
          <p role="alert" className="text-sm text-danger">
            No se pudieron cargar las citas del contacto.
          </p>
        ) : upcoming.length === 0 ? (
          <p className="text-sm text-fg-muted">
            No hay próximas citas agendadas para este contacto.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {upcoming.map((appt) => (
              <li
                key={appt.id}
                className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5"
              >
                <div className="min-w-0 flex-1 space-y-0.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-fg">
                      {appt.title}
                    </span>
                    <AppointmentStatusBadge status={appt.status} />
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
                    <span className="tabular-nums text-fg">
                      {formatDateTimeLocal(appt.starts_at)}
                    </span>
                    {appt.product ? (
                      <span className="inline-flex items-center gap-1">
                        <Package className="h-3 w-3" aria-hidden />
                        {appt.product.name}
                      </span>
                    ) : null}
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <select
                    aria-label={`Estado de ${appt.title}`}
                    value={appt.status}
                    onChange={(e) =>
                      handleStatusChange(
                        appt,
                        e.target.value as AppointmentStatus,
                      )
                    }
                    className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Pencil className="h-3.5 w-3.5" aria-hidden />
                  </button>
                  <button
                    type="button"
                    aria-label={`Eliminar ${appt.title}`}
                    title="Eliminar"
                    onClick={() => handleDelete(appt)}
                    disabled={deleteMutation.isPending}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        <AppointmentDialog
          accountId={accountId}
          open={dialogOpen}
          onClose={() => {
            setDialogOpen(false);
            setEditing(null);
          }}
          initial={editing}
          presetContact={contact}
        />
      </CardContent>
    </Card>
  );
}
