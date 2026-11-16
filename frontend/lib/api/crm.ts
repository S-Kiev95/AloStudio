import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Sales pipeline (F11): pipelines, their stages and opportunities. */
export type StageKind = "open" | "won" | "lost";

export type Stage = {
  id: number;
  /** Seeded stages: ``new`` … ``lost``, named by the dictionary. */
  code: string | null;
  /** Set when someone names the stage; wins over ``code``. */
  name: string | null;
  kind: StageKind;
  probability: number;
  position: number;
};

export type Pipeline = {
  id: number;
  /** Null on the default pipeline: named by the dictionary. */
  name: string | null;
  is_default: boolean;
  rotten_days: number;
  stages: Stage[];
};

export type Opportunity = {
  id: number;
  pipeline_id: number;
  stage_id: number;
  title: string;
  description: string | null;
  value: number | null;
  currency: string | null;
  contact_id: number | null;
  product_id: number | null;
  owner_id: number | null;
  conversation_id: number | null;
  /** ``YYYY-MM-DD`` */
  expected_close_on: string | null;
  closed_at: number | null;
  lost_reason: string | null;
  position: number;
  stage_changed_at: number | null;
  created_at: number | null;
  updated_at: number | null;
  contact: { id: number; name: string | null; avatar_url: string | null } | null;
  product: { id: number; name: string } | null;
  owner: { id: number; name: string } | null;
};

export type OpportunityInput = {
  title?: string;
  description?: string | null;
  value?: number | null;
  currency?: string | null;
  stage_id?: number;
  contact_id?: number | null;
  product_id?: number | null;
  owner_id?: number | null;
  conversation_id?: number | null;
  expected_close_on?: string | null;
  lost_reason?: string | null;
  position?: number;
};

export type StageInput = {
  id?: number;
  name?: string | null;
  kind: StageKind;
  probability: number;
};

export type OpportunityFilters = {
  company_id?: number;
  pipeline_id?: number;
  contact_id?: number;
  owner_id?: number;
  status?: StageKind;
  q?: string;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/crm`;
}

export function usePipelines(accountId: string) {
  return useQuery({
    queryKey: ["crm-pipelines", accountId],
    queryFn: () => apiFetch<Pipeline[]>(`${base(accountId)}/pipelines`),
  });
}

export function useOpportunities(accountId: string, filters: OpportunityFilters = {}) {
  return useQuery({
    queryKey: ["crm-opportunities", accountId, filters],
    queryFn: () => {
      const sp = new URLSearchParams();
      for (const [k, v] of Object.entries(filters)) {
        if (v !== undefined && v !== "") sp.set(k, String(v));
      }
      const qs = sp.toString();
      return apiFetch<Opportunity[]>(`${base(accountId)}/opportunities${qs ? `?${qs}` : ""}`);
    },
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>, accountId: string) {
  qc.invalidateQueries({ queryKey: ["crm-opportunities", accountId] });
}

export function useCreateOpportunity(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: OpportunityInput) =>
      apiFetch<Opportunity>(`${base(accountId)}/opportunities`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateOpportunity(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: OpportunityInput }) =>
      apiFetch<Opportunity>(`${base(accountId)}/opportunities/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteOpportunity(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/opportunities/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdatePipeline(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      id: number;
      patch: { name?: string | null; rotten_days?: number; stages?: StageInput[] };
    }) =>
      apiFetch<Pipeline>(`${base(accountId)}/pipelines/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crm-pipelines", accountId] }),
  });
}

/** Whole days since the opportunity last moved — the "stale" flag compares
 *  it with the pipeline's ``rotten_days``. */
export function daysIdle(o: Opportunity, now: number = Date.now()): number {
  const since = o.stage_changed_at ?? o.updated_at ?? o.created_at;
  if (!since) return 0;
  return Math.floor((now / 1000 - since) / 86_400);
}

// ---------------------------------------------------------------------------
// Activities and tasks
// ---------------------------------------------------------------------------
export type ActivityKind = "task" | "call" | "meeting" | "email";
export type ActivityStatus = "pending" | "overdue" | "done";

export type Activity = {
  id: number;
  kind: ActivityKind;
  title: string;
  description: string | null;
  /** unix seconds */
  due_at: number | null;
  done_at: number | null;
  owner_id: number | null;
  contact_id: number | null;
  opportunity_id: number | null;
  created_at: number | null;
  contact: { id: number; name: string | null; avatar_url: string | null } | null;
  opportunity: { id: number; title: string } | null;
  owner: { id: number; name: string } | null;
};

export type ActivityInput = {
  kind?: ActivityKind;
  title?: string;
  description?: string | null;
  /** ISO 8601 */
  due_at?: string | null;
  owner_id?: number | null;
  contact_id?: number | null;
  opportunity_id?: number | null;
  done?: boolean;
};

export type ActivityFilters = {
  owner_id?: number;
  contact_id?: number;
  opportunity_id?: number;
  status?: ActivityStatus;
};

export function useActivities(accountId: string, filters: ActivityFilters = {}) {
  return useQuery({
    queryKey: ["crm-activities", accountId, filters],
    queryFn: () => {
      const sp = new URLSearchParams();
      for (const [k, v] of Object.entries(filters)) {
        if (v !== undefined) sp.set(k, String(v));
      }
      const qs = sp.toString();
      return apiFetch<Activity[]>(`${base(accountId)}/activities${qs ? `?${qs}` : ""}`);
    },
  });
}

function invalidateActivities(qc: ReturnType<typeof useQueryClient>, accountId: string) {
  qc.invalidateQueries({ queryKey: ["crm-activities", accountId] });
}

export function useCreateActivity(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ActivityInput) =>
      apiFetch<Activity>(`${base(accountId)}/activities`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidateActivities(qc, accountId),
  });
}

export function useUpdateActivity(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: ActivityInput }) =>
      apiFetch<Activity>(`${base(accountId)}/activities/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidateActivities(qc, accountId),
  });
}

