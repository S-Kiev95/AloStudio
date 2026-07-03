import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Agent } from "./account";
import { apiFetch } from "./fetcher";

/** Slim inbox shape returned by contactable_inboxes. */
export type ContactInbox = {
  source_id: string;
  inbox: {
    id: number;
    avatar_url: string;
    channel_id: number;
    name: string;
    channel_type: string;
    provider: string | null;
  };
};

export type Contact = {
  id: number;
  name: string | null;
  email: string | null;
  phone_number: string | null;
  blocked: boolean;
  identifier: string | null;
  thumbnail: string;
  availability_status: "online" | "offline";
  additional_attributes: Record<string, unknown>;
  custom_attributes: Record<string, unknown>;
  last_activity_at?: number | null;
  created_at?: number | null;
  contact_inboxes?: ContactInbox[];
};

export type ContactsPage = {
  meta: { count: number; current_page: number };
  payload: Contact[];
};

export type ContactsSearchPage = {
  meta: { count: number; current_page: number; has_more: boolean };
  payload: Contact[];
};

export type ContactInput = {
  name?: string;
  email?: string | null;
  phone_number?: string | null;
  identifier?: string | null;
  blocked?: boolean;
  additional_attributes?: Record<string, unknown>;
  custom_attributes?: Record<string, unknown>;
  /** Optional — create-only — bind to an inbox at the same time. */
  inbox_id?: number;
  source_id?: string;
};

export type ContactableInbox = {
  inbox: {
    id: number;
    avatar_url: string;
    channel_id: number;
    name: string;
    channel_type: string;
    provider: string | null;
  };
  source_id: string;
};

export type ContactNote = {
  id: number;
  content: string;
  /** Always null in the wire — bug-for-bug parity with the jbuilder. */
  account_id: null;
  contact_id: null;
  created_at: number | null;
  updated_at: number | null;
  user?: Agent;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/contacts`;
}

// ---------------------------------------------------------------------------
// List + search
// ---------------------------------------------------------------------------
/** One row of the companies roll-up (``GET /contacts/companies``). */
export type Company = { name: string; count: number };

/** ``GET /contacts`` — paginated, optionally filtered by company. */
export function useContacts(accountId: string, page = 1, company?: string) {
  return useQuery({
    queryKey: ["contacts", accountId, "list", page, company ?? null],
    queryFn: () => {
      const sp = new URLSearchParams({ page: String(page) });
      if (company) sp.set("company", company);
      return apiFetch<ContactsPage>(`${base(accountId)}?${sp}`);
    },
    placeholderData: (prev) => prev,
  });
}

/** ``GET /contacts/companies`` — contacts rolled up by company_name. */
export function useContactCompanies(accountId: string) {
  return useQuery({
    queryKey: ["contact-companies", accountId],
    queryFn: () => apiFetch<Company[]>(`${base(accountId)}/companies`),
  });
}

/** ``GET /contacts/search?q=…`` — empty ``q`` falls back to the index. */
export function useSearchContacts(
  accountId: string,
  q: string,
  page = 1,
) {
  const trimmed = q.trim();
  return useQuery({
    queryKey: ["contacts", accountId, "search", trimmed, page],
    queryFn: () => {
      const sp = new URLSearchParams({ q: trimmed, page: String(page) });
      return apiFetch<ContactsSearchPage>(`${base(accountId)}/search?${sp}`);
    },
    enabled: trimmed.length > 0,
    placeholderData: (prev) => prev,
  });
}

// ---------------------------------------------------------------------------
// Single contact
// ---------------------------------------------------------------------------
export function useContact(accountId: string, contactId: number) {
  return useQuery({
    queryKey: ["contact", accountId, contactId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: Contact }>(
        `${base(accountId)}/${contactId}`,
      );
      return res.payload;
    },
    enabled: Number.isFinite(contactId),
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["contacts", accountId] });
  qc.invalidateQueries({ queryKey: ["contact", accountId] });
}

export function useCreateContact(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: ContactInput) => {
      // ``create`` returns ``{payload: {contact, contact_inbox}}``;
      // we only need the contact for routing.
      const res = await apiFetch<{
        payload: { contact: Contact; contact_inbox: unknown };
      }>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      });
      return res.payload.contact;
    },
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateContact(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; patch: ContactInput }) => {
      const res = await apiFetch<{ payload: Contact }>(
        `${base(accountId)}/${input.id}`,
        { method: "PATCH", body: JSON.stringify(input.patch) },
      );
      return res.payload;
    },
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteContact(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

/**
 * ``POST /api/v1/accounts/{id}/actions/contact_merge`` — fold ``mergee``
 * into ``base``. The mergee's conversations + notes + JSONB attrs move
 * over and the mergee row is destroyed. Returns the post-merge ``base``
 * contact (bare, no envelope).
 */
export function useMergeContacts(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { base_contact_id: number; mergee_contact_id: number }) =>
      apiFetch<Contact>(
        `/api/v1/accounts/${accountId}/actions/contact_merge`,
        { method: "POST", body: JSON.stringify(input) },
      ),
    onSuccess: () => invalidate(qc, accountId),
  });
}

/** Drop one or more custom-attribute keys from the contact's blob. */
export function useDestroyContactCustomAttributes(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; keys: string[] }) => {
      const res = await apiFetch<{ payload: Contact }>(
        `${base(accountId)}/${input.id}/destroy_custom_attributes`,
        {
          method: "POST",
          body: JSON.stringify({ custom_attributes: input.keys }),
        },
      );
      return res.payload;
    },
    onSuccess: () => invalidate(qc, accountId),
  });
}

// ---------------------------------------------------------------------------
// Contactable inboxes
// ---------------------------------------------------------------------------
export function useContactableInboxes(accountId: string, contactId: number) {
  return useQuery({
    queryKey: ["contact-inboxes", accountId, contactId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: ContactableInbox[] }>(
        `${base(accountId)}/${contactId}/contactable_inboxes`,
      );
      return res.payload;
    },
    enabled: Number.isFinite(contactId),
  });
}

// ---------------------------------------------------------------------------
// Notes (nested resource)
// ---------------------------------------------------------------------------
export function useContactNotes(accountId: string, contactId: number) {
  return useQuery({
    queryKey: ["contact-notes", accountId, contactId],
    queryFn: () =>
      apiFetch<ContactNote[]>(
        `${base(accountId)}/${contactId}/notes`,
      ),
    enabled: Number.isFinite(contactId),
  });
}

function invalidateNotes(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
  contactId: number,
) {
  qc.invalidateQueries({
    queryKey: ["contact-notes", accountId, contactId],
  });
}

export function useCreateContactNote(accountId: string, contactId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: string) =>
      apiFetch<ContactNote>(
        `${base(accountId)}/${contactId}/notes`,
        {
          method: "POST",
          body: JSON.stringify({ note: { content } }),
        },
      ),
    onSuccess: () => invalidateNotes(qc, accountId, contactId),
  });
}

export function useUpdateContactNote(accountId: string, contactId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; content: string }) =>
      apiFetch<ContactNote>(
        `${base(accountId)}/${contactId}/notes/${input.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ note: { content: input.content } }),
        },
      ),
    onSuccess: () => invalidateNotes(qc, accountId, contactId),
  });
}

export function useDeleteContactNote(accountId: string, contactId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(
        `${base(accountId)}/${contactId}/notes/${id}`,
        { method: "DELETE" },
      ),
    onSuccess: () => invalidateNotes(qc, accountId, contactId),
  });
}
