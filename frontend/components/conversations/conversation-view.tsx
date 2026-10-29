"use client";

import { ArrowLeft, CheckCircle2, Megaphone, RotateCcw } from "lucide-react";
import Link from "next/link";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  type AdReferral,
  useConversation,
  useDeleteMessage,
  useMessages,
  useToggleStatus,
} from "@/lib/api/conversations";
import { cn } from "@/lib/utils";

import { AiHandoff } from "./ai-handoff";
import { ContactPanel } from "./contact-panel";
import { ConversationActions } from "./conversation-actions";
import { ConversationParticipants } from "./conversation-participants";
import { EmailComposer } from "./email-composer";
import { EmailMessage } from "./email-message";
import { MessageBubble } from "./message-bubble";
import { MessageComposer } from "./message-composer";

const STATUS_CHIP: Record<string, { label: string; className: string }> = {
  open: {
    label: "Abierta",
    className: "border border-success bg-surface-2 text-success",
  },
  pending: {
    label: "Pendiente",
    className: "border border-warning bg-surface-2 text-warning",
  },
  resolved: {
    label: "Resuelta",
    className: "border border-glass bg-surface-2 text-fg-muted",
  },
  snoozed: {
    label: "Pospuesta",
    className: "border border-glass bg-surface-2 text-fg-muted",
  },
};

/** Where this chat came from, when it started with an ad or a ref link.
 *
 *  Worth its own line rather than a tooltip: knowing the person arrived
 *  through "20% OFF" tells the agent what was promised before they reply.
 *
 *  The wording stays "Vino de" rather than "Vino del anuncio" because the
 *  same referral block also covers ig.me / m.me links, where calling the
 *  origin an ad would be wrong. */
function AdOrigin({ referral }: { referral?: AdReferral | null }) {
  if (!referral) return null;
  const label =
    referral.headline?.trim() ||
    (referral.ad_id ? `Anuncio ${referral.ad_id}` : "un enlace");
  return (
    <p
      className="mt-0.5 flex items-center gap-1.5 text-xs text-fg-muted"
      title={referral.ad_id ? `ID del anuncio: ${referral.ad_id}` : undefined}
    >
      <Megaphone className="h-3 w-3 shrink-0 text-primary" aria-hidden />
      <span className="shrink-0">Vino de</span>
      <span className="truncate font-medium text-fg">{label}</span>
    </p>
  );
}

function StatusChip({ status }: { status: string }) {
  const s = STATUS_CHIP[status];
  if (!s) return null;
  return (
    <span
      className={cn(
        "hidden shrink-0 rounded-pill px-2.5 py-0.5 text-xs font-medium sm:inline-flex",
        s.className,
      )}
    >
      {s.label}
    </span>
  );
}

