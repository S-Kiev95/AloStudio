/**
 * Who operates this AloStudio deployment, shared by every legal page.
 *
 * Meta shows these pages to App Review and to every person who connects
 * an account, so the name and mailbox here must be real and answered.
 */
export const OPERATOR = {
  /** Responsable del tratamiento y titular del servicio. */
  legalName: "Ezequiel Viera",
  /** Casilla que atiende consultas, derechos y solicitudes de borrado. */
  contactEmail: "vezequiel58@gmail.com",
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
