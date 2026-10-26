import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type AppointmentStatus =
  | "scheduled"
  | "confirmed"
  | "cancelled"
  | "done";

export type AppointmentContact = {
  id: number;
  name: string | null;
  email: string | null;
  phone_number: string | null;
};

export type AppointmentProduct = {
  id: number;
  name: string;
  price: number | null;
  currency: string | null;
};

export type Appointment = {
  id: number;
  account_id: number;
  contact_id: number;
  product_id: number | null;
  title: string;
  description: string | null;
  starts_at: string;
  ends_at: string | null;
  status: AppointmentStatus;
  notes: string | null;
  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
  contact: AppointmentContact | null;
  product: AppointmentProduct | null;
};

export type AppointmentCreateInput = {
  contact_id: number;
  product_id?: number | null;
  title: string;
  description?: string | null;
  starts_at: string;
  ends_at?: string | null;
  status?: AppointmentStatus;
  notes?: string | null;
};

export type AppointmentPatchInput = {
  contact_id?: number;
  product_id?: number | null;
  title?: string;
  description?: string | null;
  starts_at?: string;
  ends_at?: string | null;
  status?: AppointmentStatus;
  notes?: string | null;
};

export type AppointmentFilters = {
  from?: string;
  to?: string;
  contact_id?: number;
  status?: AppointmentStatus;
  page?: number;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/appointments`;
}

export function useAppointments(
  accountId: string,
  filters: AppointmentFilters = {},
) {
  const { from, to, contact_id, status, page } = filters;
  return useQuery({
    queryKey: [
      "appointments",
      accountId,
      from ?? null,
      to ?? null,
      contact_id ?? null,
      status ?? null,
      page ?? null,
    ],
    queryFn: () => {
      const sp = new URLSearchParams();
      if (from) sp.set("from", from);
      if (to) sp.set("to", to);
      if (contact_id !== undefined) sp.set("contact_id", String(contact_id));
      if (status) sp.set("status", status);
      if (page) sp.set("page", String(page));
      const qs = sp.toString();
      return apiFetch<Appointment[]>(
        `${base(accountId)}${qs ? `?${qs}` : ""}`,
      );
    },
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["appointments", accountId] });
}

export function useCreateAppointment(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: AppointmentCreateInput) =>
      apiFetch<Appointment>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateAppointment(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: AppointmentPatchInput }) =>
      apiFetch<Appointment>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteAppointment(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
