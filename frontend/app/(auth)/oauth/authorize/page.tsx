import { Suspense } from "react";

import { OAuthConsent } from "@/components/oauth/oauth-consent";
import { getT } from "@/lib/i18n/server";

/** Where an app sends the user to authorize it (``/oauth/authorize?…``). */
export default async function OAuthAuthorizePage() {
  const t = await getT();
  return (
    <Suspense fallback={<p className="text-sm text-fg-muted">{t("common.loading")}</p>}>
      <OAuthConsent />
    </Suspense>
  );
}
