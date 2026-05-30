import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type AttributeModel = "conversation_attribute" | "contact_attribute";

export type AttributeDisplayType =
  | "text"
  | "number"
  | "currency"
  | "percent"
  | "link"
  | "date"
  | "list"
  | "checkbox";

export const ATTRIBUTE_DISPLAY_TYPES: {
  value: AttributeDisplayType;
  label: string;
}[] = [
  { value: "text", label: "Texto" },
  { value: "number", label: "Número" },
  { value: "currency", label: "Moneda" },
  { value: "percent", label: "Porcentaje" },
  { value: "link", label: "Enlace" },
  { value: "date", label: "Fecha" },
  { value: "list", label: "Lista" },
  { value: "checkbox", label: "Casilla" },
];

export type CustomAttribute = {
  id: number;
  attribute_display_name: string;
  attribute_display_type: AttributeDisplayType;
  attribute_description: string | null;
  attribute_key: string;
  regex_pattern: string | null;
  regex_cue: string | null;
  attribute_values: string[];
  attribute_model: AttributeModel;
  default_value: unknown;
  created_at: string | null;
  updated_at: string | null;
};

export type CustomAttributeInput = {
  attribute_display_name: string;
  attribute_display_type: AttributeDisplayType;
  attribute_description?: string | null;
  attribute_key?: string;
  attribute_model: AttributeModel;
  regex_pattern?: string | null;
  regex_cue?: string | null;
  attribute_values?: string[];
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/custom_attribute_definitions`;
}

export function useCustomAttributes(
  accountId: string,
  model?: AttributeModel,
) {
  return useQuery({
    queryKey: ["custom-attributes", accountId, model ?? null],
    queryFn: () => {
      const qs = model ? `?attribute_model=${encodeURIComponent(model)}` : "";
      return apiFetch<CustomAttribute[]>(`${base(accountId)}${qs}`);
    },
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["custom-attributes", accountId] });
}

export function useCreateCustomAttribute(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CustomAttributeInput) =>
      apiFetch<CustomAttribute>(base(accountId), {
        method: "POST",
        body: JSON.stringify({ custom_attribute_definition: input }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateCustomAttribute(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: CustomAttributeInput }) =>
      apiFetch<CustomAttribute>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify({ custom_attribute_definition: input.patch }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteCustomAttribute(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
