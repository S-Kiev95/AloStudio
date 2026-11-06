/**
 * Who operates this AloStudio deployment, shared by every legal page.
 *
 * Meta shows these pages to App Review and to every person who connects
 * an account, so the name and mailbox here must be real and answered.
 * Each installation sets its own at build time, in frontend/.env.local.
 */
export const OPERATOR = {
  /** Responsable del tratamiento y titular del servicio. */
  legalName: process.env.NEXT_PUBLIC_LEGAL_NAME || "Ezequiel Viera",
  /** Casilla que atiende consultas, derechos y solicitudes de borrado. */
  contactEmail: process.env.NEXT_PUBLIC_LEGAL_EMAIL || "vezequiel58@gmail.com",
  /** Domicilio del responsable, si la instalación lo publica. */
  address: process.env.NEXT_PUBLIC_LEGAL_ADDRESS || "",
  /** Jurisdicción cuya ley rige el servicio. */
  country: "Uruguay",
} as const;

export type LegalSection = {
  title: string;
  paragraphs: string[];
  bullets?: string[];
};

/** The three public URLs registered in the Meta app's basic settings. */
export const LEGAL_PAGES = [
  { href: "/privacidad", label: "Política de privacidad" },
  { href: "/terminos", label: "Términos del servicio" },
  { href: "/eliminacion-de-datos", label: "Eliminación de datos" },
] as const;
