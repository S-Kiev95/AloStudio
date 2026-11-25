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

export type PaymentTerms = "cash" | "credit" | "installments";
export type PaymentMethod = "cash" | "transfer" | "card" | "other";
export type InstallmentStatus = "paid" | "partial" | "pending" | "overdue";

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
  payment_terms?: PaymentTerms | null;
  due_on?: string | null;
  paid_amount?: number;
  owed_amount?: number;
  overdue_amount?: number;
  days_overdue?: number;
  installments_count?: number;
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
  release_allocations?: boolean;
  keep_allocations?: boolean;
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
  qc.invalidateQueries({ queryKey: ["crm-billing", accountId] });
  qc.invalidateQueries({ queryKey: ["crm-statement", accountId] });
  qc.invalidateQueries({ queryKey: ["crm-receivables", accountId] });
  qc.invalidateQueries({ queryKey: ["crm-payments", accountId] });
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
    mutationFn: (input: number | { id: number; releaseAllocations?: boolean }) => {
      const id = typeof input === "number" ? input : input.id;
      const release = typeof input === "number" ? false : Boolean(input.releaseAllocations);
      const qs = release ? "?release_allocations=true" : "";
      return apiFetch<Record<string, never>>(`${base(accountId)}/opportunities/${id}${qs}`, {
        method: "DELETE",
      });
    },
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

/** `can_login`: this installation can connect by logging in with Facebook. */
export type MetaCatalog =
  | { connected: false; can_login?: boolean }
  | {
      connected: true;
      can_login?: boolean;
      /** Connected by logging in with Facebook (as a person, or as the
       *  business with a system-user token that doesn't expire); when that
       *  access expires. */
      login?: { via: "facebook" | "facebook_business"; expires_at: number | null } | null;
      catalog_id: string;
      catalog_name: string | null;
      last_sync: MetaCatalogSync | null;
      /** Why the last background sync failed (token, permission…). */
      last_error?: { code: string; at: number } | null;
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

/** Sends the browser to Facebook to connect the catalogue; it comes back
 *  to CRM → Productos with `catalog`, `catalog_pick` or `catalog_error`. */
export async function startMetaCatalogLogin(accountId: string): Promise<void> {
  const { authorize_url } = await apiFetch<{ authorize_url: string }>(
    `${base(accountId)}/meta-catalog/connect/start`,
  );
  window.location.href = authorize_url;
}

export type PendingMetaCatalog = { id: string; name: string | null; business: string | null };

export function usePendingMetaCatalogs(accountId: string, nonce: string | null) {
  return useQuery({
    queryKey: ["meta-catalog-pending", accountId, nonce],
    enabled: Boolean(nonce),
    retry: false,
    queryFn: () =>
      apiFetch<PendingMetaCatalog[]>(`${base(accountId)}/meta-catalog/pending/${nonce}`),
  });
}

export function useConnectPendingMetaCatalog(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ nonce, catalogId }: { nonce: string; catalogId: string }) =>
      apiFetch<MetaCatalog>(`${base(accountId)}/meta-catalog/pending/${nonce}/${catalogId}`, {
        method: "POST",
      }),
    onSuccess: (data) => {
      qc.setQueryData(catalogKey(accountId), data);
      void qc.invalidateQueries({ queryKey: ["products", accountId] });
    },
  });
}

// ---------------------------------------------------------------------------
// Collections (cobranzas): billing, installments, payments & receivables
// ---------------------------------------------------------------------------
export type Installment = {
  id: number;
  number: number;
  due_on: string;
  amount: number;
  paid_amount: number;
  remaining_amount: number;
  days_overdue: number;
  status: InstallmentStatus;
  locked: boolean;
};

export type OpportunityAllocation = {
  id: number;
  payment_id: number;
  opportunity_id: number;
  installment_id: number | null;
  installment_number: number | null;
  amount: number;
  paid_on: string | null;
  method: PaymentMethod | null;
  note: string | null;
  payment_amount: number | null;
  created_by: { id: number; name: string } | null;
};

export type OpportunityBilling = {
  opportunity_id: number;
  is_won: boolean;
  payment_terms: PaymentTerms | null;
  due_on: string | null;
  value: number | null;
  currency: string | null;
  paid_amount: number;
  owed_amount: number;
  overdue_amount: number;
  days_overdue: number;
  next_due_on: string | null;
  installments: Installment[];
  allocations: OpportunityAllocation[];
  created_payment?: Payment | null;
};

export type OpportunityBillingInput = {
  payment_terms: PaymentTerms | null;
  due_on?: string | null;
  generate?: {
    count: number;
    first_due_on: string;
    frequency: "monthly" | "every_n_days";
    interval_days?: number | null;
  } | null;
  installments?: { id?: number | null; due_on: string; amount: number }[] | null;
  register_payment?: boolean;
  payment_method?: PaymentMethod;
  paid_on?: string | null;
  payment_note?: string | null;
};

export type PaymentAllocationItem = {
  id: number;
  opportunity_id: number;
  opportunity_title: string | null;
  installment_id: number | null;
  installment_number: number | null;
  amount: number;
};

export type Payment = {
  id: number;
  contact_id: number;
  amount: number;
  currency: string | null;
  paid_on: string;
  method: PaymentMethod;
  note: string | null;
  allocated_amount: number;
  unallocated_amount: number;
  created_by_id: number | null;
  created_by: { id: number; name: string } | null;
  contact: { id: number; name: string | null; avatar_url: string | null } | null;
  created_at: number | null;
  allocations: PaymentAllocationItem[];
};

