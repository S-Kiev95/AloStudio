/**
 * devise-token-auth credential cookie names.
 *
 * The backend authenticates via the headers ``access-token`` /
 * ``client`` / ``uid`` (+ ``expiry``). We store them as **httpOnly**
 * cookies (set by the login route handler in F.1) so the browser never
 * exposes them to JS. The BFF proxy reads these cookies and re-attaches
 * them as the devise headers on every backend call.
 */
export const AUTH_COOKIES = {
  accessToken: "alo_access_token",
  client: "alo_client",
  uid: "alo_uid",
  expiry: "alo_expiry",
} as const;

/** Header names the backend (devise-token-auth) expects. */
export const AUTH_HEADERS = {
  accessToken: "access-token",
  client: "client",
  uid: "uid",
  expiry: "expiry",
} as const;

export type AuthTokens = {
  accessToken: string;
  client: string;
  uid: string;
  expiry?: string;
};
