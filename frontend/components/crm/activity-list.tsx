"use client";

import { CalendarClock, ListTodo, Mail, Phone, Users } from "lucide-react";

import { Avatar } from "@/components/ui/avatar";
import { type Activity, type ActivityKind, useUpdateActivity } from "@/lib/api/crm";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

const KIND_ICON: Record<ActivityKind, typeof Phone> = {
  task: ListTodo,
  call: Phone,
  meeting: Users,
  email: Mail,
};

type Group = "overdue" | "today" | "upcoming" | "undated" | "done";

const GROUP_LABEL: Record<Group, MessageKey> = {
  overdue: "activities.groups.overdue",
  today: "activities.groups.today",
  upcoming: "activities.groups.upcoming",
  undated: "activities.groups.undated",
  done: "activities.groups.done",
};

function groupOf(a: Activity, now: Date): Group {
  if (a.done_at) return "done";
  if (!a.due_at) return "undated";
  const due = new Date(a.due_at * 1000);
  if (due < now) return "overdue";
  const endOfToday = new Date(now);
  endOfToday.setHours(23, 59, 59, 999);
  return due <= endOfToday ? "today" : "upcoming";
}

/** Activities grouped as overdue / today / upcoming / undated (or done),
 *  each with a checkbox to mark it done. */
export function ActivityList({
  accountId,
  items,
  onOpen,
  showContact = true,
}: {
  accountId: string;
  items: Activity[];
  onOpen: (a: Activity) => void;
  showContact?: boolean;
}) {
  const t = useT();
  const intlTag = useIntlTag();
  const update = useUpdateActivity(accountId);
  const now = new Date();
  const order: Group[] = ["overdue", "today", "upcoming", "undated", "done"];
  const groups = new Map<Group, Activity[]>();
  for (const a of items) {
    const g = groupOf(a, now);
    groups.set(g, [...(groups.get(g) ?? []), a]);
  }

  return (
    <div className="space-y-4">
      {order
        .filter((g) => groups.has(g))
        .map((g) => (
          <section key={g} aria-label={t(GROUP_LABEL[g])}>
            <h3
              className={cn(
                "mb-1.5 text-xs font-medium uppercase tracking-wide",
                g === "overdue" ? "text-danger" : "text-fg-muted",
              )}
            >
              {t(GROUP_LABEL[g])}
            </h3>
            <ul className="divide-y divide-glass rounded-md border border-glass bg-surface">
              {groups.get(g)?.map((a) => {
                const Icon = KIND_ICON[a.kind] ?? ListTodo;
                const due = a.due_at ? new Date(a.due_at * 1000) : null;
                return (
                  <li key={a.id} className="flex items-center gap-3 px-3 py-2.5">
                    <input
                      type="checkbox"
                      aria-label={t("activities.markDone", { title: a.title })}
                      checked={a.done_at != null}
                      disabled={update.isPending}
                      onChange={(e) =>
                        update.mutate({ id: a.id, patch: { done: e.target.checked } })
                      }
                      className="h-4 w-4 shrink-0 cursor-pointer rounded border-glass accent-neon"
                    />
                    <button
                      type="button"
                      onClick={() => onOpen(a)}
                      className="flex min-w-0 flex-1 items-center gap-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                    >
                      <Icon className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
                      <span className="min-w-0 flex-1">
                        <span
                          className={cn(
                            "block truncate text-sm",
                            a.done_at ? "text-fg-muted line-through" : "font-medium text-fg",
                          )}
                        >
                          {a.title}
                        </span>
                        {(showContact && a.contact) || a.opportunity ? (
                          <span className="block truncate text-xs text-fg-muted">
                            {[showContact ? a.contact?.name : null, a.opportunity?.title]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        ) : null}
                      </span>
                      {due ? (
                        <span
                          className={cn(
                            "flex shrink-0 items-center gap-1 font-numeric text-xs tabular-nums",
                            g === "overdue" ? "text-danger" : "text-fg-muted",
                          )}
                        >
                          <CalendarClock className="h-3.5 w-3.5" aria-hidden />
                          {due.toLocaleString(intlTag, {
                            day: "numeric",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      ) : null}
                      {a.owner ? <Avatar name={a.owner.name} size="xs" /> : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
    </div>
  );
}
