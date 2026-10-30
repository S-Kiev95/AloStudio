import { Suspense } from "react";

import { OAuthConsent } from "@/components/oauth/oauth-consent";

/** Where an app sends the user to authorize it (``/oauth/authorize?…``). */
export default function OAuthAuthorizePage() {
  return (
    <Suspense fallback={<p className="text-sm text-fg-muted">Cargando…</p>}>
      <OAuthConsent />
    </Suspense>
  );
}