export function ConversationView({
  accountId,
  displayId,
}: {
  accountId: string;
  displayId: number;
}) {
  const conv = useConversation(accountId, displayId);
  const messages = useMessages(accountId, displayId);
  const toggle = useToggleStatus(accountId, displayId);
  const del = useDeleteMessage(accountId, displayId);

  function handleDelete(id: number) {
    if (
      window.confirm(
        "¿Eliminar este mensaje? Se quita de la conversación, pero el " +
          "destinatario ya lo recibió en su WhatsApp.",
      )
    ) {
      del.mutate(id);
    }
  }

  const status = conv.data?.status;
  const contactName = conv.data?.meta?.sender?.name ?? `#${displayId}`;
  const contactId = conv.data?.meta?.sender?.id ?? null;
  const resolved = status === "resolved";
  // Email is read and answered differently enough that the chat view is
  // the wrong shape for it: subject, recipients, long bodies, and a
  // thread you scan rather than scroll.
  const isEmail = conv.data?.meta?.channel === "Channel::Email";
  const subject = conv.data?.additional_attributes?.mail_subject ?? null;
  // Who the reply goes to. The newest message's sender is the person who
  // last wrote, which is who "reply" means on a thread.
  const replyTo =
    [...(messages.data?.payload ?? [])]
      .reverse()
      .find((m) => m.message_type === 0)?.content_attributes?.email?.from ??
    null;

  return (
    <div className="flex min-h-0 flex-1">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center gap-3 border-b border-glass px-4 py-3">
          <Link
            href={`/accounts/${accountId}/conversations`}
            aria-label="Volver"
            className="rounded-md p-1 text-fg-muted hover:bg-hover-glass hover:text-fg lg:hidden"
          >
            <ArrowLeft className="h-5 w-5" aria-hidden />
          </Link>
          <Avatar name={contactName} size="sm" />
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-sm font-semibold text-fg">
              {contactName}
            </h2>
            {isEmail && subject ? (
              <p className="truncate text-xs text-fg" title={subject}>
                {subject}
              </p>
            ) : null}
            <p className="font-numeric text-xs tabular-nums text-fg-muted">
              #{displayId}
            </p>
            <AdOrigin referral={conv.data?.ad_referral} />
          </div>
          {status ? <StatusChip status={status} /> : null}
          <Button
            variant="secondary"
            size="sm"
            loading={toggle.isPending}
            onClick={() => toggle.mutate(resolved ? "open" : "resolved")}
          >
            {resolved ? (
              <>
                <RotateCcw className="h-4 w-4" aria-hidden /> Reabrir
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4" aria-hidden /> Resolver
              </>
            )}
          </Button>
        </header>

        {/* Meta Business Agent handoff (WhatsApp numbers answered by Meta's AI) */}
        <AiHandoff
          accountId={accountId}
          displayId={displayId}
          control={conv.data?.additional_attributes?.thread_control}
        />

        {/* Actions (assignee / team / "+ Etiqueta" / priority / macro) */}
        {conv.data ? (
          <ConversationActions
            accountId={accountId}
            displayId={displayId}
            priority={conv.data.priority}
            assigneeId={conv.data.meta?.assignee?.id ?? null}
            teamId={conv.data.meta?.team?.id ?? null}
            labels={conv.data.labels ?? []}
          />
        ) : null}

        {/* Participants (agents watching this conversation) */}
        {conv.data && !isEmail ? (
          <ConversationParticipants accountId={accountId} displayId={displayId} />
        ) : null}

        {/* Thread */}
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {messages.isLoading ? (
            <p className="text-center text-sm text-fg-muted">Cargando…</p>
          ) : messages.isError ? (
            <p role="alert" className="text-center text-sm text-danger">
              No se pudieron cargar los mensajes.
            </p>
          ) : (messages.data?.payload.length ?? 0) === 0 ? (
            <p className="text-center text-sm text-fg-muted">Sin mensajes.</p>
          ) : (
            messages.data?.payload.map((m, i, all) =>
              isEmail ? (
                <EmailMessage
                  key={m.id}
                  message={m}
                  // Only the newest is open. On a ten-message thread the
                  // alternative is a wall nobody reads — every mail client
                  // collapses the rest for the same reason.
                  defaultOpen={i === all.length - 1}
                />
              ) : (
                <MessageBubble
                  key={m.id}
                  message={m}
                  contactName={conv.data?.meta?.sender?.name}
                  onDelete={handleDelete}
                />
              ),
            )
          )}
        </div>

        {isEmail ? (
          <div className="border-t border-glass p-3">
            <EmailComposer
              accountId={accountId}
              displayId={displayId}
              replyTo={replyTo}
            />
          </div>
        ) : (
          <MessageComposer accountId={accountId} displayId={displayId} />
        )}
      </div>

      {/* Right-hand contact panel (lg+ only). */}
      <ContactPanel
        accountId={accountId}
        contactId={contactId}
        currentDisplayId={displayId}
        conversationStatus={status}
      />
    </div>
  );
}
