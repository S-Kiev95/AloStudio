import type { Metadata } from "next";

import { LegalDocument } from "@/components/legal/legal-document";
import { TERMS_LAST_UPDATED, TERMS_SECTIONS } from "@/lib/legal/terms";

export const metadata: Metadata = {
  title: "Términos del servicio · AloStudio",
  description:
    "Condiciones de uso de AloStudio: cuentas, canales conectados, uso aceptable y ley aplicable.",
};

/**
 * Public — the auth middleware only guards /accounts/*. Registered as the
 * Terms of Service URL of the Meta app, which App Review reads anonymously.
 */
export default function TerminosPage() {
  return (
    <LegalDocument
      title="Términos del servicio"
      lastUpdated={TERMS_LAST_UPDATED}
      sections={TERMS_SECTIONS}
    />
  );
}
