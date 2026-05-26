import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** One row of the per-inbox 7-day schedule. */
export type WorkingHour = {
  id: number;
  inbox_id: number;
  account_id: number;
  day_of_week: number; // 0 = Sunday … 6 = Saturday (Rails convention)
  closed_all_day: boolean;
  open_all_day: boolean;
  open_hour: number | null;
  open_minutes: number | null;
  close_hour: number | null;
  close_minutes: number | null;
};

/** Body shape for the bulk update endpoint — the inbox key is on the path. */
export type WorkingHourInput = {
  day_of_week: number;
  closed_all_day: boolean;
  open_all_day: boolean;
  open_hour: number | null;
  open_minutes: number | null;
  close_hour: number | null;
  close_minutes: number | null;
};

function base(accountId: string, inboxId: number): string {
  return `/api/v1/accounts/${accountId}/inboxes/${inboxId}/working_hours`;
}

export function useInboxWorkingHours(accountId: string, inboxId: number) {
  return useQuery({
    queryKey: ["working-hours", accountId, inboxId],
    queryFn: () => apiFetch<WorkingHour[]>(base(accountId, inboxId)),
    enabled: Number.isFinite(inboxId) && inboxId > 0,
  });
}

/** PATCH /inboxes/:id/working_hours — body {working_hours: WorkingHourInput[]}. */
export function useBulkUpdateWorkingHours(accountId: string, inboxId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (schedule: WorkingHourInput[]) =>
      apiFetch<WorkingHour[]>(base(accountId, inboxId), {
        method: "PATCH",
        body: JSON.stringify({ working_hours: schedule }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["working-hours", accountId, inboxId] });
    },
  });
}
