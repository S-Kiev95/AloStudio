import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Short channel-type tags accepted by `POST /inboxes` (Chatwoot parity). */
export type ChannelType =
  | "telegram"
  | "whatsapp"
  | "sms"
  | "twilio_sms"
  | "email"
  | "web_widget"
  | "api"
  | "facebook"
  | "instagram";

/** Inbox row — list view (any channel). */
export type Inbox = {
  id: number;
  channel_id: number;
  name: string;
  channel_type: string; // Ruby class name, e.g. "Channel::Telegram"
};

/** Full inbox detail (create / show response). Channel-specific keys vary. */
export type InboxDetail = Inbox & {
  greeting_enabled?: boolean;
  greeting_message?: string | null;
  enable_auto_assignment?: boolean;
  csat_survey_enabled?: boolean;
  phone_number?: string | null;
  provider?: string | null;
  webhook_url?: string | null;
  inbox_identifier?: string | null;
  hmac_token?: string | null;
  callback_webhook_url?: string | null;
  webhook_verify_token?: string | null;
  /** Channel::Email only — what every reply from this mailbox signs with. */
  email?: string | null;
  signature?: string;
  logo_url?: string;
  template_html?: string;
  /** Null when the HTML was written or edited by hand. */
  template_design?: Record<string, unknown> | null;
  /** Channel::Email transport, admin-only. Passwords are never returned;
   *  `*_password_set` says whether one is stored. */
  imap_enabled?: boolean;
  imap_address?: string;
  imap_port?: number;
  imap_login?: string;
  imap_enable_ssl?: boolean;
  imap_password_set?: boolean;
  smtp_enabled?: boolean;
  smtp_address?: string;
  smtp_port?: number;
  smtp_login?: string;
  smtp_enable_ssl_tls?: boolean;
  smtp_enable_starttls_auto?: boolean;
  smtp_password_set?: boolean;
};

/** The `channel:` sub-hash: a `type` plus whatever fields that channel needs. */
export type ChannelPayload = { type: ChannelType } & Record<string, unknown>;

export type InboxCreateInput = {
  name: string;
  channel: ChannelPayload;
  enable_auto_assignment?: boolean;
  greeting_enabled?: boolean;
  greeting_message?: string;
};

export type InboxUpdateInput = {
  name?: string;
  greeting_enabled?: boolean;
  greeting_message?: string;
  enable_auto_assignment?: boolean;
  csat_survey_enabled?: boolean;
  /** The `channel:` sub-hash. What it may carry is allow-listed per
   *  channel type server-side, so anything else is dropped rather than
   *  written. */
  channel?: Record<string, unknown>;
};

/** One agent in an `inbox_members` payload (the subset we render). */
export type InboxAgent = {
  id: number;
  name: string;
  email: string;
  availability_status?: string;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/inboxes`;
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["inboxes", accountId] });
}

/** All inboxes for the account (any channel type). Response is `{payload}`. */
export function useInboxes(accountId: string) {
  return useQuery({
    queryKey: ["inboxes", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: Inbox[] }>(base(accountId));
      return res.payload;
    },
    staleTime: 60_000,
  });
}

export function useInbox(accountId: string, id: number) {
  return useQuery({
    queryKey: ["inboxes", accountId, id],
    queryFn: () => apiFetch<InboxDetail>(`${base(accountId)}/${id}`),
    enabled: Number.isFinite(id),
  });
}

export function useCreateInbox(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: InboxCreateInput) =>
      apiFetch<InboxDetail>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateInbox(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: InboxUpdateInput }) =>
      apiFetch<InboxDetail>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

/** One side's outcome. `configured` false means that side is switched off. */
export type ProbeSide = {
  configured: boolean;
  ok: boolean;
  error: string | null;
};

/** Try the mailbox's credentials for real.
 *
 *  Saving them proved nothing: a typo left the mailbox looking configured
 *  and silently delivering nothing, and the first sign was mail not
 *  arriving days later with no error to explain it. */
export function useTestEmailConnection(accountId: string) {
  return useMutation({
    mutationFn: (inboxId: number) =>
      apiFetch<{ imap: ProbeSide; smtp: ProbeSide }>(
        `${base(accountId)}/${inboxId}/test_email_connection`,
        { method: "POST" },
      ),
  });
}

export function useDeleteInbox(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<{ message: string }>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

// --- inbox members --------------------------------------------------------
// Chatwoot declares inbox_members as a top-level account resource; only the
// `show` verb carries inbox_id in the path, the others read it from the body.
function membersBase(accountId: string): string {
  return `/api/v1/accounts/${accountId}/inbox_members`;
}

export function useInboxMembers(accountId: string, inboxId: number) {
  return useQuery({
    queryKey: ["inbox-members", accountId, inboxId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: InboxAgent[] }>(
        `${membersBase(accountId)}/${inboxId}`,
      );
      return res.payload;
    },
    enabled: Number.isFinite(inboxId),
  });
}

export function useSetInboxMembers(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { inboxId: number; userIds: number[] }) =>
      apiFetch<{ payload: InboxAgent[] }>(membersBase(accountId), {
        method: "PATCH",
        body: JSON.stringify({
          inbox_id: input.inboxId,
          user_ids: input.userIds,
        }),
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({
        queryKey: ["inbox-members", accountId, vars.inboxId],
      });
    },
  });
}

/** Map the Ruby `channel_type` class name to a short, human label. */
export function channelLabel(channelType: string): string {
  const map: Record<string, string> = {
    "Channel::Telegram": "Telegram",
    "Channel::Whatsapp": "WhatsApp",
    "Channel::Sms": "SMS",
    "Channel::TwilioSms": "Twilio",
    "Channel::Email": "Email",
    "Channel::WebWidget": "Web widget",
    "Channel::Api": "API",
    "Channel::FacebookPage": "Facebook",
    "Channel::Instagram": "Instagram",
  };
  return map[channelType] ?? channelType.replace("Channel::", "");
}
