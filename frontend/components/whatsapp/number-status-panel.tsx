"use client";

import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useWhatsappPhoneStatus } from "@/lib/api/whatsapp-business";
import { cn } from "@/lib/utils";

type Tone = "good" | "warn" | "bad" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  good: "border-success text-success",
  warn: "border-warning text-warning",
  bad: "border-danger text-danger",
  neutral: "border-glass text-fg-muted",
};

const QUALITY: Record<string, { label: string; tone: Tone }> = {
  GREEN: { label: "Alta", tone: "good" },
  YELLOW: { label: "Media", tone: "warn" },
  RED: { label: "Baja", tone: "bad" },
};

const NAME_STATUS: Record<string, { label: string; tone: Tone }> = {
  APPROVED: { label: "Aprobado", tone: "good" },
  AVAILABLE_WITHOUT_REVIEW: { label: "Aprobado", tone: "good" },
  PENDING_REVIEW: { label: "En revisión", tone: "warn" },
  DECLINED: { label: "Rechazado", tone: "bad" },
  EXPIRED: { label: "Vencido", tone: "bad" },
  NONE: { label: "Sin revisar", tone: "neutral" },
};

const CONNECTION: Record<string, { label: string; tone: Tone }> = {
  CONNECTED: { label: "Conectado", tone: "good" },
  PENDING: { label: "Pendiente", tone: "warn" },
  MIGRATED: { label: "Migrado", tone: "warn" },
  FLAGGED: { label: "Marcado por Meta", tone: "warn" },
  RESTRICTED: { label: "Restringido", tone: "bad" },
  RATE_LIMITED: { label: "Limitado", tone: "bad" },
  DISCONNECTED: { label: "Desconectado", tone: "bad" },
  OFFLINE: { label: "Sin conexión", tone: "bad" },
  BANNED: { label: "Bloqueado", tone: "bad" },
  DELETED: { label: "Borrado", tone: "bad" },
};

/** `TIER_1K` → "1.000 contactos nuevos por día". */
export function messagingLimitLabel(limit: string | null): string | null {
  if (!limit) return null;
  if (/UNLIMITED/i.test(limit)) return "Sin límite";
  const match = /(\d+)\s*(K)?/i.exec(limit);
  if (!match) return limit;
  const n = Number(match[1]) * (match[2] ? 1000 : 1);
  return `${n.toLocaleString("es-UY")} contactos nuevos por día`;
}

function Fact({
  title,
  value,
  tone = "neutral",
  hint,
}: {
  title: string;
  value: string | null;
  tone?: Tone;
  hint: string;
}) {
  return (
    <div className="rounded-xl border border-glass bg-surface p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">{title}</p>
      <p
        className={cn(
          "mt-2 inline-flex rounded-pill border px-2.5 py-0.5 text-sm font-semibold",
          TONE_CLASS[value ? tone : "neutral"],
        )}
      >
        {value ?? "Sin dato"}
      </p>
      <p className="mt-2 text-xs leading-snug text-fg-muted">{hint}</p>
    </div>
  );
}

/** The number's state on Meta: who it shows as, its quality and how many
 *  new conversations a day it may start. */
export function NumberStatusPanel({
  accountId,
  inboxId,
}: {
  accountId: string;
  inboxId: number;
}) {
  const q = useWhatsappPhoneStatus(accountId, inboxId);

  if (q.isLoading) return <p className="text-sm text-fg-muted">Consultando a Meta…</p>;
  if (q.isError || !q.data) {
    return (
      <p role="alert" className="text-sm text-danger">
        {(q.error as Error | null)?.message ?? "No se pudo consultar el número en Meta."}
      </p>
    );
  }
  const s = q.data;
  const quality = QUALITY[(s.quality_rating ?? "").toUpperCase()];
  const name = NAME_STATUS[(s.name_status ?? "").toUpperCase()];
  const connection = CONNECTION[(s.status ?? "").toUpperCase()];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold text-fg">{s.verified_name ?? "Sin nombre"}</p>
          <p className="text-sm text-fg-muted">
            {s.display_phone_number ?? s.phone_number ?? ""}
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={q.isFetching}
          onClick={() => void q.refetch()}
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          Actualizar
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Fact
          title="Conexión"
          value={connection?.label ?? s.status}
          tone={connection?.tone}
          hint="Si no dice Conectado, los mensajes no salen: revisalo en el administrador de WhatsApp de Meta."
        />
        <Fact
          title="Calidad"
          value={quality?.label ?? s.quality_rating}
          tone={quality?.tone}
          hint="Baja cuando muchos contactos bloquean o reportan los mensajes. Con calidad baja, Meta puede limitar el número."
        />
        <Fact
          title="Límite por día"
          value={messagingLimitLabel(s.messaging_limit)}
          hint="Cuántas conversaciones nuevas podés empezar con plantillas en 24 h. Sube solo si mandás mucho con buena calidad."
        />
        <Fact
          title="Nombre visible"
          value={name?.label ?? s.name_status}
          tone={name?.tone}
          hint="El nombre que ven los contactos arriba del chat. Se cambia en el administrador de WhatsApp de Meta."
        />
      </div>

      {quality?.tone === "bad" || connection?.tone === "bad" ? (
        <p
          role="alert"
          className="rounded-lg border border-danger px-3 py-2 text-sm text-danger"
        >
          Meta marcó un problema con este número. Antes de un envío masivo,
          esperá a que la calidad vuelva a subir: mandar más puede terminar en
          un bloqueo.
        </p>
      ) : null}
    </div>
  );
}
