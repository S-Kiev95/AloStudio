"use client";

import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useMessageSearch } from "@/lib/api/conversations";
import { useLocale, useT } from "@/lib/i18n/provider";
import { shortDate } from "@/lib/time";

import { Highlighted } from "./highlighted";

/** Search inside the open conversation (F8): "where in this chat did we talk
 *  about financing". Same search as the list — words and meaning — scoped
 *  to this conversation; picking a hit opens the thread at that message. */
export function ChatSearch({
  accountId,
  displayId,
  onPick,
  onClose,
}: {
  accountId: string;
  displayId: number;
  onPick: (messageId: number) => void;
  onClose: () => void;
}) {
  const t = useT();
  const locale = useLocale();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => input.current?.focus(), []);
  // A request per keystroke would search "f", "fi", "fin"…
  useEffect(() => {
    const id = setTimeout(() => setQ(text.trim()), 300);
    return () => clearTimeout(id);
  }, [text]);

  const search = useMessageSearch(accountId, q, 1, displayId);
  const hits = search.data?.payload ?? [];

  return (
    <div className="shrink-0 border-b border-glass bg-surface-2 px-4 py-2">
      <div className="flex items-center gap-2">
        <Search className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
        <input
          ref={input}
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
          }}
          aria-label={t("conversations.view.searchInChat")}
          placeholder={t("conversations.view.searchInChatPlaceholder")}
          className="min-w-0 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-fg-muted"
        />
        <button
          type="button"
          onClick={onClose}
          aria-label={t("conversations.view.closeSearch")}
          className="inline-flex h-7 w-7 items-center justify-center rounded-control text-fg-muted hover:bg-hover-glass hover:text-fg"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {q ? (
        search.isLoading ? (
          <p className="pt-2 text-xs text-fg-muted">{t("common.loading")}</p>
        ) : hits.length === 0 ? (
          <p className="pt-2 text-xs text-fg-muted">
            {t("conversations.view.noHitsInChat")}
          </p>
        ) : (
          <ul className="mt-2 max-h-56 divide-y divide-glass overflow-y-auto rounded-md border border-glass bg-surface">
            {hits.map((hit) => (
              <li key={hit.message_id}>
                <button
                  type="button"
                  onClick={() => onPick(hit.message_id)}
                  className="block w-full px-3 py-2 text-left hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neon"
                >
                  <div className="flex items-center gap-1.5 text-[11px] text-fg-muted">
                    {hit.created_at ? (
                      <span className="font-numeric tabular-nums">
                        {shortDate(hit.created_at, locale)}
                      </span>
                    ) : null}
                    {hit.match === "meaning" ? (
                      <span className="rounded-pill bg-primary/15 px-1.5 text-fg">
                        {t("conversations.list.related")}
                      </span>
                    ) : null}
                  </div>
                  <p className="line-clamp-2 text-sm text-fg-muted">
                    <Highlighted text={hit.snippet} spans={hit.highlights} />
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </div>
  );
}
