"use client";

import { Bell, CheckCheck, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  NOTIFICATION_TYPE_LABELS,
  notificationHref,
  type Notification,
  useDeleteNotification,
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from "@/lib/api/notifications";
import { useLocale, useT } from "@/lib/i18n/provider";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

/**
 * Topbar notification bell.
 *
 * - Badge: ``GET /notifications/unread_count`` (polls every 60s, refreshed
 *   live by the Cable listener on ``notification.created``).
 * - Dropdown: ``GET /notifications`` page 1 — lazy, only fetches when open.
 * - Mark read / delete / mark-all-read mutations invalidate both queries.
 */
/** The backend may add types before the frontend knows them. */
function isNotificationType(type: string): type is keyof typeof NOTIFICATION_TYPE_LABELS {
  return type in NOTIFICATION_TYPE_LABELS;
}

export function NotificationBell({ accountId }: { accountId: string }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const detailsRef = useRef<HTMLDetailsElement>(null);

  const unread = useUnreadCount(accountId);
  const list = useNotifications(accountId, { enabled: open });
  const markRead = useMarkNotificationRead(accountId);
  const markAllRead = useMarkAllNotificationsRead(accountId);
  const deleteOne = useDeleteNotification(accountId);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (
        detailsRef.current &&
        !detailsRef.current.contains(e.target as Node)
      ) {
        detailsRef.current.removeAttribute("open");
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const unreadCount = unread.data ?? 0;
  const rows = list.data?.payload ?? [];

  return (
    <details
      ref={detailsRef}
      className="group relative"
      onToggle={(e) =>
        setOpen((e.currentTarget as HTMLDetailsElement).open)
      }
    >
      <summary
        aria-label={
          unreadCount
            ? t("notifications.titleUnread", { count: unreadCount })
            : t("notifications.title")
        }
        className={cn(
          "relative flex h-10 w-10 cursor-pointer list-none items-center justify-center rounded-control text-fg-muted transition-colors",
          "after:absolute after:-inset-0.5 after:content-['']",
          "hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
        )}
      >
        <Bell className="h-5 w-5" aria-hidden />
        {unreadCount > 0 ? (
          <span
            aria-hidden
            className="absolute right-1 top-1 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-danger-solid px-1 text-[10px] font-semibold leading-none text-white tabular-nums"
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </summary>

      <div
        className="absolute right-0 z-30 mt-1.5 flex w-[22rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-md border border-glass bg-surface-2 shadow-menu"
        role="dialog"
        aria-label={t("notifications.title")}
      >
        <div className="flex items-center justify-between border-b border-glass px-3 py-2.5">
          <h2 className="text-sm font-medium text-fg">
            {t("notifications.title")}
          </h2>
          <button
            type="button"
            onClick={() => markAllRead.mutate()}
            disabled={!unreadCount || markAllRead.isPending}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-fg-muted transition-colors hover:bg-hover-glass hover:text-fg disabled:opacity-40"
          >
            <CheckCheck className="h-3.5 w-3.5" aria-hidden />
            {t("notifications.markAll")}
          </button>
        </div>

        <ul className="max-h-[28rem] divide-y divide-glass overflow-y-auto">
          {list.isLoading && open ? (
            <li className="px-3 py-6 text-center text-sm text-fg-muted">
              {t("common.loading")}
            </li>
          ) : null}
          {!list.isLoading && rows.length === 0 ? (
            <li className="px-3 py-8 text-center text-sm text-fg-muted">
              {t("notifications.empty")}
            </li>
          ) : null}
          {rows.map((n) => (
            <NotificationRow
              key={n.id}
              accountId={accountId}
              notification={n}
              onMarkRead={() => markRead.mutate(n.id)}
              onDelete={() => deleteOne.mutate(n.id)}
            />
          ))}
        </ul>

        {rows.length > 0 ? (
          <div className="border-t border-glass bg-surface px-3 py-2 text-right">
            <Link
              href={`/accounts/${accountId}/notifications`}
              className="text-xs font-medium text-info hover:underline"
              onClick={() => {
                detailsRef.current?.removeAttribute("open");
                setOpen(false);
              }}
            >
              {t("notifications.seeAll")}
            </Link>
          </div>
        ) : null}
      </div>
    </details>
  );
}

function NotificationRow({
  accountId,
  notification: n,
  onMarkRead,
  onDelete,
}: {
  accountId: string;
  notification: Notification;
  onMarkRead: () => void;
  onDelete: () => void;
}) {
  const isUnread = n.read_at == null;
  const t = useT();
  const locale = useLocale();
  const label = isNotificationType(n.notification_type)
    ? t(`notifications.types.${n.notification_type}`)
    : t("notifications.fallback");
  const href = notificationHref(n, accountId);
  const taskTitle =
    n.primary_actor_type === "CrmActivity" && typeof n.meta?.title === "string"
      ? n.meta.title
      : null;

  const body = (
    <div className="flex items-start gap-2">
      {isUnread ? (
        <span
          aria-hidden
          className="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full bg-neon"
        />
      ) : (
        <span aria-hidden className="mt-1.5 inline-block h-2 w-2 shrink-0" />
      )}
      <div className="min-w-0 flex-1">
        <p
          className={cn(
            "truncate text-sm",
            isUnread ? "font-medium text-fg" : "text-fg-muted",
          )}
        >
          {label}
        </p>
        <p className="mt-0.5 text-xs text-fg-muted">
          {taskTitle ??
            (n.primary_actor?.display_id != null
              ? t("conversations.list.fallbackName", { id: n.primary_actor.display_id })
              : null)}
          {(taskTitle || n.primary_actor?.display_id != null) && n.last_activity_at
            ? " · "
            : null}
          {relativeTime(n.last_activity_at, locale)}
        </p>
      </div>
    </div>
  );

  return (
    <li className="group/row flex items-start gap-1 px-3 py-2 transition-colors hover:bg-hover-glass">
      {href ? (
        <Link href={href} onClick={onMarkRead} className="min-w-0 flex-1">
          {body}
        </Link>
      ) : (
        <button
          type="button"
          onClick={onMarkRead}
          className="min-w-0 flex-1 text-left"
        >
          {body}
        </button>
      )}
      <button
        type="button"
        aria-label={t("notifications.delete")}
        onClick={onDelete}
        className="mt-1 rounded-md p-1 text-fg-muted opacity-0 transition-opacity hover:bg-surface hover:text-danger focus-visible:opacity-100 group-hover/row:opacity-100"
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden />
      </button>
    </li>
  );
}