export function useDeleteActivity(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/activities/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidateActivities(qc, accountId),
  });
}

// ---------------------------------------------------------------------------
// Companies
// ---------------------------------------------------------------------------
export type Company = {
  id: number;
  name: string;
  website: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  tax_id: string | null;
  notes: string | null;
  contacts_count: number;
  created_at: number | null;
};

export type CompanyContact = {
  id: number;
  name: string | null;
  email: string | null;
  phone_number: string | null;
  avatar_url: string | null;
};

export type CompanyDetail = Company & { contacts: CompanyContact[] };

export type CompanyInput = {
  name?: string;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  tax_id?: string | null;
  notes?: string | null;
};

export function useCompanies(accountId: string, filters: { q?: string; contact_id?: number } = {}) {
  return useQuery({
    queryKey: ["crm-companies", accountId, filters],
    queryFn: () => {
      const sp = new URLSearchParams();
      if (filters.q?.trim()) sp.set("q", filters.q.trim());
      if (filters.contact_id !== undefined) sp.set("contact_id", String(filters.contact_id));
      const qs = sp.toString();
      return apiFetch<Company[]>(`${base(accountId)}/companies${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useCompany(accountId: string, companyId: number) {
  return useQuery({
    queryKey: ["crm-companies", accountId, "detail", companyId],
    queryFn: () => apiFetch<CompanyDetail>(`${base(accountId)}/companies/${companyId}`),
  });
}

function invalidateCompanies(qc: ReturnType<typeof useQueryClient>, accountId: string) {
  qc.invalidateQueries({ queryKey: ["crm-companies", accountId] });
  // A company's opportunities follow its people.
  qc.invalidateQueries({ queryKey: ["crm-opportunities", accountId] });
}

export function useSaveCompany(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id?: number; data: CompanyInput }) =>
      apiFetch<Company>(
        input.id ? `${base(accountId)}/companies/${input.id}` : `${base(accountId)}/companies`,
        { method: input.id ? "PATCH" : "POST", body: JSON.stringify(input.data) },
      ),
    onSuccess: () => invalidateCompanies(qc, accountId),
  });
}

export function useDeleteCompany(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/companies/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateCompanies(qc, accountId),
  });
}

/** Put a contact in a company (``companyId``) or take it out of ``fromId``. */
export function useSetContactCompany(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { contactId: number; companyId: number | null; fromId?: number | null }) => {
      if (input.companyId !== null) {
        await apiFetch(`${base(accountId)}/companies/${input.companyId}/contacts`, {
          method: "POST",
          body: JSON.stringify({ contact_id: input.contactId }),
        });
      } else if (input.fromId) {
        await apiFetch(`${base(accountId)}/companies/${input.fromId}/contacts/${input.contactId}`, {
          method: "DELETE",
        });
      }
    },
    onSuccess: () => invalidateCompanies(qc, accountId),
  });
}

// ---------------------------------------------------------------------------
// Contact origin: how each person first came (F11)
// ---------------------------------------------------------------------------
/** Set automatically by the first conversation. */
export const AUTO_ORIGIN_SOURCES = ["channel", "ad", "post", "shortlink"] as const;
/** For what the system cannot see; set by hand. */
export const MANUAL_ORIGIN_SOURCES = ["referral", "event", "walk_in", "phone", "website", "other"] as const;
export const ORIGIN_SOURCES = [...AUTO_ORIGIN_SOURCES, ...MANUAL_ORIGIN_SOURCES] as const;
export type OriginSource = (typeof ORIGIN_SOURCES)[number];
export const ORIGIN_CHANNELS = ["whatsapp", "instagram", "facebook", "web", "email", "telegram", "sms", "api"] as const;
export type OriginChannel = (typeof ORIGIN_CHANNELS)[number];

export type ContactOrigin = {
  source: OriginSource;
  channel: OriginChannel | null;
  /** The ad's title, or a note typed by hand. */
  detail: string | null;
  ad_id: string | null;
  conversation_id: number | null;
  at: number | null;
};

export function useSetContactOrigin(accountId: string, contactId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { source: OriginSource | null; channel?: OriginChannel | null; detail?: string | null }) =>
      apiFetch<{ origin: ContactOrigin | null }>(`${base(accountId)}/contacts/${contactId}/origin`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["contact", accountId, contactId] });
      void qc.invalidateQueries({ queryKey: ["contacts", accountId] });
    },
  });
}

// ---------------------------------------------------------------------------
// Meta catalogue: products → Commerce Manager (F11)
// ---------------------------------------------------------------------------
export type MetaCatalogSync = {
  at: number;
  /** False when Meta was still checking the batch after a few seconds. */
  validated: boolean;
  sent: number;
  removed: number;
  skipped: number;
  failed: number;
};

export type MetaCatalog =
  | { connected: false }
  | {
      connected: true;
      catalog_id: string;
      catalog_name: string | null;
      last_sync: MetaCatalogSync | null;
    };

const catalogKey = (accountId: string) => ["meta-catalog", accountId] as const;

export function useMetaCatalog(accountId: string) {
  return useQuery({
    queryKey: catalogKey(accountId),
    queryFn: () => apiFetch<MetaCatalog>(`${base(accountId)}/meta-catalog`),
  });
}

export function useMetaCatalogActions(accountId: string) {
  const qc = useQueryClient();
  const done = (data: MetaCatalog) => {
    qc.setQueryData(catalogKey(accountId), data);
    void qc.invalidateQueries({ queryKey: ["products", accountId] });
  };
  const connect = useMutation({
    mutationFn: (input: { catalog_id: string; access_token?: string }) =>
      apiFetch<MetaCatalog>(`${base(accountId)}/meta-catalog`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: done,
  });
  const disconnect = useMutation({
    mutationFn: () => apiFetch<MetaCatalog>(`${base(accountId)}/meta-catalog`, { method: "DELETE" }),
    onSuccess: done,
  });
  const sync = useMutation({
    mutationFn: () =>
      apiFetch<MetaCatalog & { result: Omit<MetaCatalogSync, "at" | "validated"> }>(
        `${base(accountId)}/meta-catalog/sync`,
        { method: "POST" },
      ),
    onSuccess: done,
  });
  return { connect, disconnect, sync };
}
