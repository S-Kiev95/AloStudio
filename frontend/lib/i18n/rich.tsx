import { Fragment, type ReactNode } from "react";

/**
 * A translated sentence with elements inside it (a link, a bold name):
 * `rich(t("x.consent"), { music: <a …>…</a> })` puts each `{name}` of the
 * text where the translation placed it, so word order stays the
 * translator's, not the code's.
 */
export function rich(text: string, parts: Record<string, ReactNode>): ReactNode {
  const pieces = text.split(/\{(\w+)\}/);
  return pieces.map((piece, i) =>
    // Odd positions are the names captured by the split.
    i % 2 === 1 ? (
      <Fragment key={i}>{piece in parts ? parts[piece] : `{${piece}}`}</Fragment>
    ) : (
      piece
    ),
  );
}
