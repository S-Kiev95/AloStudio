import { describe, expect, it } from "vitest";

import {
  DEFAULT_DESIGN,
  renderDesign,
  type TemplateDesign,
} from "./email-template-design";

const design = (over: Partial<TemplateDesign> = {}): TemplateDesign => ({
  ...DEFAULT_DESIGN,
  ...over,
});

describe("renderDesign", () => {
  it("always leaves a place for the message", () => {
    // Without it the server refuses the template, and rightly: every
    // reply would go out with the agent's text missing.
    expect(renderDesign(design())).toContain("{{contenido}}");
  });

  it("puts the chosen colours in", () => {
    const html = renderDesign(design({ headerColor: "#ff0000" }));
    expect(html).toContain("background:#ff0000");
  });

  it("includes the logo only when asked", () => {
    expect(renderDesign(design({ showLogo: true }))).toContain("{{logo}}");
    expect(renderDesign(design({ showLogo: false }))).not.toContain("{{logo}}");
  });

  it("includes the signature only when asked", () => {
    expect(renderDesign(design({ showSignature: true }))).toContain("{{firma}}");
    expect(renderDesign(design({ showSignature: false }))).not.toContain(
      "{{firma}}",
    );
  });

  it("draws no header when there is nothing to put in it", () => {
    const html = renderDesign(design({ showLogo: false, headerTitle: "  " }));
    expect(html).not.toContain(DEFAULT_DESIGN.headerColor);
  });

  it("escapes what the author typed", () => {
    // They are writing a title, not markup — an ampersand in "Ventas &
    // Post Venta" must not break the email.
    const html = renderDesign(design({ headerTitle: "Ventas & <b>Post</b>" }));
    expect(html).toContain("Ventas &amp; &lt;b&gt;Post&lt;/b&gt;");
    expect(html).not.toContain("<b>Post</b>");
  });

  it("styles inline, because mail clients drop style blocks", () => {
    const html = renderDesign(design({ headerTitle: "Hola" }));
    expect(html).not.toContain("<style");
    expect(html).toContain('style="');
  });

  it("uses no layout a mail client cannot render", () => {
    const html = renderDesign(design({ headerTitle: "Hola" }));
    expect(html).not.toMatch(/display:\s*(flex|grid)/);
  });

  it("keeps a footer note out when it is blank", () => {
    expect(renderDesign(design({ footerNote: "   " }))).not.toContain(
      "margin-top:12px",
    );
  });
});
