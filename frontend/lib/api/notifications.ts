import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** ----------------------------------------------------------------------- */
/* Types — mirror app/domains/notifications/presenters.py                    */
/** ----------------------------------------------------------------------- */
export type NotificationType =
  | "conversation_creation"
  | "conversation_assignment"
  | "assigned_conversation_new_message"
  | "conversation_mention"
  | "participating_conversation_new_message"
  | "sla_missed_first_response"
  | "sla_missed_next_response"
  | "sla_missed_resolution";

export type NotificationActor = {
  id: number;
  display_id: number | null;
  account_id: number | null;
  inbox_id: number | null;
  contact_id: number | null;
  assignee_id: number | null;
  status: string;
  priority: string | null;
  uuid: string | null;
};

export type Notification = {
  id: number;
  notification_type: NotificationType;
  primary_actor_type: string | null;
  primary_actor_id: number | null;
  secondary_actor_type: string | null;
  secondary_actor_id: number | null;
  primary_actor?: NotificationActor;
  read_at: number | null;
  snoozed_until: number | null;
  last_activity_at: number | null;
  created_at: number | null;
  account_id: number | null;
  user_id: number | null;
  meta: Record<string, unknown>;
};

export type NotificationIndex = {
  meta: { count: number; unread_count: number; current_page: number };
  payload: Notification[];
};

export type NotificationSettings = {
  id: number;
  account_id: number;
  user_id: number;
  selected_email_flags: NotificationType[];
  selected_push_flags: NotificationType[];
};

export const NOTIFICATION_TYPE_LABELS: Record<NotificationType, string> = {
  conversation_creation: "Conversación creada",
  conversation_assignment: "Conversación asignada",
  assigned_conversation_new_message: "Mensaje nuevo en conversación asignada",
  conversation_mention: "Te mencionaron",
  participating_conversation_new_message:
    "Mensaje nuevo donde participas",
  sla_missed_first_response: "SLA: primera respuesta vencida",
  sla_missed_next_response: "SLA: siguiente respuesta vencida",
  sla_missed_resolution: "SLA: resolución vencida",
};

export const NOTIFICATION_TYPES: NotificationType[] = [
  "conversation_creation",
  "conversation_assignment",
  "assigned_conversation_new_message",
  "conversation_mention",
  "participating_conversation_new_message",
];

/** ----------------------------------------------------------------------- */
/* URL builders                                                              */
/** ----------------------------------------------------------------------- */
function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/notifications`;
}

function settingsBase(accountId: string): string {
  return `/api/v1/accounts/${accountId}/notification_settings`;
}

/** ----------------------------------------------------------------------- */
/* Queries                                                                   */
/** ----------------------------------------------------------------------- */
export function useNotifications(
  accountId: string,
  opts?: { status?: "unread"; page?: number; enabled?: boolean },
) {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.page) params.set("page", String(opts.page));
  const qs = params.toString();
  return useQuery({
    queryKey: ["notifications", accountId, opts?.status ?? "all", opts?.page ?? 1],
    queryFn: () =>
      apiFetch<NotificationIndex>(`${base(accountId)}${qs ? `?${qs}` : ""}`),
    enabled: opts?.enabled ?? true,
    staleTime: 30_000,
  });
}

export function useUnreadCount(accountId: string) {
  return useQuery({
    queryKey: ["notifications", accountId, "unread_count"],
    queryFn: () => apiFetch<number>(`${base(accountId)}/unread_count`),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

/** ----------------------------------------------------------------------- */
/* Mutations                                                                 */
/** ----------------------------------------------------------------------- */
function invalidateAll(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["notifications", accountId] });
}

export function useMarkNotificationRead(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Notification>(`${base(accountId)}/${id}/read`, {
        method: "POST",
      }),
    onSuccess: () => invalidateAll(qc, accountId),
  });
}

export function useMarkAllNotificationsRead(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<Record<string, never>>(`${base(accountId)}/read_all`, {
        method: "POST",
      }),
    onSuccess: () => invalidateAll(qc, accountId),
  });
}

export function useDeleteNotification(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidateAll(qc, accountId),
  });
}

/** ----------------------------------------------------------------------- */
/* Settings                                                                  */
/** ----------------------------------------------------------------------- */
export function useNotificationSettings(accountId: string) {
  return useQuery({
    queryKey: ["notification_settings", accountId],
    queryFn: () =>
      apiFetch<NotificationSettings>(settingsBase(accountId)),
    staleTime: 5 * 60_000,
  });
}

export function useUpdateNotificationSettings(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: {
      selected_email_flags?: NotificationType[];
      selected_push_flags?: NotificationType[];
    }) =>
      apiFetch<NotificationSettings>(settingsBase(accountId), {
        method: "PATCH",
        body: JSON.stringify(patch),
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["notification_settings", accountId] }),
  });
}
