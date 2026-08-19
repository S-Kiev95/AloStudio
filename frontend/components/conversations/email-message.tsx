"use client";

import { ChevronDown, Paperclip } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import type { Message } from "@/lib/api/conversations";

type EmailMeta = NonNullable<
  NonNullable<Message["content_attributes"]>["email"]
>;
import { cn } from "@/lib/utils";

/** One email in a thread, as a card rather than a chat bubble.
 *
 *  A bubble is the wrong shape for this. Email is long, has an author
 *  line, a set of recipients and a subject, and threads are read by
 *  scanning who wrote what and opening the one that matters — which is
 *  why every mail client collapses all but the last.
 *
 *  Collapsed by default except the newest: on a ten-message thread the
 *  alternative is a wall nobody reads. */
export function EmailMessage({
  message,
  defaultOpen,
}: {
  message: Message;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = message.content_attributes?.email;
  const outgoing = message.message_type === 1;

  const author =
    meta?.from_name?.trim() ||
    message.sender?.name?.trim() ||
    meta?.from?.trim() ||
    (outgoing ? "Vos" : "Contacto");
  const address = meta?.from?.trim() || null;

  const preview = (message.content ?? "").replace(/\s+/g, " ").trim();

  return (
    <article
      className={cn(
        "rounded-xl border transition-colors",
        outgoing
          ? "border-primary/25 bg-primary/[0.04]"
          : "border-border bg-surface",
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 p-3 text-left"
      >
        <Avatar name={author} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-sm font-semibold text-fg">{author}</span>
            {address ? (
              <span className="truncate text-xs text-fg-muted">{address}</span>
            ) : null}
            {outgoing ? (
              <span className="text-xs text-primary">enviado</span>
            ) : null}
          </div>
          {open ? (
            <Recipients meta={meta} />
          ) : (
            <p className="truncate text-xs text-fg-muted">{preview}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {message.attachments?.length ? (
            <span
              className="flex items-center gap-0.5 text-xs text-fg-muted"
              title={`${message.attachments.length} adjunto(s)`}
            >
              <Paperclip className="h-3.5 w-3.5" aria-hidden />
              {message.attachments.length}
            </span>
          ) : null}
          <time className="text-xs text-fg-muted">
            {new Date(message.created_at * 1000).toLocaleString()}
          </time>
          <ChevronDown
            aria-hidden
            className={cn(
              "h-4 w-4 text-fg-muted transition-transform",
              open && "rotate-180",
            )}
          />
        </div>
      </button>

      {open ? (
        <div className="border-t border-border px-3 py-3">
          {/* Whitespace preserved: an email is written with line breaks
              and paragraphs, and collapsing them turns a quoted reply
              into an unreadable run-on. */}
          <p className="whitespace-pre-wrap break-words text-sm text-fg">
            {message.content || <span className="text-fg-muted">(sin texto)</span>}
          </p>
          {message.attachments?.length ? (
            <Attachments attachments={message.attachments} />
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function Recipients({ meta }: { meta: EmailMeta | undefined }) {
  const to = meta?.to ?? [];
  const cc = meta?.cc ?? [];
  if (!to.length && !cc.length) return null;
  return (
    <dl className="mt-0.5 space-y-0.5 text-xs text-fg-muted">
      {to.length ? (
        <div className="flex gap-1.5">
          <dt className="shrink-0">Para:</dt>
          <dd className="min-w-0 truncate">{to.join(", ")}</dd>
        </div>
      ) : null}
      {cc.length ? (
        <div className="flex gap-1.5">
          <dt className="shrink-0">CC:</dt>
          <dd className="min-w-0 truncate">{cc.join(", ")}</dd>
        </div>
      ) : null}
    </dl>
  );
}

/** Files, listed as files.
 *
 *  The chat view renders an image attachment inline, which is right for
 *  a photo someone sent on WhatsApp and wrong for a 3 MB scan attached to
 *  an email — those get downloaded, not looked at in the thread. */
function Attachments({
  attachments,
}: {
  attachments: NonNullable<Message["attachments"]>;
}) {
  return (
    <ul className="mt-3 flex flex-wrap gap-2">
      {attachments.map((a) => (
        <li key={a.id}>
          <a
            href={a.data_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs text-fg hover:bg-surface-2"
          >
            <Paperclip className="h-3.5 w-3.5 text-fg-muted" aria-hidden />
            <span className="max-w-[16rem] truncate">
              {a.fallback_title || `archivo.${a.extension ?? "bin"}`}
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}
