import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Mirrors backend's ALLOWED_WEBHOOK_EVENTS (v4.13.0). */
export const WEBHOOK_EVENTS = [
  "conversation_created",
  "conversation_updated",
  "conversation_status_changed",
  "conversation_typing_on",
  "conversation_typing_off",
  "message_created",
  "message_updated",
  "contact_created",
  "contact_updated",
  "inbox_created",
  "inbox_updated",
  "webwidget_triggered",
] as const;
export type WebhookEvent = (typeof WEBHOOK_EVENTS)[number];

export type Webhook = {
  id: number;
  name: string | null;
  url: string;
  account_id: number;
  subscriptions: WebhookEvent[];
  secret: string | null;
  inbox?: { id: number; name: string } | null;
};

export type WebhookInput = {
  name?: string | null;
  url: string;
  inbox_id?: number | null;
  subscriptions: WebhookEvent[];
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/webhooks`;
}

export function useWebhooks(accountId: string) {
  return useQuery({
    queryKey: ["webhooks", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: { webhooks: Webhook[] } }>(
        base(accountId),
      );
      return res.payload.webhooks;
    },
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["webhooks", accountId] });
}

export function useCreateWebhook(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: WebhookInput) => {
      const res = await apiFetch<{ payload: { webhook: Webhook } }>(
        base(accountId),
        { method: "POST", body: JSON.stringify({ webhook: input }) },
      );
      return res.payload.webhook;
    },
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateWebhook(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; patch: WebhookInput }) => {
      const res = await apiFetch<{ payload: { webhook: Webhook } }>(
        `${base(accountId)}/${input.id}`,
        { method: "PATCH", body: JSON.stringify({ webhook: input.patch }) },
      );
      return res.payload.webhook;
    },
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteWebhook(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
