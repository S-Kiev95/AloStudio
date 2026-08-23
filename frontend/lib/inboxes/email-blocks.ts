/** A stack of blocks, and the email HTML it renders to.
 *
 *  Kept out of the components so the generator can be tested on its own:
 *  what it emits goes to every customer of the organisation, and the
 *  rules it has to respect are mail-client rules, not browser ones.
 *
 *  **Why blocks and not a canvas.** Outlook renders with Word's engine —
 *  no flexbox, no grid, `position:absolute` ignored. Free XY placement
 *  produces layouts the medium cannot express, so every serious email
 *  builder is a vertical stack of full-width rows. This is that.
 *
 *  Three rules the output obeys, all learned from mail clients rather
 *  than chosen:
 *    - Tables for layout. A `<div>` stack collapses in Outlook.
 *    - Inline styles only. Gmail strips `<style>` blocks.
 *    - Images carry a `width` attribute as well as CSS, because Outlook
 *      reads the attribute and ignores the rule.
 */

export const CONTENT_TOKEN = "{{contenido}}";

export type Align = "left" | "center" | "right";

export type TextBlock = {
  id: string;
  type: "text";
  text: string;
  align: Align;
  fontSize: number;
  color: string;
  bold: boolean;
};

export type ImageBlock = {
  id: string;
  type: "image";
  src: string;
  alt: string;
  /** Percentage of the template width, 10–100. Percentages rather than
   *  pixels so the image still fits when a phone narrows the layout. */
  widthPct: number;
  align: Align;
  href: string;
};

export type ButtonBlock = {
  id: string;
  type: "button";
  label: string;
  href: string;
  background: string;
  color: string;
  align: Align;
};

export type DividerBlock = { id: string; type: "divider"; color: string };
export type SpacerBlock = { id: string; type: "spacer"; height: number };

/** Where the agent's message goes. Exactly one, always. */
export type ContentBlock = { id: string; type: "content" };

export type SignatureBlock = {
  id: string;
  type: "signature";
  showAgent: boolean;
  showMailbox: boolean;
};

export type Block =
  | TextBlock
  | ImageBlock
  | ButtonBlock
  | DividerBlock
  | SpacerBlock
  | ContentBlock
  | SignatureBlock;

export type PageSettings = {
  /** Backdrop behind the card. */
  pageColor: string;
  /** The card itself. */
  bodyColor: string;
  textColor: string;
  /** 480–700. Wider than ~700 and desktop clients start scrolling. */
  width: number;
  fontFamily: string;
};

export type BlockDocument = {
  /** Discriminates this from the older flat design in the same column. */
  kind: "blocks";
  page: PageSettings;
  blocks: Block[];
};

export const DEFAULT_PAGE: PageSettings = {
  pageColor: "#f4f5f7",
  bodyColor: "#ffffff",
  textColor: "#1f2328",
  width: 600,
  fontFamily: "Arial, Helvetica, sans-serif",
};

export function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function blankBlock(type: Block["type"]): Block {
  const id = newId();
  switch (type) {
    case "text":
      return {
        id,
        type: "text",
        text: "Escribí acá",
        align: "left",
        fontSize: 15,
        color: "#1f2328",
        bold: false,
      };
    case "image":
      return { id, type: "image", src: "", alt: "", widthPct: 100, align: "center", href: "" };
    case "button":
      return {
        id,
        type: "button",
        label: "Ver más",
        href: "",
        background: "#003366",
        color: "#ffffff",
        align: "center",
      };
    case "divider":
      return { id, type: "divider", color: "#e5e7eb" };
    case "spacer":
      return { id, type: "spacer", height: 24 };
    case "signature":
      return { id, type: "signature", showAgent: true, showMailbox: true };
    case "content":
      return { id, type: "content" };
  }
}

export const DEFAULT_DOCUMENT: BlockDocument = {
  kind: "blocks",
  page: DEFAULT_PAGE,
  blocks: [
    { ...(blankBlock("image") as ImageBlock), widthPct: 40 },
    blankBlock("content"),
    blankBlock("divider"),
    blankBlock("signature"),
  ],
};

export function isBlockDocument(value: unknown): value is BlockDocument {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as { kind?: unknown }).kind === "blocks" &&
    Array.isArray((value as { blocks?: unknown }).blocks)
  );
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

/** Escape text an author typed into a control.
 *
 *  They are writing a label, not markup — an ampersand in "Ventas &
 *  Post Venta" must not break the email. */