export type PaymentInput = {
  contact_id?: number;
  amount?: number;
  currency?: string | null;
  paid_on?: string;
  method?: PaymentMethod;
  note?: string | null;
  allocation_mode?: "auto" | "manual";
  allocations?: { opportunity_id: number; installment_id?: number | null; amount: number }[];
};

export type PaymentPreview = {
  currency: string | null;
  amount: number;
  allocated_total: number;
  unallocated_amount: number;
  allocations: {
    opportunity_id: number;
    opportunity_title: string;
    installment_id: number | null;
    installment_number: number | null;
    due_on: string | null;
    amount: number;
  }[];
  balance_before: { owed_total: number; credit_balance: number; net_balance: number };
  balance_after: { owed_total: number; credit_balance: number; net_balance: number };
};

export type CurrencyBalance = {
  currency: string | null;
  total_sales: number;
  paid_total: number;
  owed_total: number;
  credit_balance: number;
  net_balance: number;
  overdue_total: number;
  days_overdue: number;
  next_due_on: string | null;
};

export type StatementSale = {
  id: number;
  title: string;
  value: number | null;
  currency: string | null;
  closed_at: number | null;
  payment_terms: PaymentTerms | null;
  due_on: string | null;
  paid_amount: number;
  owed_amount: number;
  overdue_amount: number;
  days_overdue: number;
  next_due_on: string | null;
  owner: { id: number; name: string } | null;
  installments: Installment[];
};

export type WhatsappConversationRef = {
  display_id: number;
  inbox_id: number;
};

export type ContactStatement = {
  as_of: string;
  contact: {
    id: number;
    name: string | null;
    email: string | null;
    phone_number: string | null;
    avatar_url: string | null;
  };
  whatsapp_conversation: WhatsappConversationRef | null;
  balances: CurrencyBalance[];
  sales: StatementSale[];
  payments: Payment[];
};

export type ReceivableCurrency = {
  currency: string | null;
  owed_total: number;
  overdue_total: number;
  credit_balance: number;
  net_balance: number;
};

export type ReceivableRow = {
  contact: {
    id: number;
    name: string | null;
    email: string | null;
    phone_number: string | null;
    avatar_url: string | null;
  };
  owner: { id: number; name: string } | null;
  currencies: ReceivableCurrency[];
  days_overdue: number;
  next_due_on: string | null;
  sales_count: number;
  overdue_count: number;
  whatsapp_conversation: WhatsappConversationRef | null;
};

export type ReceivablesResponse = {
  as_of: string;
  items: ReceivableRow[];
  meta: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
};

export type ReceivablesSummary = {
  as_of: string;
  month: string;
  debtors_count: number;
  overdue_debtors_count: number;
  currencies: {
    currency: string | null;
    to_collect: number;
    overdue: number;
    collected_this_month: number;
    credit_balance: number;
  }[];
};

export type ReceivablesFilters = {
  status?: "all" | "overdue" | "upcoming";
  owner_id?: number;
  q?: string;
  sort?: "overdue" | "amount" | "due_on" | "name";
  order?: "asc" | "desc";
  page?: number;
  per_page?: number;
};

export function useOpportunityBilling(
  accountId: string,
  opportunityId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: ["crm-billing", accountId, opportunityId],
    enabled: enabled && opportunityId !== null,
    queryFn: () =>
      apiFetch<OpportunityBilling>(`${base(accountId)}/opportunities/${opportunityId}/billing`),
  });
}

export function useSaveOpportunityBilling(accountId: string, opportunityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: OpportunityBillingInput) =>
      apiFetch<OpportunityBilling>(`${base(accountId)}/opportunities/${opportunityId}/billing`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useCreatePayment(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PaymentInput) =>
      apiFetch<Payment>(`${base(accountId)}/payments`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdatePayment(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: PaymentInput }) =>
      apiFetch<Payment>(`${base(accountId)}/payments/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeletePayment(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/payments/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function usePreviewPayment(accountId: string) {
  return useMutation({
    mutationFn: (input: {
      contact_id: number;
      amount: number;
      currency: string | null;
      allocation_mode: "auto" | "manual";
      allocations?: { opportunity_id: number; installment_id?: number | null; amount: number }[];
      exclude_payment_id?: number | null;
    }) =>
      apiFetch<PaymentPreview>(`${base(accountId)}/payments/preview`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
  });
}

export function useContactStatement(
  accountId: string,
  contactId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: ["crm-statement", accountId, contactId],
    enabled: enabled && contactId !== null,
    queryFn: () =>
      apiFetch<ContactStatement>(`${base(accountId)}/contacts/${contactId}/statement`),
  });
}

export function useReceivables(accountId: string, filters: ReceivablesFilters = {}) {
  return useQuery({
    queryKey: ["crm-receivables", accountId, "list", filters],
    queryFn: () => {
      const sp = new URLSearchParams();
      for (const [k, v] of Object.entries(filters)) {
        if (v !== undefined && v !== "" && v !== "all") sp.set(k, String(v));
      }
      const qs = sp.toString();
      return apiFetch<ReceivablesResponse>(`${base(accountId)}/receivables${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useReceivablesSummary(accountId: string) {
  return useQuery({
    queryKey: ["crm-receivables", accountId, "summary"],
    queryFn: () => apiFetch<ReceivablesSummary>(`${base(accountId)}/receivables/summary`),
  });
}
