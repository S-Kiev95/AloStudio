import {
  CheckCheck,
  CheckCircle2,
  Clock,
  type LucideIcon,
  XCircle,
} from "lucide-react";

import type { AppointmentStatus } from "@/lib/api/appointments";
import { cn } from "@/lib/utils";

export const APPOINTMENT_STATUS_META: Record<
  AppointmentStatus,
  { label: string; icon: LucideIcon; className: string }
> = {
  scheduled: {
    label: "Programada",
    icon: Clock,
    className: "bg-warning/10 text-warning",
  },
  confirmed: {
    label: "Confirmada",
    icon: CheckCircle2,
    className: "bg-info/10 text-info",
  },
  done: {
    label: "Realizada",
    icon: CheckCheck,
    className: "bg-success/10 text-success",
  },
  cancelled: {
    label: "Cancelada",
    icon: XCircle,
    className: "bg-danger/10 text-danger",
  },
};

export const APPOINTMENT_STATUS_OPTIONS: {
  value: AppointmentStatus;
  label: string;
}[] = [
  { value: "scheduled", label: "Programada" },
  { value: "confirmed", label: "Confirmada" },
  { value: "done", label: "Realizada" },
  { value: "cancelled", label: "Cancelada" },
];

export function AppointmentStatusBadge({
  status,
  className,
}: {
  status: AppointmentStatus;
  className?: string;
}) {
  const meta =
    APPOINTMENT_STATUS_META[status] ?? APPOINTMENT_STATUS_META.scheduled;
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        meta.className,
        className,
      )}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden />
      {meta.label}
    </span>
  );
}
