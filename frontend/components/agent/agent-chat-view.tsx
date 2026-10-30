"use client";

import { Ban, Check, Clock, MessageSquare, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  type AgentItem,
  type AgentPendingAction,
  type AgentToolItem,
  getAgentErrorMessage,
  getBrowserTimezone,
  isAgentErrorStatus,
  useAgentStatus,
  useAgentThread,
  useConfirmAgentAction,
  useCreateAgentThread,
  useRejectAgentAction,
  useSendAgentMessage,
} from "@/lib/api/agent";
import { cn } from "@/lib/utils";

import { AgentComposer } from "./agent-composer";
import { useAgentShell } from "./agent-shell";
import { formatLocalClock } from "./agent-time";
import { PendingActionCard } from "./pending-action-card";

const WRITE_SUGGESTION =
  "Armá una publicación para mañana a las 10 en todos mis canales";

const READ_SUGGESTIONS = [
  "¿Qué tengo programado esta semana?",
  "¿Cómo les fue a mis publicaciones del último mes?",
] as const;

const UNCONFIGURED_NOTICE =
  "El agente todavía no está configurado. Un operador de la instalación tiene que cargar la clave de OpenAI en Ajustes → Instalación → Inteligencia artificial.";

const READ_ONLY_NOTICE =
  "Podés consultar publicaciones y estadísticas. Crear o borrar publicaciones lo hace un administrador.";

const EMPTY_GREETING =
  "Hola, soy el agente de AloStudio. Puedo armar y programar publicaciones en tus canales, revisar tu calendario y contarte cómo les fueron tus posts.";

function ToolStatusIcon({ status }: { status: AgentToolItem["status"] }) {
  switch (status) {
    case "done":
      return <Check className="h-3.5 w-3.5 shrink-0 text-success" aria-hidden />;
    case "error":
      return <X className="h-3.5 w-3.5 shrink-0 text-danger" aria-hidden />;
    case "pending":
      return <Clock className="h-3.5 w-3.5 shrink-0 text-warning" aria-hidden />;
    case "rejected":
      return <Ban className="h-3.5 w-3.5 shrink-0 text-fg-muted" aria-hidden />;
  }
}

function ToolActivityRow({
  accountId,
  item,
}: {
  accountId: string;
  item: AgentToolItem;
}) {
  return (
    <div className="my-1 flex flex-col gap-0.5 py-0.5 text-xs">
      <div className="flex flex-wrap items-center gap-1.5 text-fg-muted">
        <ToolStatusIcon status={item.status} />
        <span>{item.label}</span>
        {item.publication_id !== null ? (
          <Link
            href={`/accounts/${accountId}/publications?publication=${item.publication_id}`}
            className="font-medium text-info hover:underline"
          >
            Ver en el calendario
          </Link>
        ) : null}
      </div>
      {item.detail?.trim() ? (
        <p className="pl-5 whitespace-pre-wrap break-words text-xs text-fg-muted">
          {item.detail}
        </p>
      ) : null}
    </div>
  );
}

function AgentItemRow({
  accountId,
  item,
}: {
  accountId: string;
  item: AgentItem;
}) {
  if (item.kind === "tool") {
    return <ToolActivityRow accountId={accountId} item={item} />;
  }

  const isUser = item.kind === "user";
  const time = formatLocalClock(item.created_at);

  return (
    <div
      className={cn(
        "flex flex-col",
        isUser ? "items-end" : "items-start",
      )}
    >
      <div
        className={cn(
          "max-w-[80%] min-w-0 px-3.5 py-2 text-sm",
          isUser
            ? "rounded-panel rounded-br-sm bg-primary text-primary-fg"
            : "rounded-panel rounded-bl-sm border border-glass bg-surface-2 text-fg",
        )}
      >
        <p className="whitespace-pre-wrap break-words">{item.content}</p>
      </div>
      {time ? (
        <span
          className={cn(
            "mt-1 font-numeric text-[11px] tabular-nums text-fg-muted",
            isUser ? "text-right" : "text-left",
          )}
        >
          {time}
        </span>
      ) : null}
    </div>
  );
}

