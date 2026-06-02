"use client";

import { Bell, CheckCheck, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  NOTIFICATION_TYPE_LABELS,
  type Notification,
  useDeleteNotification,
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from "@/lib/api/notifications";
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
export function NotificationBell({ accountId }: { accountId: string }) {
  const [open, setOpen] = useState(false);
  const detailsRef = useRef<HTMLDetailsElement>(null);

  const unread = useUnreadCount(accountId);
  const list = useNotifications(accountId, { enabled: open });
  const markRead = useMarkNotificationRead(accountId);
  const markAllRead = useMarkAllNotificationsRead(accountId);
  const deleteOne = useDeleteNotification(accountId);

  // Close the dropdown when clicking outside.
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
        aria-label={`Notificaciones${unreadCount ? ` (${unreadCount} sin leer)` : ""}`}
        className={cn(
          "relative flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-md text-fg-muted",
          "hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <Bell className="h-5 w-5" aria-hidden />
        {unreadCount > 0 ? (
          <span
            aria-hidden
            className="absolute right-1 top-1 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold leading-none text-white"
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </summary>

      <div
        className="absolute right-0 z-30 mt-1 flex w-[22rem] flex-col overflow-hidden rounded-md border border-border bg-surface shadow-lg"
        role="dialog"
        aria-label="Notificaciones"
      >
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <h2 className="text-sm font-semibold text-fg">Notificaciones</h2>
          <button
            type="button"
            onClick={() => markAllRead.mutate()}
            disabled={!unreadCount || markAllRead.isPending}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-fg-muted hover:bg-surface-2 disabled:opacity-40"
          >
            <CheckCheck className="h-3.5 w-3.5" aria-hidden />
            Marcar todo
          </button>
        </div>

        <ul className="max-h-[28rem] divide-y divide-border overflow-y-auto">
          {list.isLoading && open ? (
            <li className="px-3 py-6 text-center text-sm text-fg-muted">
              Cargando…
            </li>
          ) : null}
          {!list.isLoading && rows.length === 0 ? (
            <li className="px-3 py-8 text-center text-sm text-fg-muted">
              No tienes notificaciones.
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
          <div className="border-t border-border bg-surface-2 px-3 py-2 text-right">
            <Link
              href={`/accounts/${accountId}/notifications`}
              className="text-xs font-medium text-primary hover:underline"
              onClick={() => {
                detailsRef.current?.removeAttribute("open");
                setOpen(false);
              }}
            >
              Ver todas
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
  const label = NOTIFICATION_TYPE_LABELS[n.notification_type] ?? "Notificación";
  const href =
    n.primary_actor?.display_id != null
      ? `/accounts/${accountId}/conversations/${n.primary_actor.display_id}`
      : undefined;

  const body = (
    <div className="flex items-start gap-2">
      {isUnread ? (
        <span
          aria-hidden
          className="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full bg-primary"
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
          {n.primary_actor?.display_id != null
            ? `Conversación #${n.primary_actor.display_id}`
            : null}
          {n.primary_actor?.display_id != null && n.last_activity_at
            ? " · "
            : null}
          {relativeTime(n.last_activity_at)}
        </p>
      </div>
    </div>
  );

  return (
    <li className="group/row flex items-start gap-1 px-3 py-2 hover:bg-surface-2">
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
        aria-label="Borrar notificación"
        onClick={onDelete}
        className="mt-1 rounded-md p-1 text-fg-muted opacity-0 hover:bg-surface focus-visible:opacity-100 group-hover/row:opacity-100"
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden />
      </button>
    </li>
  );
}
