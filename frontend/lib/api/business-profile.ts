import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Ajustes → Sobre el negocio: what every AI of the account reads about the
 *  business (the voice agent, the decisions model, the chat agent). */
export type BusinessProfile = { text: string; max: number };

function key(accountId: string) {
  return ["business-profile", accountId] as const;
}

function url(accountId: string) {
  return `/api/v1/accounts/${accountId}/business_profile`;
}

export function useBusinessProfile(accountId: string) {
  return useQuery({
    queryKey: key(accountId),
    queryFn: () => apiFetch<BusinessProfile>(url(accountId)),
  });
}

export function useSaveBusinessProfile(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (text: string) =>
      apiFetch<BusinessProfile>(url(accountId), {
        method: "PUT",
        body: JSON.stringify({ text }),
      }),
    onSuccess: (data) => qc.setQueryData(key(accountId), data),
  });
}
