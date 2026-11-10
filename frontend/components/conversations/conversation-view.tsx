"use client";

import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Megaphone,
  RotateCcw,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  type AdReferral,
  useConversation,
  useDeleteMessage,
  useMessages,
  usePendingMessages,
  useToggleStatus,
} from "@/lib/api/conversations";
import { cn } from "@/lib/utils";

import { AiHandoff, describeThreadControl } from "./ai-handoff";
import { ContactPanel } from "./contact-panel";
import { ConversationActions } from "./conversation-actions";
import { ConversationParticipants } from "./conversation-participants";
import { EmailComposer } from "./email-composer";
import { EmailMessage } from "./email-message";
import { useInboxPanels } from "./inbox-shell";
import { MessageBubble, PendingMessageBubble } from "./message-bubble";
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
  const {
    contactCollapsed,
    toggleContactCollapsed,
    detailsCollapsed,
    toggleDetailsCollapsed,
  } = useInboxPanels();
  const conv = useConversation(accountId, displayId);
  const messages = useMessages(accountId, displayId);
  const pending = usePendingMessages(accountId, displayId);
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
  const assigneeName = conv.data?.meta?.assignee?.name?.trim() || null;
  const assigneeSummary = assigneeName
    ? `Asignada a ${assigneeName}`
    : "Sin asignar";
  const handoffInfo = describeThreadControl(
    conv.data?.additional_attributes?.thread_control,
  );
  const detailsToggleLabel = detailsCollapsed
    ? "Mostrar detalles"
    : "Ocultar detalles";
  // Email is read and answered differently enough that the chat view is
  // the wrong shape for it: subject, recipients, long bodies, and a
  // thread you scan rather than scroll.
  const isEmail = conv.data?.meta?.channel === "Channel::Email";
  const subject = conv.data?.additional_attributes?.mail_subject ?? null;

  // The chat follows the newest message, unless the agent scrolled up to
  // read; sending brings them back down.
  const threadRef = useRef<HTMLDivElement>(null);
  const followNewest = useRef(true);
  const lastScrollTop = useRef(0);
  const sentCount = useRef(0);
  const newestId = messages.data?.payload.at(-1)?.id;
  useEffect(() => {
    followNewest.current = true;
  }, [displayId]);
  useEffect(() => {
    if (pending.length > sentCount.current) followNewest.current = true;
    sentCount.current = pending.length;
    const thread = threadRef.current;
    if (thread && !isEmail && followNewest.current) {
      thread.scrollTop = thread.scrollHeight;
    }
  }, [displayId, isEmail, newestId, pending.length]);
  // The bars above the thread load after it and shrink it.
  useEffect(() => {
    const thread = threadRef.current;
    if (!thread || isEmail || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (followNewest.current) thread.scrollTop = thread.scrollHeight;
    });
    observer.observe(thread);
    return () => observer.disconnect();
  }, [isEmail]);

  // Who the reply goes to. The newest message's sender is the person who
  // last wrote, which is who "reply" means on a thread.
  const replyTo =
    [...(messages.data?.payload ?? [])]
      .reverse()
      .find((m) => m.message_type === 0)?.content_attributes?.email?.from ??
    null;

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex shrink-0 items-center gap-3 border-b border-glass px-4 py-3">
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
            <div className="flex min-w-0 items-center gap-1.5 text-xs text-fg-muted">
              <span className="shrink-0 font-numeric tabular-nums">
                #{displayId}
              </span>
              {detailsCollapsed && conv.data ? (
                <>
                  <span aria-hidden>·</span>
                  <span
                    data-testid="collapsed-assignee-summary"
                    className="min-w-0 truncate"
                    title={assigneeSummary}
                  >
                    {assigneeSummary}
                  </span>
                  {handoffInfo ? (
                    <>
                      <span aria-hidden>·</span>
                      <span
                        data-testid="collapsed-ai-summary"
                        className="min-w-0 truncate text-fg"
                        title={handoffInfo.summary}
                      >
                        {handoffInfo.summary}
                      </span>
                    </>
                  ) : null}
                </>
              ) : null}
            </div>
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
          <button
            type="button"
            onClick={toggleDetailsCollapsed}
            aria-expanded={!detailsCollapsed}
            aria-label={detailsToggleLabel}
            title={detailsToggleLabel}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-control text-fg-muted transition-colors hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon"
          >
            {detailsCollapsed ? (
              <ChevronDown className="h-5 w-5" aria-hidden />
            ) : (
              <ChevronUp className="h-5 w-5" aria-hidden />
            )}
          </button>
        </header>

        <div
          data-testid="conversation-details-panel"
          data-collapsed={detailsCollapsed ? "true" : "false"}
          className={cn(
            "transition-[max-height,opacity] duration-200 ease-out motion-reduce:transition-none",
            detailsCollapsed
              ? "hidden max-h-0 overflow-hidden opacity-0"
              : "shrink-0 opacity-100",
          )}
        >
          {!detailsCollapsed ? (
            <>
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
                <ConversationParticipants
                  accountId={accountId}
                  displayId={displayId}
                />
              ) : null}
            </>
          ) : null}
        </div>

        {/* Thread */}
        <div
          ref={threadRef}
          onScroll={(e) => {
            const el = e.currentTarget;
            // Only moving up stops following: the thread shrinking while the
            // bars above it load also leaves it away from the bottom.
            if (el.scrollHeight - el.scrollTop - el.clientHeight < 120) {
              followNewest.current = true;
            } else if (el.scrollTop < lastScrollTop.current) {
              followNewest.current = false;
            }
            lastScrollTop.current = el.scrollTop;
          }}
          className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4"
        >
          {messages.isLoading ? (
            <p className="text-center text-sm text-fg-muted">Cargando…</p>
          ) : messages.isError ? (
            <p role="alert" className="text-center text-sm text-danger">
              No se pudieron cargar los mensajes.
            </p>
          ) : (messages.data?.payload.length ?? 0) === 0 &&
            (isEmail || pending.length === 0) ? (
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
          {isEmail
            ? null
            : pending.map((p) => (
                <PendingMessageBubble
                  key={p.mutationId}
                  accountId={accountId}
                  displayId={displayId}
                  pending={p}
                />
              ))}
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
        collapsed={contactCollapsed}
        onToggleCollapse={toggleContactCollapsed}
      />
    </div>
  );
}
