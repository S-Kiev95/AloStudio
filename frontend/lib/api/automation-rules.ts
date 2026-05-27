import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";
import { MACRO_ACTIONS } from "./macros";

/** Events the backend's AutomationRuleListener fires on. */
export const AUTOMATION_EVENTS = [
  "conversation_created",
  "conversation_updated",
  "conversation_opened",
  "conversation_resolved",
  "message_created",
] as const;
export type AutomationEvent = (typeof AUTOMATION_EVENTS)[number];

export const AUTOMATION_EVENT_LABELS: Record<AutomationEvent, string> = {
  conversation_created: "Conversación creada",
  conversation_updated: "Conversación actualizada",
  conversation_opened: "Conversación abierta",
  conversation_resolved: "Conversación resuelta",
  message_created: "Mensaje creado",
};

/** Macro action set + automation-only extras (mirrors backend allow-list). */
export const AUTOMATION_ACTIONS = [
  ...MACRO_ACTIONS,
  "send_email_to_team",
  "open_conversation",
  "pending_conversation",
] as const;
export type AutomationActionName = (typeof AUTOMATION_ACTIONS)[number];

/** Filter operators supported by the condition evaluator. */
export const FILTER_OPERATORS = [
  "equal_to",
  "not_equal_to",
  "contains",
  "does_not_contain",
  "starts_with",
  "is_present",
  "is_not_present",
  "is_greater_than",
  "is_less_than",
] as const;
export type FilterOperator = (typeof FILTER_OPERATORS)[number];

export const FILTER_OPERATOR_LABELS: Record<FilterOperator, string> = {
  equal_to: "es igual a",
  not_equal_to: "no es igual a",
  contains: "contiene",
  does_not_contain: "no contiene",
  starts_with: "empieza con",
  is_present: "está presente",
  is_not_present: "no está presente",
  is_greater_than: "es mayor que",
  is_less_than: "es menor que",
};

/** Operators that don't read ``values``. */
export const OPERATORS_WITHOUT_VALUES: ReadonlySet<FilterOperator> = new Set([
  "is_present",
  "is_not_present",
]);

/** Common standard attributes the UI offers without per-account custom defs. */
export const STANDARD_ATTRIBUTES = [
  { key: "status", label: "Estado" },
  { key: "priority", label: "Prioridad" },
  { key: "assignee_id", label: "ID del agente asignado" },
  { key: "team_id", label: "ID del equipo" },
  { key: "inbox_id", label: "ID de la bandeja" },
  { key: "labels", label: "Etiquetas" },
  { key: "browser_language", label: "Idioma del navegador" },
  { key: "country_code", label: "Código de país" },
  { key: "referer", label: "Referer" },
  { key: "conversation_language", label: "Idioma de conversación" },
  { key: "mail_subject", label: "Asunto del email" },
  { key: "content", label: "Contenido del mensaje" },
  { key: "message_type", label: "Tipo de mensaje" },
  { key: "email", label: "Email del contacto" },
  { key: "phone_number", label: "Teléfono del contacto" },
  { key: "company", label: "Empresa del contacto" },
] as const;

export type RuleCondition = {
  attribute_key: string;
  filter_operator: FilterOperator;
  query_operator: "AND" | "OR" | "";
  values: unknown[];
  custom_attribute_type?: string | null;
};

export type RuleAction = {
  action_name: AutomationActionName;
  action_params: unknown[];
};

export type AutomationRule = {
  id: number;
  account_id: number;
  name: string;
  description: string | null;
  event_name: AutomationEvent;
  conditions: RuleCondition[];
  actions: RuleAction[];
  created_on: number | null;
  active: boolean;
};

export type AutomationRuleInput = {
  name: string;
  description?: string | null;
  event_name: AutomationEvent;
  active?: boolean;
  conditions: RuleCondition[];
  actions: RuleAction[];
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/automation_rules`;
}

export function useAutomationRules(accountId: string) {
  return useQuery({
    queryKey: ["automation-rules", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: AutomationRule[] }>(
        base(accountId),
      );
      return res.payload;
    },
  });
}

export function useAutomationRule(accountId: string, ruleId: number) {
  return useQuery({
    queryKey: ["automation-rule", accountId, ruleId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: AutomationRule }>(
        `${base(accountId)}/${ruleId}`,
      );
      return res.payload;
    },
    enabled: Number.isFinite(ruleId),
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["automation-rules", accountId] });
  qc.invalidateQueries({ queryKey: ["automation-rule", accountId] });
}

/** POST returns the bare object (no envelope) per Chatwoot's create.jbuilder. */
export function useCreateAutomationRule(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: AutomationRuleInput) =>
      apiFetch<AutomationRule>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateAutomationRule(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      id: number;
      patch: Partial<AutomationRuleInput>;
    }) => {
      const res = await apiFetch<{ payload: AutomationRule }>(
        `${base(accountId)}/${input.id}`,
        {
          method: "PATCH",
          body: JSON.stringify(input.patch),
        },
      );
      return res.payload;
    },
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteAutomationRule(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useCloneAutomationRule(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await apiFetch<{ payload: AutomationRule }>(
        `${base(accountId)}/${id}/clone`,
        { method: "POST" },
      );
      return res.payload;
    },
    onSuccess: () => invalidate(qc, accountId),
  });
}
