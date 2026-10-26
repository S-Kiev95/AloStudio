import type { Metadata } from "next";
import { Geologica, Neonderthaw, Tilt_Neon } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

// Working text, tables and forms (DESIGN.md: Three Faces Rule).
const geologica = Geologica({
  subsets: ["latin", "latin-ext"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

// Signage, sidebar navigation and section tabs.
const tiltNeon = Tilt_Neon({
  subsets: ["latin", "latin-ext"],
  weight: "400",
  variable: "--font-display",
  display: "swap",
});

// Brand wordmark only ("AloStudio").
const neonderthaw = Neonderthaw({
  subsets: ["latin", "latin-ext"],
  weight: "400",
  variable: "--font-script",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AloStudio",
  description: "AloStudio dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="es"
      className={`${geologica.variable} ${tiltNeon.variable} ${neonderthaw.variable}`}
      suppressHydrationWarning
    >
      <body>
        {/* Skip-link for keyboard users. Visible only when focused. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-control focus:bg-primary focus:px-3 focus:py-1.5 focus:text-sm focus:font-medium focus:text-primary-fg"
        >
          Saltar al contenido
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
