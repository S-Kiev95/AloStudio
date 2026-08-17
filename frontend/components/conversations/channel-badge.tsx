import {
  AtSign,
  Facebook,
  Globe,
  Instagram,
  type LucideIcon,
  MessageCircle,
  MessageSquare,
  Plug,
  Send,
} from "lucide-react";

import { cn } from "@/lib/utils";

/** The channel discriminator the API returns, e.g. `Channel::Instagram`. */
type ChannelType = string | null | undefined;

const CHANNELS: Record<string, { label: string; icon: LucideIcon; cls: string }> =
  {
    "Channel::Instagram": {
      label: "Instagram",
      icon: Instagram,
      cls: "text-[#E1306C]",
    },
    "Channel::Whatsapp": {
      label: "WhatsApp",
      icon: MessageCircle,
      cls: "text-[#25D366]",
    },
    "Channel::FacebookPage": {
      label: "Facebook",
      icon: Facebook,
      cls: "text-[#1877F2]",
    },
    "Channel::Telegram": { label: "Telegram", icon: Send, cls: "text-[#29A9EB]" },
    "Channel::Email": { label: "Email", icon: AtSign, cls: "text-fg-muted" },
    "Channel::Sms": { label: "SMS", icon: MessageSquare, cls: "text-fg-muted" },
    "Channel::TwilioSms": {
      label: "SMS",
      icon: MessageSquare,
      cls: "text-fg-muted",
    },
    "Channel::WebWidget": { label: "Web", icon: Globe, cls: "text-fg-muted" },
    "Channel::Api": { label: "API", icon: Plug, cls: "text-fg-muted" },
  };

export function channelLabel(channel: ChannelType): string | null {
  if (!channel) return null;
  return CHANNELS[channel]?.label ?? channel.split("::").pop() ?? null;
}

/** Where a conversation came from, at a glance.
 *
 *  Icon-only in the list: the row already carries the name, the preview and
 *  the time, and a text badge on every row would compete with all three.
 *  The accessible name carries the channel for anyone not reading colour. */
export function ChannelBadge({
  channel,
  className,
}: {
  channel: ChannelType;
  className?: string;
}) {
  if (!channel) return null;
  const known = CHANNELS[channel];
  const label = channelLabel(channel);
  const Icon = known?.icon ?? Plug;

  return (
    <span
      title={label ?? undefined}
      aria-label={label ?? undefined}
      role="img"
      className={cn("inline-flex shrink-0 items-center", className)}
    >
      <Icon className={cn("h-3.5 w-3.5", known?.cls ?? "text-fg-muted")} aria-hidden />
    </span>
  );
}
