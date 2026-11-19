"use client";

import { CircleHelp, ExternalLink, Plus, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { AgentChatView } from "@/components/agent/agent-chat-view";
import { useAgentStatus } from "@/lib/api/agent";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/** Topbar "?": opens the Agent (one assistant with the Agente menu) in a
 *  side panel over the current screen, which it is told about. Fast guides
 *  and does, Free (the local model) only guides; the chat shows up in the
 *  Agente menu like any other. Hidden while neither mode is set up. */
export function HelpButton({ accountId }: { accountId: string }) {
  const t = useT();
  const pathname = usePathname() ?? "";
  const status = useAgentStatus(accountId);
  const [open, setOpen] = useState(false);
  // Mounted on first open and kept while navigating, so the chat goes on.
  const [started, setStarted] = useState(false);
  // Bumped by "Nuevo chat": a fresh chat in the panel.
  const [chatKey, setChatKey] = useState(0);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!status.data?.enabled) return null;
  // On the Agente screen the chat is already there.
  const onAgentPage = pathname.startsWith(`/accounts/${accountId}/agent`);

  return (
    <>
      <button
        type="button"
        aria-label={t("helpAssistant.title")}
        title={t("helpAssistant.title")}
        aria-expanded={open}
        disabled={onAgentPage}
        onClick={() => {
          setStarted(true);
          setOpen((v) => !v);
        }}
        className={cn(
          "relative flex h-10 w-10 items-center justify-center rounded-control text-fg-muted transition-colors",
          "hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon disabled:opacity-40",
        )}
      >
        <CircleHelp className="h-5 w-5" aria-hidden />
      </button>

      {started ? (
        <aside
          key={accountId}
          role="dialog"
          aria-label={t("helpAssistant.title")}
          aria-hidden={!open || onAgentPage}
          // A link to a screen takes the person there: the panel steps aside.
          onClick={(e) => {
            if ((e.target as Element).closest("a")) setOpen(false);
          }}
          className={cn(
            open && !onAgentPage ? "flex" : "hidden",
            "fixed inset-y-0 right-0 z-40 w-[28rem] max-w-full flex-col border-l border-glass bg-surface shadow-menu",
          )}
        >
          <div className="flex shrink-0 items-center gap-2 border-b border-glass px-3 py-2">
            <h2 className="min-w-0 flex-1 text-sm font-medium text-fg">{t("helpAssistant.title")}</h2>
            <button
              type="button"
              onClick={() => setChatKey((k) => k + 1)}
              className="inline-flex items-center gap-1 rounded-control px-2 py-1 text-xs text-fg-muted hover:bg-hover-glass hover:text-fg"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden />
              {t("agent.newChat")}
            </button>
            <Link
              href={`/accounts/${accountId}/agent`}
              className="inline-flex items-center gap-1 rounded-control px-2 py-1 text-xs text-fg-muted hover:bg-hover-glass hover:text-fg"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden />
              {t("agent.openFull")}
            </Link>
            <button
              type="button"
              aria-label={t("agent.closePanel")}
              onClick={() => setOpen(false)}
              className="rounded-control p-1.5 text-fg-muted hover:bg-hover-glass hover:text-fg"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
          <AgentChatView
            key={chatKey}
            accountId={accountId}
            threadId={null}
            page={pathname}
            embedded
            defaultMode="free"
          />
        </aside>
      ) : null}
    </>
  );
}
