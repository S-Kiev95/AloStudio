import {
  CheckCheck,
  CheckCircle2,
  Clock,
  type LucideIcon,
  XCircle,
} from "lucide-react";

import type { AppointmentStatus } from "@/lib/api/appointments";
import { cn } from "@/lib/utils";
import type { MessageKey } from "@/lib/i18n/translate";
import { useT } from "@/lib/i18n/provider";

export const APPOINTMENT_STATUS_META: Record<
  AppointmentStatus,
  { label: MessageKey; icon: LucideIcon; className: string }
> = {
  scheduled: {
    label: "agenda.status.scheduled",
    icon: Clock,
    className: "bg-warning/10 text-warning",
  },
  confirmed: {
    label: "agenda.status.confirmed",
    icon: CheckCircle2,
    className: "bg-info/10 text-info",
  },
  done: {
    label: "agenda.status.done",
    icon: CheckCheck,
    className: "bg-success/10 text-success",
  },
  cancelled: {
    label: "agenda.status.cancelled",
    icon: XCircle,
    className: "bg-danger/10 text-danger",
  },
};

export const APPOINTMENT_STATUS_OPTIONS: {
  value: AppointmentStatus;
  label: MessageKey;
}[] = [
  { value: "scheduled", label: "agenda.status.scheduled" },
  { value: "confirmed", label: "agenda.status.confirmed" },
  { value: "done", label: "agenda.status.done" },
  { value: "cancelled", label: "agenda.status.cancelled" },
];

export function AppointmentStatusBadge({
  status,
  className,
}: {
  status: AppointmentStatus;
  className?: string;
}) {
  const t = useT();
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
      {t(meta.label)}
    </span>
  );
}
