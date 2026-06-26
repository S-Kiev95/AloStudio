"use client";

import {
  ArrowLeft,
  Facebook,
  Globe,
  Instagram,
  type LucideIcon,
  Mail,
  MessageCircle,
  MessageSquare,
  Phone,
  Send,
  Webhook,
} from "lucide-react";
import Link from "next/link";

import { CHANNEL_CATALOG } from "@/lib/inboxes/channel-catalog";

const ICON: Record<string, LucideIcon> = {
  telegram: Send,
  whatsapp: MessageCircle,
  sms: MessageSquare,
  twilio_sms: Phone,
  email: Mail,
  web_widget: Globe,
  api: Webhook,
  facebook: Facebook,
  instagram: Instagram,
};

export function ChannelPicker({ accountId }: { accountId: string }) {
  return (
    <div className="space-y-4">
      <div>
        <Link
          href={`/accounts/${accountId}/settings/inboxes`}
          className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Volver
        </Link>
        <h2 className="mt-2 text-xl font-semibold text-fg">Elegí un canal</h2>
        <p className="text-sm text-fg-muted">
          Conectá un canal de mensajería a tu cuenta.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CHANNEL_CATALOG.map((c) => {
          const Icon = ICON[c.type] ?? Webhook;
          return (
            <Link
              key={c.type}
              href={`/accounts/${accountId}/settings/inboxes/new/${c.type}`}
              className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4 transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary">
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <span className="font-medium text-fg">{c.label}</span>
              <span className="text-xs text-fg-muted">{c.blurb}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
