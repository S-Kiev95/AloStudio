import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** An approved WhatsApp template as the composer needs it. `variables` is the
 *  sorted, distinct `{{n}}` positions in the body — one input each. */
export type WhatsappTemplate = {
  name: string;
  language: string | null;
  status: string;
  category: string | null;
  body_text: string | null;
  variables: number[];
};

function base(accountId: string, inboxId: number): string {
  return `/api/v1/accounts/${accountId}/inboxes/${inboxId}/whatsapp/templates`;
}

/** Cached approved templates for a WhatsApp inbox. */
export function useWhatsappTemplates(
  accountId: string,
  inboxId: number | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["whatsapp-templates", accountId, inboxId],
    queryFn: () =>
      apiFetch<{ templates: WhatsappTemplate[]; last_updated: number | null }>(
        base(accountId, inboxId as number),
      ),
    enabled: enabled && inboxId != null,
    retry: false,
  });
}

/** Refresh the cached templates from Meta. */
export function useSyncWhatsappTemplates(
  accountId: string,
  inboxId: number | null,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ templates: WhatsappTemplate[] }>(
        `${base(accountId, inboxId as number)}/sync`,
        { method: "POST" },
      ),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ["whatsapp-templates", accountId, inboxId],
      }),
  });
}
