"use client";

import { Plus, Trash2, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  type AgentThreadSummary,
  getAgentErrorMessage,
  useAgentThreads,
  useDeleteAgentThread,
} from "@/lib/api/agent";
import { cn } from "@/lib/utils";

import { useAgentShell } from "./agent-shell";
import { formatRelativeIso } from "./agent-time";

export function AgentThreadList({ accountId }: { accountId: string }) {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const shell = useAgentShell();
  const threadsQuery = useAgentThreads(accountId);
  const deleteThread = useDeleteAgentThread(accountId);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const activeMatch = /^\/accounts\/[^/]+\/agent\/(\d+)(?:\/|$)/.exec(pathname);
  const activeThreadId = activeMatch ? Number(activeMatch[1]) : null;
  const threads = threadsQuery.data?.threads ?? [];

  function handleNewChat() {
    setDeleteError(null);
    shell?.closeMobileList();
    shell?.triggerNewChatReset();
    router.push(`/accounts/${accountId}/agent`);
  }

  async function handleDelete(thread: AgentThreadSummary) {
    if (!window.confirm(`¿Borrar el chat “${thread.title}”?`)) return;
    setDeleteError(null);
    try {
      await deleteThread.mutateAsync(thread.id);
      if (activeThreadId === thread.id) {
        shell?.triggerNewChatReset();
        router.push(`/accounts/${accountId}/agent`);
      }
    } catch (err) {
      setDeleteError(getAgentErrorMessage(err, "No se pudo borrar el chat."));
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-glass p-3">
        <Button type="button" className="flex-1" onClick={handleNewChat}>
          <Plus className="h-4 w-4" aria-hidden />
          Nuevo chat
        </Button>
        {shell?.mobileListOpen ? (
          <button
            type="button"
            aria-label="Cerrar lista de chats"
            onClick={shell.closeMobileList}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-control text-fg-muted hover:bg-hover-glass hover:text-fg md:hidden"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        ) : null}
      </div>

      {deleteError ? (
        <p
          role="alert"
          className="border-b border-glass px-3 py-2 text-xs text-danger"
        >
          {deleteError}
        </p>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {threadsQuery.isLoading ? (
          <p className="p-6 text-center text-sm text-fg-muted">Cargando…</p>
        ) : threadsQuery.isError ? (
          <p role="alert" className="p-6 text-center text-sm text-danger">
            {getAgentErrorMessage(
              threadsQuery.error,
              "No se pudieron cargar los chats.",
            )}
          </p>
        ) : threads.length === 0 ? (
          <p className="p-6 text-center text-sm text-fg-muted">
            Todavía no tenés chats.
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {threads.map((thread) => {
              const active = activeThreadId === thread.id;
              return (
                <li
                  key={thread.id}
                  className={cn(
                    "group flex items-center transition-colors",
                    active ? "bg-focused" : "hover:bg-hover-glass",
                  )}
                >
                  <Link
                    href={`/accounts/${accountId}/agent/${thread.id}`}
                    onClick={() => shell?.closeMobileList()}
                    aria-current={active ? "page" : undefined}
                    className="flex min-w-0 flex-1 flex-col gap-1 py-2.5 pl-3 pr-1 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neon"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "min-w-0 flex-1 truncate text-sm font-medium",
                          active ? "text-lit" : "text-fg",
                        )}
                      >
                        {thread.title}
                      </span>
                      <span className="shrink-0 font-numeric text-[11px] tabular-nums text-fg-muted">
                        {formatRelativeIso(thread.updated_at)}
                      </span>
                    </div>
                    {thread.has_pending_action ? (
                      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-warning">
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full bg-warning"
                          aria-hidden
                        />
                        Por confirmar
                      </span>
                    ) : null}
                  </Link>
                  <button
                    type="button"
                    onClick={() => void handleDelete(thread)}
                    disabled={deleteThread.isPending}
                    aria-label={`Borrar chat ${thread.title}`}
                    title="Borrar chat"
                    className="mr-2 shrink-0 rounded-md p-1.5 text-fg-muted opacity-0 transition hover:bg-hover-glass hover:text-danger focus-visible:opacity-100 group-hover:opacity-100 disabled:opacity-40"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
