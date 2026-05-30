import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export const IG_CHANNEL_TYPE = "Channel::Instagram";

export type Inbox = {
  id: number;
  channel_id: number;
  name: string;
  channel_type: string;
};

export type ChannelSettings = {
  channel_instagram_id: number;
  login_type: "facebook" | "instagram";
  connect_method: string;
  page_id: string | null;
  can_delete_media: boolean;
};

// ---------------------------------------------------------------------------
// Inboxes (filtered to Instagram)
// ---------------------------------------------------------------------------
export function useInstagramInboxes(accountId: string) {
  return useQuery({
    queryKey: ["instagram-inboxes", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: Inbox[] }>(
        `/api/v1/accounts/${accountId}/inboxes`,
      );
      return res.payload.filter((i) => i.channel_type === IG_CHANNEL_TYPE);
    },
  });
}

export function useChannelSettings(accountId: string, channelId: number) {
  return useQuery({
    queryKey: ["ig-channel-settings", accountId, channelId],
    queryFn: () =>
      apiFetch<ChannelSettings>(
        `/api/v1/accounts/${accountId}/instagram_channels/${channelId}/settings`,
      ),
    retry: false, // a legacy channel has no settings row (404) — that's fine
  });
}

// ---------------------------------------------------------------------------
// Connection
// ---------------------------------------------------------------------------
/** Fetch the OAuth dialog URL then redirect the browser to Meta. */
export async function startOAuth(
  accountId: string,
  flow: "facebook" | "instagram",
): Promise<void> {
  const path =
    flow === "instagram" ? "connect/start_instagram" : "connect/start";
  const { authorize_url } = await apiFetch<{ authorize_url: string }>(
    `/api/v1/accounts/${accountId}/instagram_channels/${path}`,
  );
  window.location.href = authorize_url;
}

export type ManualConnectInput = {
  name: string;
  instagram_id: string;
  access_token: string;
  login_type: "facebook" | "instagram";
};

export function useConnectManual(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ManualConnectInput) =>
      apiFetch<{ inbox_id: number; channel_instagram_id: number }>(
        `/api/v1/accounts/${accountId}/instagram_channels/connect_manual`,
        { method: "POST", body: JSON.stringify(input) },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["instagram-inboxes", accountId] });
    },
  });
}