function esc(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Only http(s) and mailto reach an href.
 *
 *  A `javascript:` URL is inert in every mail client, but the same
 *  template is shown in the dashboard preview, which is a browser. */
function safeHref(raw: string): string {
  const url = (raw || "").trim();
  if (/^(https?:|mailto:)/i.test(url)) return esc(url);
  return "";
}

function paragraphs(text: string): string {
  return (text || "")
    .split(/\n{2,}/)
    .map((p) => esc(p).replace(/\n/g, "<br>"))
    .filter((p) => p.length > 0)
    .map((p) => `<p style="margin:0 0 12px">${p}</p>`)
    .join("");
}

const PAD = "padding:0 28px";

function renderBlock(block: Block, page: PageSettings): string {
  switch (block.type) {
    case "text": {
      const weight = block.bold ? "bold" : "normal";
      return `<tr><td style="${PAD};text-align:${block.align};font-size:${block.fontSize}px;line-height:1.55;color:${esc(
        block.color,
      )};font-weight:${weight}">${paragraphs(block.text)}</td></tr>`;
    }
    case "image": {
      if (!block.src.trim()) return "";
      // The width attribute is for Outlook, which ignores the CSS rule.
      const px = Math.round((page.width - 56) * (block.widthPct / 100));
      const img =
        `<img src="${esc(block.src)}" alt="${esc(block.alt)}" width="${px}" ` +
        `style="width:${px}px;max-width:100%;height:auto;display:block;border:0" />`;
      const link = safeHref(block.href);
      const inner = link ? `<a href="${link}" target="_blank">${img}</a>` : img;
      // Centring an image means centring its container, not text-align on
      // the image itself — Outlook disagrees about the latter.
      const margin =
        block.align === "center"
          ? "margin:0 auto"
          : block.align === "right"
            ? "margin:0 0 0 auto"
            : "margin:0";
      return `<tr><td style="${PAD}"><div style="${margin};width:${px}px;max-width:100%">${inner}</div></td></tr>`;
    }
    case "button": {
      const href = safeHref(block.href);
      const label = esc(block.label);
      // Table-based: a styled <a> loses its background in Outlook.
      const button =
        `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">` +
        `<tr><td style="background:${esc(block.background)};border-radius:6px">` +
        `<a href="${href || "#"}" target="_blank" style="display:inline-block;padding:12px 22px;` +
        `font-family:${page.fontFamily};font-size:15px;font-weight:bold;color:${esc(
          block.color,
        )};text-decoration:none">${label}</a>` +
        `</td></tr></table>`;
      return `<tr><td style="${PAD};padding-top:4px;padding-bottom:4px" align="${block.align}">${button}</td></tr>`;
    }
    case "divider":
      return `<tr><td style="${PAD}"><div style="border-top:1px solid ${esc(
        block.color,
      )};font-size:0;line-height:0">&nbsp;</div></td></tr>`;
    case "spacer":
      return `<tr><td style="height:${block.height}px;font-size:0;line-height:0">&nbsp;</td></tr>`;
    case "content":
      return `<tr><td style="${PAD};font-size:15px;line-height:1.55;color:${esc(
        page.textColor,
      )}">${CONTENT_TOKEN}</td></tr>`;
    case "signature": {
      const rows: string[] = [];
      if (block.showAgent) {
        rows.push(
          `<div style="font-size:14px;color:${esc(page.textColor)}">{{firma_agente}}</div>`,
        );
      }
      if (block.showMailbox) {
        rows.push(
          `<div style="margin-top:10px;font-size:13px;color:#5b6470">{{firma}}</div>`,
        );
      }
      if (rows.length === 0) return "";
      return `<tr><td style="${PAD}">${rows.join("")}</td></tr>`;
    }
  }
}

/** The email HTML for a document.
 *
 *  Always emits the content token, even if the author deleted the block:
 *  a template without it is refused on save, and silently dropping the
 *  agent's message is the one failure nothing downstream would notice.
 */
export function renderBlocks(doc: BlockDocument): string {
  const { page } = doc;
  const rows = doc.blocks.map((b) => renderBlock(b, page)).join("");
  const hasContent = doc.blocks.some((b) => b.type === "content");
  const fallback = hasContent
    ? ""
    : `<tr><td style="${PAD};font-size:15px;line-height:1.55;color:${esc(
        page.textColor,
      )}">${CONTENT_TOKEN}</td></tr>`;

  return (
    `<div style="background:${esc(page.pageColor)};padding:24px 0;font-family:${page.fontFamily}">` +
    `<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" ` +
    `width="${page.width}" style="width:${page.width}px;max-width:100%;margin:0 auto;` +
    `background:${esc(page.bodyColor)};border-radius:8px;border-collapse:collapse">` +
    `<tr><td style="height:28px;font-size:0;line-height:0">&nbsp;</td></tr>` +
    rows +
    fallback +
    `<tr><td style="height:28px;font-size:0;line-height:0">&nbsp;</td></tr>` +
    `</table></div>`
  );
}
