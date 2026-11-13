"use client";

import { Search, User as UserIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useContacts, useSearchContacts } from "@/lib/api/contacts";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export type PickedContact = { id: number; name: string | null };

/** Optional contact for a CRM record: search, pick, change or clear it.
 *  ``locked`` keeps the contact fixed (opened from that contact's page). */
export function ContactPicker({
  accountId,
  inputId,
  value,
  onChange,
  locked = false,
}: {
  accountId: string;
  inputId: string;
  value: PickedContact | null;
  onChange: (contact: PickedContact | null) => void;
  locked?: boolean;
}) {
  const t = useT();
  const [picking, setPicking] = useState(false);
  const [query, setQuery] = useState("");
  const search = useSearchContacts(accountId, query, 1);
  const recent = useContacts(accountId, 1);
  const candidates =
    query.trim().length > 0 ? (search.data?.payload ?? []) : (recent.data?.payload ?? []);

  if (value && !picking) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-control border border-glass bg-field px-3 py-2 text-sm">
        <span className="flex min-w-0 items-center gap-2">
          <UserIcon className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
          <span className="truncate font-medium text-fg">
            {value.name || t("conversations.contact.fallbackName", { id: value.id })}
          </span>
        </span>
        {locked ? null : (
          <span className="flex gap-1">
            <Button type="button" size="sm" variant="ghost" onClick={() => setPicking(true)}>
              {t("agenda.dialog.change")}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => onChange(null)}>
              {t("common.remove")}
            </Button>
          </span>
        )}
      </div>
    );
  }
  if (!picking) {
    return (
      <Button type="button" size="sm" variant="secondary" onClick={() => setPicking(true)}>
        {t("opportunities.pickContact")}
      </Button>
    );
  }
  return (
    <div className="space-y-2">
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
          aria-hidden
        />
        <Input
          id={inputId}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("agenda.dialog.searchPlaceholder")}
          className="pl-9"
        />
      </div>
      {candidates.length === 0 ? (
        <p className="text-xs text-fg-muted">{t("agenda.dialog.noContacts")}</p>
      ) : (
        <ul className="max-h-40 divide-y divide-glass overflow-y-auto rounded-md border border-glass bg-surface">
          {candidates.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => {
                  onChange({ id: c.id, name: c.name });
                  setPicking(false);
                }}
                className={cn(
                  "flex w-full flex-col items-start px-3 py-2 text-left text-sm hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon",
                  value?.id === c.id && "bg-focused text-lit",
                )}
              >
                <span className="font-medium text-fg">
                  {c.name ||
                    c.email ||
                    c.phone_number ||
                    t("conversations.contact.fallbackName", { id: c.id })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
