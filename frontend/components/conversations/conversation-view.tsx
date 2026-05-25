"use client";

import { ArrowLeft, CheckCircle2, RotateCcw } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  useConversation,
  useMessages,
  useToggleStatus,
} from "@/lib/api/conversations";

import { MessageBubble } from "./message-bubble";
import { MessageComposer } from "./message-composer";

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

  const status = conv.data?.status;
  const contactName = conv.data?.meta?.sender?.name ?? `#${displayId}`;
  const resolved = status === "resolved";

  return (
    <div className="flex h-[calc(100dvh-3.5rem-2rem)] flex-col sm:h-[calc(100dvh-3.5rem-3rem)]">
      {/* Header */}
      <header className="flex items-center gap-3 border-b border-border pb-3">
        <Link
          href={`/accounts/${accountId}/conversations`}
          aria-label="Volver"
          className="rounded-md p-1 text-fg-muted hover:bg-surface-2 lg:hidden"
        >
          <ArrowLeft className="h-5 w-5" aria-hidden />
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-semibold text-fg">
            {contactName}
          </h1>
          <p className="text-xs text-fg-muted">
            Conversación #{displayId}
            {status ? ` · ${status}` : ""}
          </p>
        </div>
        <Button
          variant={resolved ? "secondary" : "primary"}
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

      {/* Thread */}
      <div className="flex-1 space-y-2 overflow-y-auto py-4">
        {messages.isLoading ? (
          <p className="text-center text-sm text-fg-muted">Cargando…</p>
        ) : messages.isError ? (
          <p role="alert" className="text-center text-sm text-danger">
            No se pudieron cargar los mensajes.
          </p>
        ) : (messages.data?.payload.length ?? 0) === 0 ? (
          <p className="text-center text-sm text-fg-muted">Sin mensajes.</p>
        ) : (
          messages.data?.payload.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))
        )}
      </div>

      <MessageComposer accountId={accountId} displayId={displayId} />
    </div>
  );
}
