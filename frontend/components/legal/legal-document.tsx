import Link from "next/link";

import { LEGAL_PAGES, OPERATOR, type LegalSection } from "@/lib/legal/operator";

type LegalDocumentProps = {
  title: string;
  lastUpdated: string;
  sections: LegalSection[];
};

/**
 * Shared layout for the public legal pages (privacy, terms, data
 * deletion). Meta reads all three anonymously at App Review, so they are
 * plain server-rendered HTML with no client state and no session.
 */
export function LegalDocument({
  title,
  lastUpdated,
  sections,
}: LegalDocumentProps) {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="space-y-3 border-b border-border pb-8">
        <p className="text-sm font-medium text-primary">AloStudio</p>
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-fg-muted">
          Última actualización: {lastUpdated}
        </p>
      </header>

      <div className="space-y-10 py-10">
        {sections.map((section) => (
          <section key={section.title} className="space-y-3">
            <h2 className="text-xl font-semibold tracking-tight">
              {section.title}
            </h2>
            {section.paragraphs.map((text) => (
              <p key={text} className="text-sm leading-relaxed text-fg-muted">
                {text}
              </p>
            ))}
            {section.bullets ? (
              <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-fg-muted">
                {section.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}
      </div>

      <footer className="space-y-2 border-t border-border pt-8 text-sm text-fg-muted">
        <p>
          Responsable: <strong>{OPERATOR.legalName}</strong> (
          {OPERATOR.country})
        </p>
        <p>
          Consultas y ejercicio de derechos:{" "}
          <a
            href={`mailto:${OPERATOR.contactEmail}`}
            className="text-info hover:underline"
          >
            {OPERATOR.contactEmail}
          </a>
        </p>
        <nav className="flex flex-wrap gap-4 pt-2">
          {LEGAL_PAGES.map((page) => (
            <Link
              key={page.href}
              href={page.href}
              className="text-info hover:underline"
            >
              {page.label}
            </Link>
          ))}
        </nav>
      </footer>
    </main>
  );
}
