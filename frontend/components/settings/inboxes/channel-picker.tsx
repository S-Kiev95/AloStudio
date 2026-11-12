"use client";

import {
  ArrowLeft,
  Globe,
  Mail,
  MessageSquare,
  Phone,
  Webhook,
} from "lucide-react";
import Link from "next/link";

import {
  type IconComponent,
  Instagram,
  Messenger,
  Telegram,
  WhatsApp,
} from "@/components/ui/brand-icons";
import { CHANNEL_CATALOG } from "@/lib/inboxes/channel-catalog";
import { useT } from "@/lib/i18n/provider";

const ICON: Record<string, IconComponent> = {
  telegram: Telegram,
  whatsapp: WhatsApp,
  sms: MessageSquare,
  twilio_sms: Phone,
  email: Mail,
  web_widget: Globe,
  api: Webhook,
  facebook: Messenger,
  instagram: Instagram,
};

export function ChannelPicker({ accountId }: { accountId: string }) {
  const t = useT();
  return (
    <div className="space-y-4">
      <div>
        <Link
          href={`/accounts/${accountId}/settings/inboxes`}
          className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t("actions.back")}
        </Link>
        <h2 className="mt-2 text-xl font-medium text-fg">{t("settingsInboxes.chooseChannel")}</h2>
        <p className="text-sm text-fg-muted">
          {t("settingsInboxes.chooseChannelHint")}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CHANNEL_CATALOG.map((c) => {
          const Icon = ICON[c.type] ?? Webhook;
          return (
            <Link
              key={c.type}
              href={`/accounts/${accountId}/settings/inboxes/new/${c.type}`}
              className="flex flex-col gap-2 rounded-md border border-glass bg-surface p-4 transition-colors hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon"
            >
              <span className="grid h-10 w-10 place-items-center rounded-md bg-focused text-lit">
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
