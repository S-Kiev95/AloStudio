import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

// `labels.ts` is the canonical source for the Label type + hook
// (full CRUD + envelope-unwrapping); re-exported here so existing
// `from "./account"` imports keep working.
export { useLabels } from "./labels";
export type { Label } from "./labels";

export type Agent = {
  id: number;
  name: string;
  available_name?: string;
  email?: string;
  /** Backend emits an int: 0 = agent, 1 = administrator. */
  role?: number;
  account_id?: number;
  availability_status?: "online" | "offline" | "busy";
  auto_offline?: boolean;
  confirmed?: boolean;
  thumbnail?: string;
};

/** Role enum on the wire (``AccountUser.role`` int). */
export const ROLE_AGENT = 0;
export const ROLE_ADMINISTRATOR = 1;

export function useAgents(accountId: string) {
  return useQuery({
    queryKey: ["agents", accountId],
    queryFn: () => apiFetch<Agent[]>(`/api/v1/accounts/${accountId}/agents`),
    staleTime: 5 * 60_000,
  });
}
