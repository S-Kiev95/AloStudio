import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "./errors";
import { apiFetch } from "./fetcher";

/** The WhatsApp number's state, business profile and QR codes on Meta
 *  (`/inboxes/{id}/whatsapp/...`, WhatsApp Cloud inboxes only). */

export type WhatsappPhoneStatus = {
  phone_number: string | null;
  display_phone_number: string | null;
  verified_name: string | null;
  name_status: string | null;
  quality_rating: string | null;
  messaging_limit: string | null;
  status: string | null;
  code_verification_status: string | null;
  throughput: string | null;
  platform_type: string | null;
};

export type WhatsappBusinessProfile = {
  about: string | null;
  address: string | null;
  description: string | null;
  email: string | null;
  websites: string[];
  vertical: string | null;
  profile_picture_url: string | null;
};

export type WhatsappProfileInput = Partial<
  Omit<WhatsappBusinessProfile, "profile_picture_url">
>;

export type WhatsappQrCode = {
  code: string;
  prefilled_message: string | null;
  deep_link_url: string | null;
  qr_image_url: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

function base(accountId: string, inboxId: number): string {
  return `/api/v1/accounts/${accountId}/inboxes/${inboxId}/whatsapp`;
}

export function useWhatsappPhoneStatus(accountId: string, inboxId: number) {
  return useQuery({
    queryKey: ["whatsapp-phone", accountId, inboxId],
    queryFn: () => apiFetch<WhatsappPhoneStatus>(`${base(accountId, inboxId)}/phone`),
    retry: false,
    staleTime: 60_000,
  });
}

export function useWhatsappProfile(accountId: string, inboxId: number) {
  return useQuery({
    queryKey: ["whatsapp-profile", accountId, inboxId],
    queryFn: () =>
      apiFetch<WhatsappBusinessProfile>(`${base(accountId, inboxId)}/profile`),
    retry: false,
  });
}

export function useUpdateWhatsappProfile(accountId: string, inboxId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: WhatsappProfileInput) =>
      apiFetch<WhatsappBusinessProfile>(`${base(accountId, inboxId)}/profile`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: (data) =>
      qc.setQueryData(["whatsapp-profile", accountId, inboxId], data),
  });
}

/** New profile photo: multipart through our API, which hands it to Meta. */
export function useUploadWhatsappProfilePhoto(accountId: string, inboxId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file, file.name);
      const res = await fetch(`${API_BASE}${base(accountId, inboxId)}/profile/photo`, {
        method: "POST",
        body: form,
      });
      const body = (await res.json().catch(() => ({}))) as
        | WhatsappBusinessProfile
        | { message?: string };
      if (!res.ok) {
        const message =
          (body as { message?: string }).message ?? "No se pudo cambiar la foto.";
        throw new ApiError(res.status, message, body);
      }
      return body as WhatsappBusinessProfile;
    },
    onSuccess: (data) =>
      qc.setQueryData(["whatsapp-profile", accountId, inboxId], data),
  });
}

export function useWhatsappQrCodes(accountId: string, inboxId: number) {
  return useQuery({
    queryKey: ["whatsapp-qr", accountId, inboxId],
    queryFn: async () =>
      (
        await apiFetch<{ qr_codes: WhatsappQrCode[] }>(
          `${base(accountId, inboxId)}/qr`,
        )
      ).qr_codes,
    retry: false,
  });
}

function useQrMutation<T>(
  accountId: string,
  inboxId: number,
  request: (input: T) => Promise<{ qr_codes: WhatsappQrCode[] }>,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: (data) =>
      qc.setQueryData(["whatsapp-qr", accountId, inboxId], data.qr_codes),
  });
}

export function useCreateWhatsappQr(accountId: string, inboxId: number) {
  return useQrMutation(accountId, inboxId, (message: string) =>
    apiFetch(`${base(accountId, inboxId)}/qr`, {
      method: "POST",
      body: JSON.stringify({ prefilled_message: message }),
    }),
  );
}

export function useUpdateWhatsappQr(accountId: string, inboxId: number) {
  return useQrMutation(
    accountId,
    inboxId,
    ({ code, message }: { code: string; message: string }) =>
      apiFetch(`${base(accountId, inboxId)}/qr/${encodeURIComponent(code)}`, {
        method: "POST",
        body: JSON.stringify({ prefilled_message: message }),
      }),
  );
}

export function useDeleteWhatsappQr(accountId: string, inboxId: number) {
  return useQrMutation(accountId, inboxId, (code: string) =>
    apiFetch(`${base(accountId, inboxId)}/qr/${encodeURIComponent(code)}`, {
      method: "DELETE",
    }),
  );
}
