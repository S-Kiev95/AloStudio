import type { Metadata } from "next";

import { LegalDocument } from "@/components/legal/legal-document";
import { PRIVACY_LAST_UPDATED, PRIVACY_SECTIONS } from "@/lib/legal/privacy";

export const metadata: Metadata = {
  title: "Política de privacidad · AloStudio",
  description:
    "Qué datos trata AloStudio, con qué fin, cuánto los conserva y cómo ejercer tus derechos.",
};

/**
 * Public — the auth middleware only guards /accounts/*.
 *
 * Meta fetches this URL to validate the app's privacy policy before it
 * will let the app go live, so it has to answer 200 with real HTML to
 * an anonymous request. It is also what App Review reads.
 */
export default function PrivacidadPage() {
  return (
    <LegalDocument
      title="Política de privacidad"
      lastUpdated={PRIVACY_LAST_UPDATED}
      sections={PRIVACY_SECTIONS}
    />
  );
}
