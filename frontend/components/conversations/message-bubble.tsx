import { Lock, Paperclip } from "lucide-react";

import { MESSAGE_TYPE, type Message } from "@/lib/api/conversations";
import { clockTime } from "@/lib/time";
import { cn } from "@/lib/utils";

type Attachment = NonNullable<Message["attachments"]>[number];

function AttachmentView({ att }: { att: Attachment }) {
  if (!att.data_url) return null;
  if (att.file_type === "image") {
    return (
      <a
        href={att.data_url}
        target="_blank"
        rel="noreferrer"
        className="mt-1 block"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={att.data_url}
          alt="Adjunto"
          className="max-h-56 max-w-full rounded-md border border-border object-contain"
        />
      </a>
    );
  }
  return (
    <a
      href={att.data_url}
      target="_blank"
      rel="noreferrer"
      className="mt-1 flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1 text-xs font-medium text-primary hover:underline"
    >
      <Paperclip className="h-3 w-3 shrink-0" aria-hidden />
      Descargar adjunto
    </a>
  );
}

/**
 * One message in the thread. Outgoing = right + primary; incoming = left +
 * surface; activity = centered system note; private notes get a warning
 * tint + a lock. Attachments render inline (image preview or a download link).
 */
export function MessageBubble({ message }: { message: Message }) {
  if (message.message_type === MESSAGE_TYPE.activity) {
    return (
      <div className="my-2 text-center text-xs text-fg-muted">
        {message.content}
      </div>
    );
  }

  const outgoing = message.message_type === MESSAGE_TYPE.outgoing;
  const isPrivate = message.private;

  return (
    <div className={cn("flex", outgoing ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] rounded-lg px-3 py-2 text-sm",
          isPrivate
            ? "border border-warning/40 bg-warning/10 text-fg"
            : outgoing
              ? "bg-surface-2 text-fg"
              : "border border-border bg-surface text-fg",
        )}
      >
        {isPrivate ? (
          <span className="mb-1 flex items-center gap-1 text-xs font-medium text-warning">
            <Lock className="h-3 w-3" aria-hidden /> Nota privada
          </span>
        ) : null}
        {message.content ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : null}
        {message.attachments?.map((att) => (
          <AttachmentView key={att.id} att={att} />
        ))}
        <span className="mt-1 block text-right text-[10px] tabular-nums text-fg-muted">
          {clockTime(message.created_at)}
        </span>
      </div>
    </div>
  );
}
