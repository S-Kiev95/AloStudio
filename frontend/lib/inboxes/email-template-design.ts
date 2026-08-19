/** The visual designer's settings, and the HTML they produce.
 *
 *  Kept out of the component so the generator can be tested on its own —
 *  what it emits goes to every customer, and the rules it has to respect
 *  are the mail-client ones, not the browser ones. */

export type TemplateDesign = {
  headerColor: string;
  headerTitle: string;
  headerTextColor: string;
  showLogo: boolean;
  pageColor: string;
  bodyColor: string;
  textColor: string;
  showAgentSignature: boolean;
  showSignature: boolean;
  footerNote: string;
};

export const DEFAULT_DESIGN: TemplateDesign = {
  headerColor: "#003366",
  headerTitle: "",
  headerTextColor: "#ffffff",
  showLogo: true,
  pageColor: "#f4f5f7",
  bodyColor: "#ffffff",
  textColor: "#1f2328",
  showAgentSignature: true,
  showSignature: true,
  footerNote: "",
};

/** Escape text a non-technical author typed into a control.
 *
 *  They are writing a title, not markup — an ampersand in "Ventas & Post
 *  Venta" must not break the email. */
function esc(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Build the HTML for a design.
 *
 *  Every rule is an inline `style` attribute: Gmail and Outlook drop
 *  `<style>` blocks, so a stylesheet would render as unstyled text in the
 *  two clients that matter most. Same reason the layout is plain divs and
 *  not flex or grid. */
export function renderDesign(d: TemplateDesign): string {
  const parts: string[] = [];

  parts.push(
    `<div style="background:${d.pageColor};padding:24px;` +
      `font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">`,
    `<div style="max-width:560px;margin:0 auto;background:${d.bodyColor};` +
      `border-radius:8px;overflow:hidden">`,
  );

  const hasHeader = d.showLogo || d.headerTitle.trim().length > 0;
  if (hasHeader) {
    parts.push(
      `<div style="background:${d.headerColor};padding:20px;text-align:center">`,
    );
    if (d.showLogo) parts.push("{{logo}}");
    if (d.headerTitle.trim()) {
      parts.push(
        `<div style="color:${d.headerTextColor};font-size:18px;` +
          `font-weight:bold;margin-top:8px">${esc(d.headerTitle.trim())}</div>`,
      );
    }
    parts.push("</div>");
  }

  parts.push(
    `<div style="padding:24px;color:${d.textColor};font-size:15px;line-height:1.5">`,
    "{{contenido}}",
  );

  // With the message, not down in the institutional block: this is the
  // person who wrote the reply, not the letterhead.
  if (d.showAgentSignature) {
    parts.push(
      `<div style="margin-top:16px;font-size:14px;line-height:1.45">{{firma_agente}}</div>`,
    );
  }

  if (d.showSignature || d.footerNote.trim()) {
    parts.push(
      `<hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0 16px">`,
    );
    if (d.showSignature) {
      parts.push(
        `<div style="color:#5b6470;font-size:13px;line-height:1.45">{{firma}}</div>`,
      );
    }
    if (d.footerNote.trim()) {
      parts.push(
        `<div style="color:#8a919b;font-size:12px;margin-top:12px">` +
          `${esc(d.footerNote.trim())}</div>`,
      );
    }
  }

  parts.push("</div></div></div>");
  return parts.join("\n");
}
