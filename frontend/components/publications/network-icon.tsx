import {
  AtSign,
  Facebook,
  Globe,
  Instagram,
  type LucideIcon,
  MessageSquare,
  Send,
} from "lucide-react";

import { Avatar } from "@/components/ui/avatar";
import type { Channel } from "@/lib/api/publications";
import { cn } from "@/lib/utils";

const KNOWN_NETWORKS: Record<
  string,
  { label: string; icon: LucideIcon; colorClass: string }
> = {
  instagram: {
    label: "Instagram",
    icon: Instagram,
    colorClass: "text-[#E1306C]",
  },
  facebook_page: {
    label: "Facebook",
    icon: Facebook,
    colorClass: "text-[#1877F2]",
  },
  threads: {
    label: "Threads",
    icon: AtSign,
    colorClass: "text-fg",
  },
  telegram: {
    label: "Telegram",
    icon: Send,
    colorClass: "text-[#29A9EB]",
  },
  discord: {
    label: "Discord",
    icon: MessageSquare,
    colorClass: "text-[#5865F2]",
  },
};

export function networkLabel(network: string): string {
  return KNOWN_NETWORKS[network]?.label ?? network;
}

export function channelDisplayName(channel: Channel): string {
  return (
    channel.name?.trim() ||
    (channel.username ? `@${channel.username}` : null) ||
    networkLabel(channel.network)
  );
}

export function NetworkIcon({
  network,
  className,
}: {
  network: string;
  className?: string;
}) {
  const known = KNOWN_NETWORKS[network];
  const Icon = known?.icon ?? Globe;
  const label = networkLabel(network);
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className={cn("inline-flex shrink-0 items-center", className)}
    >
      <Icon
        className={cn("h-3.5 w-3.5", known?.colorClass ?? "text-fg-muted")}
        aria-hidden
      />
    </span>
  );
}

export function ChannelAvatar({
  channel,
  size = "md",
}: {
  channel: Channel;
  size?: "sm" | "md";
}) {
  const name = channelDisplayName(channel);
  const dim = size === "sm" ? "h-8 w-8" : "h-9 w-9";

  return (
    <span className={cn("relative inline-flex shrink-0", dim)}>
      {channel.avatar_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={channel.avatar_url}
          alt={name}
          className={cn(
            "rounded-full border border-glass object-cover",
            dim,
          )}
        />
      ) : (
        <Avatar name={name} size={size} />
      )}
      <span className="absolute -bottom-0.5 -right-0.5 grid h-4 w-4 place-items-center rounded-full border border-glass bg-surface">
        <NetworkIcon network={channel.network} className="[&_svg]:h-2.5 [&_svg]:w-2.5" />
      </span>
    </span>
  );
}
