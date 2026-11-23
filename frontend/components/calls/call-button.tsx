"use client";

import { Phone } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useCallPermission, useRequestCallPermission } from "@/lib/api/calls";
import { useDismissOnOutsideAndEscape } from "@/lib/hooks/use-dismiss";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

import { requestDial } from "./dialer";

function problemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("calls.")) {
    return `calls.problems.${code.slice(6)}`;
  }
  return "calls.problems.refused";
}

/** Meta's own reason, when it gave one beyond our code. */
function metaReason(err: unknown): string | null {
  const body = (err as { body?: { code?: unknown; message?: unknown } })?.body;
  if (typeof body?.message === "string" && body.message !== body.code) return body.message;
  return null;
}

/**
 * Conversation header → call the customer on WhatsApp (F7). Opens a small
 * panel that asks Meta whether the customer allows calls: if so, it calls;
 * if not, it asks them in the chat (WhatsApp shows its own buttons).
 */
export function CallButton({
  accountId,
  conversationId,
  contactName,
  thumbnail,
}: {
  accountId: string;
  /** The conversation's number in the panel (``display_id``). */
  conversationId: number;
  contactName: string;
  thumbnail?: string | null;
}) {
  const t = useT();
  const tag = useIntlTag();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [sent, setSent] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const permission = useCallPermission(accountId, conversationId, open);
  const ask = useRequestCallPermission(accountId, conversationId);

  useDismissOnOutsideAndEscape(panel, open, () => setOpen(false));

  function toggle() {
    setSent(false);
    ask.reset();
    setOpen((v) => !v);
  }

  function call() {
    requestDial({ conversationId, contactName, thumbnail });
    setOpen(false);
  }

  async function requestPermission() {
    try {
      await ask.mutateAsync(text.trim() || undefined);
      setSent(true);
    } catch {
      // shown from ask.error
    }
  }

  const state = permission.data;
  const until =
    state?.status === "temporary" && state.expires_at
      ? new Date(state.expires_at * 1000).toLocaleDateString(tag, { day: "numeric", month: "long" })
      : null;

  return (
    <div className="relative" ref={panel}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={t("calls.callTitle")}
        title={t("calls.callTitle")}
        className="relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-control text-fg-muted transition-colors after:absolute after:-inset-1 after:content-[''] hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon"
      >
        <Phone className="h-4 w-4" aria-hidden />
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label={t("calls.callTitle")}
          className="glass-panel absolute right-0 top-10 z-40 w-[min(320px,calc(100vw-32px))] space-y-3 rounded-panel border border-glass bg-surface p-3 text-sm shadow-lg"
        >
          <p className="font-medium text-fg">{t("calls.callTitle")}</p>
          {permission.isLoading ? (
            <p className="text-fg-muted">{t("calls.checking")}</p>
          ) : permission.error ? (
            <p role="alert" className="text-danger">
              {translateOr(t, problemKey(permission.error), t("calls.problems.refused"))}
              {metaReason(permission.error) ? ` (${metaReason(permission.error)})` : ""}
            </p>
          ) : state?.can_call ? (
            <>
              <p className="text-fg-muted">
                {state.status === "permanent"
                  ? t("calls.canCallAlways")
                  : until
                    ? t("calls.canCallUntil", { date: until })
                    : t("calls.canCall")}
              </p>
              <Button size="sm" className="w-full bg-success text-white" onClick={call}>
                <Phone className="h-4 w-4" aria-hidden />
                {t("calls.callNow")}
              </Button>
              <p className="text-xs text-fg-muted">{t("calls.costNote")}</p>
            </>
          ) : state && state.status !== "no_permission" ? (
            <p className="text-fg-muted">{t("calls.cannotCall")}</p>
          ) : sent ? (
            <p role="status" className="text-success">
              {t("calls.requestSent")}
            </p>
          ) : state?.can_request ? (
            <>
              <p className="text-fg-muted">{t("calls.noPermission")}</p>
              <Textarea
                aria-label={t("calls.requestText")}
                placeholder={t("calls.requestPlaceholder")}
                value={text}
                maxLength={1024}
                rows={3}
                onChange={(e) => setText(e.target.value)}
              />
              <Button
                size="sm"
                variant="secondary"
                className="w-full"
                loading={ask.isPending}
                onClick={() => void requestPermission()}
              >
                {t("calls.requestSend")}
              </Button>
              {ask.error ? (
                <p role="alert" className="text-xs text-danger">
                  {translateOr(t, problemKey(ask.error), t("calls.problems.refused"))}
                  {metaReason(ask.error) ? ` (${metaReason(ask.error)})` : ""}
                </p>
              ) : null}
            </>
          ) : (
            <p className="text-fg-muted">{t("calls.requestLimit")}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
