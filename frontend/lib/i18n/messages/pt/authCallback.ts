import type { authCallback as es } from "../es/authCallback";
import type { Strings } from "../types";

export const authCallback: Strings<typeof es> = {
  googleCancelled: "A entrada com Google foi cancelada.",
  googleFailed: "Não foi possível entrar com Google.",
  googleTitle: "Entrar com Google",
  signingIn: "Entrando…",
  ssoNoToken: "O link de acesso não inclui um token.",
  ssoFailed: "Não foi possível entrar. O link pode ter expirado.",
  ssoTitle: "Acesso pelo Postiz",
};
