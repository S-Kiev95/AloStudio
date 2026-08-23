import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { BlockDocument } from "@/lib/inboxes/email-blocks";
import type { TemplateDesign } from "@/lib/inboxes/email-template-design";

import { apiFetch } from "./fetcher";

export type EmailTemplate = {
  id: number;
  name: string;
  template_html: string;
  /** Whichever editor produced the HTML: the block document, the flat
   *  design, or null when the markup was written by hand. */
  template_design: BlockDocument | TemplateDesign | null;
  created_at: string | null;
  updated_at: string | null;
};

const key = (accountId: string) => ["email-templates", accountId];
const base = (accountId: string) =>
  `/api/v1/accounts/${accountId}/email_templates`;

export function useEmailTemplates(accountId: string) {
  return useQuery({
    queryKey: key(accountId),
    queryFn: async () => {
      const res = await apiFetch<{ payload: EmailTemplate[] }>(base(accountId));
      return res.payload;
    },
  });
}

export function useCreateEmailTemplate(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; template_html?: string }) =>
      apiFetch<EmailTemplate>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(accountId) }),
  });
}

export function useUpdateEmailTemplate(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<Pick<EmailTemplate, "name" | "template_html" | "template_design">>;
    }) =>
      apiFetch<EmailTemplate>(`${base(accountId)}/${id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(accountId) }),
  });
}

export function useDeleteEmailTemplate(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<{ message: string }>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(accountId) }),
  });
}

/** Mail the template to a real address, through a mailbox's own SMTP.
 *
 *  The dashboard preview is a browser rendering, and a browser is the one
 *  place this message will never be read. */
export function useTestSendEmailTemplate(accountId: string) {
  return useMutation({
    mutationFn: ({
      id,
      inboxId,
      to,
    }: {
      id: number;
      inboxId: number;
      to: string;
    }) =>
      apiFetch<{ message: string }>(`${base(accountId)}/${id}/test_send`, {
        method: "POST",
        body: JSON.stringify({ inbox_id: inboxId, to }),
      }),
  });
}
