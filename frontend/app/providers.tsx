"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { ThemeProvider } from "next-themes";
import { useState, type ReactNode } from "react";

import type { Locale } from "@/lib/i18n/config";
import { I18nProvider } from "@/lib/i18n/provider";
import { makeQueryClient } from "@/lib/query";

/**
 * App-wide client providers. TanStack Query holds all server state;
 * next-themes drives the light/dark `.dark` class (system-aware); the
 * interface language comes from the server (cookie or browser).
 */
export function Providers({
  locale,
  children,
}: {
  locale: Locale;
  children: ReactNode;
}) {
  const [queryClient] = useState(makeQueryClient);

  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
      <QueryClientProvider client={queryClient}>
        <I18nProvider locale={locale}>{children}</I18nProvider>
        {process.env.NODE_ENV === "development" ? (
          <ReactQueryDevtools initialIsOpen={false} />
        ) : null}
      </QueryClientProvider>
    </ThemeProvider>
  );
}
