import type { Metadata } from "next";

export const metadata: Metadata = {
  // Each portal page overrides this — the default here only covers the
  // hypothetical case where someone hits /hc directly.
  title: "Help Center",
  robots: { index: true, follow: true },
};

/**
 * Public Help Center shell — no auth, no app sidebar.
 *
 * Intentionally minimal: each portal renders its own branding header
 * inside :file:`[slug]/layout.tsx`. We just set the page background +
 * font scale here.
 */
export default function HelpCenterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-bg text-fg">
      {children}
      <footer className="mt-12 border-t border-border py-6 text-center text-xs text-fg-muted">
        Powered by AloStudio
      </footer>
    </div>
  );
}
