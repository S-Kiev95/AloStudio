import Link from "next/link";

import type { Portal } from "@/lib/api/portals";

/** Branded portal header. The portal's ``color`` becomes the accent. */
export function PortalHeader({ portal }: { portal: Portal }) {
  const accent = portal.color || "#1f93ff";
  return (
    <header
      className="border-b border-border"
      style={{ backgroundColor: `${accent}10` }}
    >
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-5 md:px-6">
        <Link
          href={`/hc/${portal.slug}`}
          className="flex items-center gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full font-semibold text-white"
            style={{ backgroundColor: accent }}
          >
            {portal.name.slice(0, 1).toUpperCase()}
          </span>
          <span className="font-semibold text-fg">{portal.name}</span>
        </Link>
        {portal.homepage_link ? (
          <a
            href={portal.homepage_link}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-fg-muted hover:text-fg"
          >
            Volver al sitio
          </a>
        ) : null}
      </div>
    </header>
  );
}
