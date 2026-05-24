import "server-only";

import { AUTH_HEADERS } from "./cookies";
import { getAuthTokens } from "./session";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

export type ProfileAccount = {
  id: number;
  name: string;
  role: string | null;
  availability?: string | null;
};

export type Profile = {
  id: number;
  name: string;
  email: string;
  availableName: string | null;
  activeAccountId: number | null;
  accounts: ProfileAccount[];
};

/** Fetch the signed-in user's profile from the backend (server-side). */
export async function getProfile(): Promise<Profile | null> {
  const tokens = await getAuthTokens();
  if (!tokens) return null;
  try {
    const res = await fetch(`${BACKEND}/api/v1/profile`, {
      headers: {
        [AUTH_HEADERS.accessToken]: tokens.accessToken,
        [AUTH_HEADERS.client]: tokens.client,
        [AUTH_HEADERS.uid]: tokens.uid,
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = (await res.json())?.data ?? {};
    return {
      id: data.id,
      name: data.name ?? "",
      email: data.email ?? "",
      availableName: data.available_name ?? null,
      activeAccountId: data.account_id ?? null,
      accounts: (data.accounts ?? []).map(
        (a: { id: number; name: string; role?: string; availability?: string }) => ({
          id: a.id,
          name: a.name,
          role: a.role ?? null,
          availability: a.availability ?? null,
        }),
      ),
    };
  } catch {
    return null;
  }
}