export function AgentChatView({
  accountId,
  threadId,
}: {
  accountId: string;
  threadId: number | null;
}) {
  const router = useRouter();
  const shell = useAgentShell();
  const scrollRef = useRef<HTMLDivElement>(null);

  const [createdThreadId, setCreatedThreadId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [optimisticUserMessage, setOptimisticUserMessage] = useState<
    string | null
  >(null);
  const [composerError, setComposerError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const resetSignal = shell?.newChatResetKey ?? 0;

  useEffect(() => {
    setCreatedThreadId(null);
    setDraft("");
    setOptimisticUserMessage(null);
    setComposerError(null);
    setActionError(null);
  }, [threadId, resetSignal]);

  const effectiveThreadId = threadId ?? createdThreadId;
  const invalidThreadParam =
    effectiveThreadId !== null &&
    (!Number.isFinite(effectiveThreadId) || effectiveThreadId <= 0);

  const statusQuery = useAgentStatus(accountId);
  const threadQuery = useAgentThread(accountId, effectiveThreadId);
  const createThread = useCreateAgentThread(accountId);
  const sendMessage = useSendAgentMessage(accountId);
  const confirmAction = useConfirmAgentAction(accountId);
  const rejectAction = useRejectAgentAction(accountId);

  const agentDisabled =
    statusQuery.data?.enabled === false || statusQuery.isError;
  const canWrite = statusQuery.data ? statusQuery.data.can_write : true;
  const showReadOnlyBanner = statusQuery.data?.can_write === false;

  const isSending = createThread.isPending || sendMessage.isPending;
  const isActing = confirmAction.isPending || rejectAction.isPending;
  const isBusy = isSending || isActing;

  const items = threadQuery.data?.items ?? [];
  const rawPendingAction = threadQuery.data?.pending_action ?? null;
  // Hide any prior pending card while the user has sent a follow-up message
  // (which discards the pending proposal on the backend).
  const visiblePendingAction = isSending ? null : rawPendingAction;

  const lastItemId = items.length > 0 ? items[items.length - 1]?.id ?? 0 : 0;
  const scrollTrigger = `${effectiveThreadId ?? "new"}|${items.length}|${lastItemId}|${visiblePendingAction?.id ?? ""}|${optimisticUserMessage ?? ""}|${actionError ?? ""}`;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [scrollTrigger]);

  async function sendContent(rawText: string) {
    const text = rawText.trim();
    const charLen = Array.from(rawText).length;
    if (!text || charLen > 4000 || isBusy || agentDisabled) {
      return;
    }

    const timezone = getBrowserTimezone();
    setComposerError(null);
    setActionError(null);
    setOptimisticUserMessage(text);
    setDraft("");

    try {
      if (effectiveThreadId === null) {
        const created = await createThread.mutateAsync({
          content: text,
          timezone,
        });
        setCreatedThreadId(created.id);
        setOptimisticUserMessage(null);
        router.push(`/accounts/${accountId}/agent/${created.id}`);
      } else {
        await sendMessage.mutateAsync({
          threadId: effectiveThreadId,
          content: text,
          timezone,
        });
        setOptimisticUserMessage(null);
      }
    } catch (err) {
      setOptimisticUserMessage(null);
      setComposerError(getAgentErrorMessage(err));
      // On 502 the backend saved the user's message and the mutation's onError
      // refetches the thread, so do not put the text back into the composer.
      if (!isAgentErrorStatus(err, 502)) {
        setDraft((curr) => (curr ? curr : rawText));
      }
    }
  }

  async function handleConfirm(action: AgentPendingAction) {
    if (effectiveThreadId === null || isBusy || agentDisabled) return;
    setActionError(null);
    setComposerError(null);
    try {
      await confirmAction.mutateAsync({
        threadId: effectiveThreadId,
        actionId: action.id,
        publicationId: action.publication.id,
      });
    } catch (err) {
      setActionError(getAgentErrorMessage(err));
    }
  }

  async function handleReject(action: AgentPendingAction) {
    if (effectiveThreadId === null || isBusy) return;
    setActionError(null);
    setComposerError(null);
    try {
      await rejectAction.mutateAsync({
        threadId: effectiveThreadId,
        actionId: action.id,
        publicationId: action.publication.id,
      });
    } catch (err) {
      setActionError(getAgentErrorMessage(err));
    }
  }

  const headerTitle =
    effectiveThreadId === null
      ? "Nuevo chat"
      : (threadQuery.data?.title ??
        (threadQuery.isLoading ? "Cargando…" : "Chat"));

  const suggestions = statusQuery.data?.can_write
    ? [WRITE_SUGGESTION, ...READ_SUGGESTIONS]
    : [...READ_SUGGESTIONS];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Header */}
      <header className="flex shrink-0 items-center gap-2.5 border-b border-glass px-4 py-3">
        {shell ? (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={shell.openMobileList}
            className="md:hidden"
          >
            <MessageSquare className="h-4 w-4" aria-hidden />
            Chats
          </Button>
        ) : null}
        <h2 className="min-w-0 flex-1 truncate text-sm font-semibold text-fg">
          {headerTitle}
        </h2>
      </header>

      {/* Fixed read-only note for non-admin agents */}
      {showReadOnlyBanner ? (
        <div
          role="note"
          className="shrink-0 border-b border-glass bg-surface-2 px-4 py-2 text-xs text-fg-muted"
        >
          {READ_ONLY_NOTICE}
        </div>
      ) : null}

      {/* Unconfigured banner on existing threads (old chats remain readable) */}
      {effectiveThreadId !== null && statusQuery.data?.enabled === false ? (
        <div
          role="status"
          className="shrink-0 border-b border-glass bg-surface-2 px-4 py-2 text-xs text-warning"
        >
          {UNCONFIGURED_NOTICE}
        </div>
      ) : null}

      {/* Conversation body */}
      <div
        ref={scrollRef}
        className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-4"
      >
        {effectiveThreadId === null && optimisticUserMessage === null ? (
          statusQuery.isLoading ? (
            <div className="flex flex-1 items-center justify-center p-6">
              <p className="text-sm text-fg-muted">Cargando…</p>
            </div>
          ) : statusQuery.isError ? (
            <div className="flex flex-1 items-center justify-center p-6">
              <p role="alert" className="max-w-md text-center text-sm text-danger">
                {getAgentErrorMessage(
                  statusQuery.error,
                  "No se pudo consultar el estado del agente.",
                )}
              </p>
            </div>
          ) : statusQuery.data?.enabled === false ? (
            <div className="flex flex-1 items-center justify-center p-6">
              <div
                role="status"
                className="max-w-md rounded-md border border-glass bg-surface-2 p-5 text-center text-sm text-fg-muted"
              >
                {UNCONFIGURED_NOTICE}
              </div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-xl flex-1 flex-col items-start justify-center gap-4 py-6">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-glass bg-focused text-lit">
                  <Sparkles className="h-4 w-4" aria-hidden />
                </span>
                <p className="text-sm leading-relaxed text-fg">
                  {EMPTY_GREETING}
                </p>
              </div>

              <div className="flex w-full flex-col gap-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    disabled={isBusy}
                    onClick={() => void sendContent(suggestion)}
                    className="w-full rounded-control border border-glass bg-surface-2 px-3.5 py-2.5 text-left text-sm text-fg transition-colors hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon disabled:opacity-50"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )
        ) : invalidThreadParam ? (
          <div className="flex flex-1 items-center justify-center p-6">
            <p role="alert" className="text-sm text-danger">
              No se encontró este chat.
            </p>
          </div>
        ) : effectiveThreadId !== null && threadQuery.isLoading ? (
          <div className="flex flex-1 items-center justify-center p-6">
            <p className="text-sm text-fg-muted">Cargando…</p>
          </div>
        ) : effectiveThreadId !== null && threadQuery.isError ? (
          <div className="flex flex-1 items-center justify-center p-6">
            <p role="alert" className="text-sm text-danger">
              {isAgentErrorStatus(threadQuery.error, 404)
                ? "No se encontró este chat."
                : getAgentErrorMessage(
                    threadQuery.error,
                    "No se pudo cargar el chat.",
                  )}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <AgentItemRow
                key={item.id}
                accountId={accountId}
                item={item}
              />
            ))}

            {optimisticUserMessage !== null ? (
              <>
                <div className="flex flex-col items-end">
                  <div className="max-w-[80%] min-w-0 rounded-panel rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-fg">
                    <p className="whitespace-pre-wrap break-words">
                      {optimisticUserMessage}
                    </p>
                  </div>
                </div>
                <div className="flex flex-col items-start">
                  <div className="max-w-[80%] min-w-0 rounded-panel rounded-bl-sm border border-glass bg-surface-2 px-3.5 py-2 text-sm text-fg-muted">
                    <p className="animate-pulse">Pensando…</p>
                  </div>
                </div>
              </>
            ) : null}

            {visiblePendingAction ? (
              <PendingActionCard
                key={visiblePendingAction.id}
                action={visiblePendingAction}
                canWrite={canWrite}
                disabled={agentDisabled}
                isConfirming={confirmAction.isPending}
                isRejecting={rejectAction.isPending}
                error={actionError}
                onConfirm={() => void handleConfirm(visiblePendingAction)}
                onReject={() => void handleReject(visiblePendingAction)}
              />
            ) : actionError ? (
              <div
                role="alert"
                className="rounded-md border border-danger bg-surface-2 px-3.5 py-2.5 text-xs text-danger"
              >
                {actionError}
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* Fixed bottom composer */}
      <AgentComposer
        value={draft}
        onChange={setDraft}
        onSubmit={() => void sendContent(draft)}
        disabled={agentDisabled}
        isBusy={isBusy}
        error={composerError}
      />
    </div>
  );
}
