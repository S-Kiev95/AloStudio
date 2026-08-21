import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type ConfigKind = "text" | "password" | "boolean";

export type InstallationConfig = {
  name: string;
  title: string;
  description: string;
  group: string;
  kind: ConfigKind;
  secret: boolean;
  /** Masked for secrets — never the value in the clear. */
  value: string | boolean;
  configured: boolean;
  /** Where the effective value came from. */
  source: "database" | "environment";
  editable: boolean;
};

const KEY = ["installation-configs"];

export function useInstallationConfigs() {
  return useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const res = await apiFetch<{ payload: InstallationConfig[] }>(
        "/api/v1/installation/configs",
      );
      return res.payload;
    },
    // 401 here means "not the operator", which retrying won't fix.
    retry: false,
  });
}

export function useSetInstallationConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, value }: { name: string; value: string | boolean }) =>
      apiFetch<InstallationConfig>(
        `/api/v1/installation/configs/${encodeURIComponent(name)}`,
        { method: "PUT", body: JSON.stringify({ value }) },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useClearInstallationConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch<InstallationConfig>(
        `/api/v1/installation/configs/${encodeURIComponent(name)}`,
        { method: "DELETE" },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

/** Preserve the backend's group order rather than sorting alphabetically —
 *  the registry lists them in the order an operator fills them in. */
export function groupConfigs(
  configs: InstallationConfig[],
): { group: string; items: InstallationConfig[] }[] {
  const out: { group: string; items: InstallationConfig[] }[] = [];
  for (const config of configs) {
    const existing = out.find((g) => g.group === config.group);
    if (existing) existing.items.push(config);
    else out.push({ group: config.group, items: [config] });
  }
  return out;
}
