import type { authCallback as es } from "../es/authCallback";
import type { Strings } from "../types";

export const authCallback: Strings<typeof es> = {
  googleCancelled: "Die Anmeldung mit Google wurde abgebrochen.",
  googleFailed: "Anmeldung mit Google nicht möglich.",
  googleTitle: "Mit Google anmelden",
  signingIn: "Anmeldung läuft…",
  ssoNoToken: "Der Zugangslink enthält kein Token.",
  ssoFailed: "Anmeldung nicht möglich. Der Link ist vielleicht abgelaufen.",
  ssoTitle: "Zugang über Postiz",
};
