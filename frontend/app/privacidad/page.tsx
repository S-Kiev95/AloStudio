import type { Metadata } from "next";

import {
  OPERATOR,
  PRIVACY_LAST_UPDATED,
  PRIVACY_SECTIONS,
} from "@/lib/legal/privacy";

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
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="space-y-3 border-b border-border pb-8">
        <p className="text-sm font-medium text-primary">AloStudio</p>
        <h1 className="text-3xl font-semibold tracking-tight">
          Política de privacidad
        </h1>
        <p className="text-sm text-fg-muted">
          Última actualización: {PRIVACY_LAST_UPDATED}
        </p>
      </header>

      <div className="space-y-10 py-10">
        {PRIVACY_SECTIONS.map((section) => (
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
          Responsable del tratamiento: <strong>{OPERATOR.legalName}</strong>
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
      </footer>
    </main>
  );
}
