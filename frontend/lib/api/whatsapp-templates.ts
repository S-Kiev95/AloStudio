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

export type WhatsappTemplateCategory =
  | "UTILITY"
  | "MARKETING"
  | "AUTHENTICATION";

export type WhatsappTemplateButton =
  | { type: "QUICK_REPLY"; text: string }
  | {
      type: "URL";
      text: string;
      url: string;
      example?: string[];
    }
  | {
      type: "PHONE_NUMBER";
      text: string;
      phone_number: string;
    };

export type WhatsappTemplateComponent =
  | {
      type: "HEADER";
      format?: "TEXT" | string;
      text?: string;
      example?: { header_text?: string[] };
    }
  | {
      type: "BODY";
      text: string;
      example?: { body_text?: string[][] };
    }
  | {
      type: "FOOTER";
      text: string;
    }
  | {
      type: "BUTTONS";
      buttons: WhatsappTemplateButton[];
    };

/** Full template returned by `GET ?status=all` and management mutations. */
export type WhatsappTemplateFull = WhatsappTemplate & {
  id: string | null;
  rejected_reason?: string | null;
  quality_score?: unknown;
  components?: WhatsappTemplateComponent[];
};

export type CreateWhatsappTemplateInput = {
  name: string;
  category: WhatsappTemplateCategory;
  language: string;
  components: WhatsappTemplateComponent[];
};

export type EditWhatsappTemplateInput = {
  id: string;
  category?: WhatsappTemplateCategory;
  components: WhatsappTemplateComponent[];
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

/** All templates (`?status=all`) for the inbox settings management panel. */
export function useAllWhatsappTemplates(
  accountId: string,
  inboxId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: ["whatsapp-templates", accountId, inboxId, "all"],
    queryFn: () =>
      apiFetch<{
        templates: WhatsappTemplateFull[];
        last_updated: number | null;
      }>(`${base(accountId, inboxId as number)}?status=all`),
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

function updateCachedAllTemplates(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
  inboxId: number | null,
  templates?: WhatsappTemplateFull[],
) {
  if (Array.isArray(templates)) {
    qc.setQueryData<{
      templates: WhatsappTemplateFull[];
      last_updated: number | null;
    }>(["whatsapp-templates", accountId, inboxId, "all"], (old) => ({
      templates,
      last_updated: old?.last_updated ?? Math.floor(Date.now() / 1000),
    }));
  } else {
    void qc.invalidateQueries({
      queryKey: ["whatsapp-templates", accountId, inboxId, "all"],
    });
  }
  void qc.invalidateQueries({
    queryKey: ["whatsapp-templates", accountId, inboxId],
    exact: true,
  });
}

/** Submit a new template to Meta for review (admin only). */
export function useCreateWhatsappTemplate(
  accountId: string,
  inboxId: number | null,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateWhatsappTemplateInput) =>
      apiFetch<{
        result: Record<string, unknown>;
        templates: WhatsappTemplateFull[];
      }>(base(accountId, inboxId as number), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: (data) =>
      updateCachedAllTemplates(qc, accountId, inboxId, data?.templates),
  });
}

/** Edit an existing template on Meta (admin only; sends it back to review). */
export function useEditWhatsappTemplate(
  accountId: string,
  inboxId: number | null,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: EditWhatsappTemplateInput) =>
      apiFetch<{
        result: Record<string, unknown>;
        templates: WhatsappTemplateFull[];
      }>(`${base(accountId, inboxId as number)}/${encodeURIComponent(id)}`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (data) =>
      updateCachedAllTemplates(qc, accountId, inboxId, data?.templates),
  });
}

export const useUpdateWhatsappTemplate = useEditWhatsappTemplate;

/** Delete a template on Meta (admin only). */
export function useDeleteWhatsappTemplate(
  accountId: string,
  inboxId: number | null,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ templates: WhatsappTemplateFull[] }>(
        `${base(accountId, inboxId as number)}/${encodeURIComponent(id)}`,
        { method: "DELETE" },
      ),
    onSuccess: (data) =>
      updateCachedAllTemplates(qc, accountId, inboxId, data?.templates),
  });
}
