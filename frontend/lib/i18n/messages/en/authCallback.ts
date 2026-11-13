import type { authCallback as es } from "../es/authCallback";
import type { Strings } from "../types";

export const authCallback: Strings<typeof es> = {
  googleCancelled: "Signing in with Google was cancelled.",
  googleFailed: "Couldn't sign in with Google.",
  googleTitle: "Sign in with Google",
  signingIn: "Signing in…",
  ssoNoToken: "The access link doesn't include a token.",
  ssoFailed: "Couldn't sign in. The link may have expired.",
  ssoTitle: "Access from Postiz",
};
