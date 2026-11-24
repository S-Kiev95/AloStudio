import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { BlockDocument, CanvasKind } from "@/lib/inboxes/email-blocks";
import type { TemplateDesign } from "@/lib/inboxes/email-template-design";

import { apiFetch } from "./fetcher";

export type TemplateScope = "organization" | "personal";

export type EmailTemplate = {
  id: number;
  name: string;
  scope?: TemplateScope;
  user_id?: number | null;
  is_default?: boolean;
  template_html: string;
  /** Whichever editor produced the HTML: the block document, the flat
   *  design, or null when the markup was written by hand. */
  template_design: BlockDocument | TemplateDesign | null;
  created_at: string | null;
  updated_at: string | null;
};

export type EmailSignature = {
  id: number | null;
  scope: TemplateScope;
  signature_html: string;
  signature_text: string;
  signature_design: BlockDocument | null;
  fallback_text: string;
  created_at: string | null;
  updated_at: string | null;
};

export type GeneratedEmailDesign = {
  html: string;
  notes: string;
  mode: string;
  seen: string | null;
};

export type EmailAiStatus = {
  enabled: boolean;
  media: boolean;
};

const key = (accountId: string, scope: TemplateScope = "organization") =>
  scope === "personal"
    ? ["email-templates", accountId, "personal"]
    : ["email-templates", accountId];

const sigKey = (accountId: string, scope: TemplateScope) => [
  "email-signatures",
  accountId,
  scope,
];

const base = (accountId: string, scope: TemplateScope = "organization") =>
  scope === "personal"
    ? `/api/v1/accounts/${accountId}/email_templates/personal`
    : `/api/v1/accounts/${accountId}/email_templates`;

const sigBase = (accountId: string, scope: TemplateScope) =>
  `/api/v1/accounts/${accountId}/email_signatures/${scope}`;

export function useEmailTemplates(
  accountId: string,
  options: { scope?: TemplateScope; enabled?: boolean } = {},
) {
  const scope = options.scope ?? "organization";
  return useQuery({
    queryKey: key(accountId, scope),
    enabled: options.enabled ?? true,
    queryFn: async () => {
      const res = await apiFetch<{ payload: EmailTemplate[] }>(
        base(accountId, scope),
      );
      return res.payload;
    },
  });
}

export function useCreateEmailTemplate(
  accountId: string,
  scope: TemplateScope = "organization",
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      name: string;
      template_html?: string;
      template_design?: BlockDocument | TemplateDesign | null;
      is_default?: boolean;
    }) =>
      apiFetch<EmailTemplate>(base(accountId, scope), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(accountId, scope) }),
  });
}

export function useUpdateEmailTemplate(
  accountId: string,
  scope: TemplateScope = "organization",
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<
        Pick<
          EmailTemplate,
          "name" | "template_html" | "template_design" | "is_default"
        >
      >;
    }) =>
      apiFetch<EmailTemplate>(`${base(accountId, scope)}/${id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(accountId, scope) }),
  });
}

export function useDeleteEmailTemplate(
  accountId: string,
  scope: TemplateScope = "organization",
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<{ message: string }>(`${base(accountId, scope)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(accountId, scope) }),
  });
}

/** Mail the template to a real address, through a mailbox's own SMTP. */
export function useTestSendEmailTemplate(
  accountId: string,
  scope: TemplateScope = "organization",
) {
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
      apiFetch<{ message: string }>(
        `${base(accountId, scope)}/${id}/test_send`,
        {
          method: "POST",
          body: JSON.stringify({ inbox_id: inboxId, to }),
        },
      ),
  });
}

export function useEmailSignature(
  accountId: string,
  scope: TemplateScope,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: sigKey(accountId, scope),
    enabled: options.enabled ?? true,
    queryFn: () => apiFetch<EmailSignature>(sigBase(accountId, scope)),
  });
}

export function useUpdateEmailSignature(
  accountId: string,
  scope: TemplateScope,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: {
      signature_html?: string;
      signature_text?: string;
      signature_design?: BlockDocument | null;
    }) =>
      apiFetch<EmailSignature>(sigBase(accountId, scope), {
        method: "PUT",
        body: JSON.stringify(patch),
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: sigKey(accountId, scope) }),
  });
}

export function useEmailAiStatus(accountId: string) {
  return useQuery({
    queryKey: ["email-templates-ai-status", accountId],
    queryFn: () =>
      apiFetch<EmailAiStatus>(
        `/api/v1/accounts/${accountId}/email_templates/ai_status`,
      ),
    staleTime: 60_000,
    retry: false,
  });
}

export function useGenerateEmailDesign(accountId: string) {
  return useMutation({
    mutationFn: (input: {
      prompt: string;
      image?: string | null;
      kind: CanvasKind;
    }) =>
      apiFetch<GeneratedEmailDesign>(
        `/api/v1/accounts/${accountId}/email_templates/generate`,
        {
          method: "POST",
          body: JSON.stringify(input),
        },
      ),
  });
}
