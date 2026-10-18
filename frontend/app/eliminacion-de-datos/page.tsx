import type { Metadata } from "next";

import { LegalDocument } from "@/components/legal/legal-document";
import {
  DATA_DELETION_LAST_UPDATED,
  DATA_DELETION_SECTIONS,
} from "@/lib/legal/data-deletion";

export const metadata: Metadata = {
  title: "Eliminación de datos · AloStudio",
  description:
    "Cómo pedir que AloStudio elimine tus mensajes, datos de contacto y cuentas conectadas.",
};

/**
 * Public — the auth middleware only guards /accounts/*. Registered as the
 * Data Deletion Instructions URL of the Meta app: Meta sends people here
 * when they remove the app from their account settings.
 */
export default function EliminacionDeDatosPage() {
  return (
    <LegalDocument
      title="Eliminación de datos"
      lastUpdated={DATA_DELETION_LAST_UPDATED}
      sections={DATA_DELETION_SECTIONS}
    />
  );
}
