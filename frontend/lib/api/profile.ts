import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/**
 * Client-side hooks over the ``/api/v1/profile`` endpoints. The
 * server-only :func:`lib/auth/profile.ts:getProfile` is for the
 * dashboard layout's initial render; these are for the Settings →
 * Profile / Security forms.
 */

export type ProfileUser = {
  id: number;
  name: string;
  email: string;
  available_name?: string;
  display_name?: string | null;
  avatar_url?: string | null;
  message_signature?: string | null;
  pubsub_token?: string;
  ui_settings?: Record<string, unknown>;
  custom_attributes?: Record<string, unknown>;
  account_id?: number;
  accounts?: {
    id: number;
    name: string;
    role?: string;
    availability?: string;
  }[];
};

export type ProfileResponse = {
  data: ProfileUser;
};

export type ProfileUpdateInput = {
  name?: string;
  email?: string;
  display_name?: string | null;
  avatar_url?: string | null;
  message_signature?: string | null;
  phone_number?: string | null;
};

export type ChangePasswordInput = {
  current_password: string;
  password: string;
  password_confirmation: string;
};

/** ``GET /api/v1/profile`` — current user envelope. */
export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: async () => {
      const res = await apiFetch<ProfileResponse>("/api/v1/profile");
      return res.data;
    },
    staleTime: 60_000,
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["profile"] });
}

/** ``PUT /api/v1/profile`` — partial profile update (no password). */
export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: ProfileUpdateInput) => {
      const res = await apiFetch<ProfileResponse>("/api/v1/profile", {
        method: "PUT",
        body: JSON.stringify({ profile: input }),
      });
      return res.data;
    },
    onSuccess: () => invalidate(qc),
  });
}

/**
 * ``PUT /api/v1/profile`` — password rotation branch. Same endpoint as
 * profile update; the backend checks ``current_password`` before
 * accepting the new password (422 on mismatch).
 */
export function useChangePassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: ChangePasswordInput) => {
      const res = await apiFetch<ProfileResponse>("/api/v1/profile", {
        method: "PUT",
        body: JSON.stringify({ profile: input }),
      });
      return res.data;
    },
    onSuccess: () => invalidate(qc),
  });
}
