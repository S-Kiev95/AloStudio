import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

// BinancePlex substitute: monospace tabular numerals for prices, counts,
// metrics, timestamps. Exposed as --font-numeric (Tailwind `font-numeric`).
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-numeric",
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
      className={`${inter.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <body>
        {/* Skip-link for keyboard users. Visible only when focused. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-1.5 focus:text-sm focus:font-medium focus:text-primary-fg"
        >
          Saltar al contenido
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
