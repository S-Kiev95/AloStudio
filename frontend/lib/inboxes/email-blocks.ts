import { clientT } from "@/lib/i18n/client-t";

/** A stack of blocks, and the email HTML it renders to.
 *
 *  Kept out of the components so the generator can be tested on its own:
 *  what it emits goes to every customer of the organisation, and the
 *  rules it has to respect are mail-client rules, not browser ones.
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
export type CanvasKind = "template" | "signature";

export type HeaderBlock = {
  id: string;
  type: "header";
  logoUrl: string;
  logoWidth: number;
  title: string;
  subtitle: string;
  background: string;
  textColor: string;
  align: Align;
  paddingY?: number;
};

export type TextBlock = {
  id: string;
  type: "text";
  text: string;
  align: Align;
  fontSize: number;
  color: string;
  bold: boolean;
  backgroundColor?: string;
  paddingY?: number;
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
  paddingY?: number;
};

export type ButtonBlock = {
  id: string;
  type: "button";
  label: string;
  href: string;
  background: string;
  color: string;
  align: Align;
  borderRadius?: number;
  paddingY?: number;
};

export type DividerBlock = {
  id: string;
  type: "divider";
  color: string;
  thickness?: number;
  paddingY?: number;
};

export type SpacerBlock = { id: string; type: "spacer"; height: number };

export type ColumnsBlock = {
  id: string;
  type: "columns";
  leftTitle: string;
  leftText: string;
  leftImage: string;
  rightTitle: string;
  rightText: string;
  rightImage: string;
  textColor: string;
  paddingY?: number;
};

export type SocialLink = {
  id: string;
  label: string;
  url: string;
};

export type SocialBlock = {
  id: string;
  type: "social";
  links: SocialLink[];
  align: Align;
  color: string;
  paddingY?: number;
};

/** Where the agent's message goes. Exactly one, always, on templates. */
export type ContentBlock = { id: string; type: "content" };

export type SignatureBlock = {
  id: string;
  type: "signature";
  showAgent: boolean;
  showMailbox: boolean;
  showOrg?: boolean;
  paddingY?: number;
};

export type Block =
  | HeaderBlock
  | TextBlock
  | ImageBlock
  | ButtonBlock
  | DividerBlock
  | SpacerBlock
  | ColumnsBlock
  | SocialBlock
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
  fontFamily: "Arial, Helvetica, sans-serif", // i18n-ignore
};

export function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function blankBlock(type: Block["type"]): Block {
  const id = newId();
  switch (type) {
    case "header":
      return {
        id,
        type: "header",
        logoUrl: "",
        logoWidth: 140,
        title: clientT()("settingsEmailTpl.defaults.headerTitle"),
        subtitle: "",
        background: "#003366",
        textColor: "#ffffff",
        align: "left",
        paddingY: 20,
      };
    case "text":
      return {
        id,
        type: "text",
        text: clientT()("settingsEmailTpl.defaults.text"),
        align: "left",
        fontSize: 15,
        color: "#1f2328",
        bold: false,
        paddingY: 6,
      };
    case "image":
      return {
        id,
        type: "image",
        src: "",
        alt: "",
        widthPct: 100,
        align: "center",
        href: "",
        paddingY: 8,
      };
    case "button":
      return {
        id,
        type: "button",
        label: clientT()("settingsEmailTpl.defaults.button"),
        href: "",
        background: "#003366",
        color: "#ffffff",
        align: "center",
        borderRadius: 6,
        paddingY: 8,
      };
    case "divider":
      return {
        id,
        type: "divider",
        color: "#e5e7eb",
        thickness: 1,
        paddingY: 12,
      };
    case "spacer":
      return { id, type: "spacer", height: 24 };
    case "columns":
      return {
        id,
        type: "columns",
        leftTitle: clientT()("settingsEmailTpl.defaults.colLeft"),
        leftText: clientT()("settingsEmailTpl.defaults.text"),
        leftImage: "",
        rightTitle: clientT()("settingsEmailTpl.defaults.colRight"),
        rightText: clientT()("settingsEmailTpl.defaults.text"),
        rightImage: "",
        textColor: "#1f2328",
        paddingY: 10,
      };
    case "social":
      return {
        id,
        type: "social",
        align: "center",
        color: "#003366",
        paddingY: 10,
        links: [
          { id: newId(), label: "Web", url: "https://ejemplo.com" },
          { id: newId(), label: "Instagram", url: "https://instagram.com" },
          { id: newId(), label: "LinkedIn", url: "https://linkedin.com" },
        ],
      };
    case "signature":
      return {
        id,
        type: "signature",
        showAgent: true,
        showMailbox: false,
        showOrg: false,
        paddingY: 8,
      };
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

export function createDefaultSignatureDocument(): BlockDocument {
  return {
    kind: "blocks",
    page: {
      ...DEFAULT_PAGE,
      pageColor: "#ffffff",
      width: 520,
    },
    blocks: [
      {
        id: newId(),
        type: "text",
        text: "{{nombre}}\n{{cargo}}",
        align: "left",
        fontSize: 15,
        color: "#1f2328",
        bold: true,
        paddingY: 2,
      },
      {
        id: newId(),
        type: "text",
        text: "{{correo}} · {{telefono}}",
        align: "left",
        fontSize: 13,
        color: "#5b6470",
        bold: false,
        paddingY: 2,
      },
      {
        id: newId(),
        type: "divider",
        color: "#e5e7eb",
        thickness: 1,
        paddingY: 8,
      },
      {
        id: newId(),
        type: "social",
        align: "left",
        color: "#003366",
        paddingY: 4,
        links: [{ id: newId(), label: "Web", url: "https://ejemplo.com" }],
      },
    ],
  };
}

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

/** Only http(s), mailto and tel reach an href.
 *
 *  A `javascript:` URL is inert in every mail client, but the same
 *  template is shown in the dashboard preview, which is a browser. */
function safeHref(raw: string): string {
  const url = (raw || "").trim();
  if (/^(https?:|mailto:|tel:)/i.test(url)) return esc(url);
  return "";
}

function safeImgSrc(raw: string): string {
  const url = (raw || "").trim();
  if (/^(https?:\/\/|\/public\/|data:image\/(?:png|jpe?g|gif|webp);base64,)/i.test(url)) {
    return esc(url);
  }
  return "";
}

function paragraphs(text: string): string {
  return (text || "")
    .split(/\n{2,}/)
    .map((p) => esc(p).replace(/\n/g, "<br>"))
    .filter((p) => p.length > 0)
    .map((p) => `<p style="margin:0 0 8px">${p}</p>`)
    .join("");
}

function padStyle(paddingY: number | undefined, horizontal = 28): string {
  const py = Math.max(0, Math.min(64, paddingY ?? 0));
  return `padding:${py}px ${horizontal}px`;
}

function renderColumnCell(
  title: string,
  text: string,
  imageUrl: string,
  textColor: string,
  colWidth: number,
): string {
  const parts: string[] = [];
  const src = safeImgSrc(imageUrl);
  if (src) {
    parts.push(
      `<img src="${src}" alt="${esc(title)}" width="${colWidth}" ` +
        `style="width:100%;max-width:${colWidth}px;height:auto;display:block;border:0;margin-bottom:8px;border-radius:4px" />`,
    );
  }
  if (title.trim()) {
    parts.push(
      `<p style="margin:0 0 6px;font-size:15px;font-weight:bold;color:${esc(textColor)}">${esc(
        title.trim(),
      )}</p>`,
    );
  }
  if (text.trim()) {
    parts.push(
      `<div style="font-size:14px;line-height:1.5;color:${esc(textColor)}">${paragraphs(text)}</div>`,
    );
  }
  return parts.join("");
}

function renderBlock(
  block: Block,
  page: PageSettings,
  horizontalPad: number,
): string {
  switch (block.type) {
    case "header": {
      const py = Math.max(8, Math.min(48, block.paddingY ?? 20));
      const logoSrc = safeImgSrc(block.logoUrl);
      const logoW = Math.max(40, Math.min(280, block.logoWidth || 140));
      const margin =
        block.align === "center"
          ? "margin:0 auto 8px"
          : block.align === "right"
            ? "margin:0 0 8px auto"
            : "margin:0 0 8px 0";
      const logoHtml = logoSrc
        ? `<img src="${logoSrc}" alt="${esc(block.title)}" width="${logoW}" ` +
          `style="width:${logoW}px;max-width:100%;height:auto;display:block;border:0;${margin}" />`
        : "";
      const titleHtml = block.title.trim()
        ? `<div style="font-size:20px;font-weight:bold;line-height:1.3;color:${esc(
            block.textColor,
          )}">${esc(block.title.trim())}</div>`
        : "";
      const subHtml = block.subtitle.trim()
        ? `<div style="margin-top:4px;font-size:13px;line-height:1.4;color:${esc(
            block.textColor,
          )}">${esc(block.subtitle.trim())}</div>`
        : "";
      return (
        `<tr><td align="${block.align}" style="background:${esc(
          block.background,
        )};padding:${py}px ${horizontalPad}px;text-align:${block.align}">` +
        `${logoHtml}${titleHtml}${subHtml}</td></tr>`
      );
    }
    case "text": {
      const weight = block.bold ? "bold" : "normal";
      const bg = block.backgroundColor ? `;background:${esc(block.backgroundColor)}` : "";
      return `<tr><td style="${padStyle(block.paddingY, horizontalPad)}${bg};text-align:${
        block.align
      };font-size:${block.fontSize}px;line-height:1.55;color:${esc(
        block.color,
      )};font-weight:${weight}">${paragraphs(block.text)}</td></tr>`;
    }
    case "image": {
      const src = safeImgSrc(block.src);
      if (!src) return "";
      // The width attribute is for Outlook, which ignores the CSS rule.
      const px = Math.round((page.width - horizontalPad * 2) * (block.widthPct / 100));
      const img =
        `<img src="${src}" alt="${esc(block.alt)}" width="${px}" ` +
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
      return `<tr><td style="${padStyle(
        block.paddingY,
        horizontalPad,
      )}"><div style="${margin};width:${px}px;max-width:100%">${inner}</div></td></tr>`;
    }
    case "button": {
      const href = safeHref(block.href);
      const label = esc(block.label);
      const radius = Math.max(0, Math.min(32, block.borderRadius ?? 6));
      const py = Math.max(4, Math.min(40, block.paddingY ?? 8));
      // Table-based: a styled <a> loses its background in Outlook.
      const button =
        `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">` +
        `<tr><td style="background:${esc(block.background)};border-radius:${radius}px">` +
        `<a href="${href || "#"}" target="_blank" style="display:inline-block;padding:12px 22px;` +
        `font-family:${page.fontFamily};font-size:15px;font-weight:bold;color:${esc(
          block.color,
        )};text-decoration:none">${label}</a>` +
        `</td></tr></table>`;
      return `<tr><td style="padding:${py}px ${horizontalPad}px" align="${block.align}">${button}</td></tr>`;
    }
    case "divider": {
      const thick = Math.max(1, Math.min(6, block.thickness ?? 1));
      const py = Math.max(4, Math.min(40, block.paddingY ?? 12));
      return `<tr><td style="padding:${py}px ${horizontalPad}px"><div style="border-top:${thick}px solid ${esc(
        block.color,
      )};font-size:0;line-height:0">&nbsp;</div></td></tr>`;
    }
    case "spacer":
      return `<tr><td style="height:${block.height}px;font-size:0;line-height:0">&nbsp;</td></tr>`;
    case "columns": {
      const py = Math.max(0, Math.min(48, block.paddingY ?? 10));
      const colW = Math.round((page.width - horizontalPad * 2 - 16) / 2);
      const left = renderColumnCell(
        block.leftTitle,
        block.leftText,
        block.leftImage,
        block.textColor,
        colW,
      );
      const right = renderColumnCell(
        block.rightTitle,
        block.rightText,
        block.rightImage,
        block.textColor,
        colW,
      );
      return (
        `<tr><td style="padding:${py}px ${horizontalPad}px">` +
        `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">` +
        `<tr>` +
        `<td width="50%" valign="top" style="width:50%;padding-right:8px;vertical-align:top">${left}</td>` +
        `<td width="50%" valign="top" style="width:50%;padding-left:8px;vertical-align:top">${right}</td>` +
        `</tr></table></td></tr>`
      );
    }
    case "social": {
      const py = Math.max(0, Math.min(40, block.paddingY ?? 10));
      const valid = block.links
        .map((l) => ({ label: l.label.trim(), href: safeHref(l.url) }))
        .filter((l) => l.label && l.href);
      if (valid.length === 0) return "";
      const cells = valid
        .map(
          (l) =>
            `<td style="padding:0 8px 0 0"><a href="${l.href}" target="_blank" ` +
            `style="display:inline-block;padding:6px 12px;border:1px solid ${esc(
              block.color,
            )};border-radius:4px;font-family:${page.fontFamily};font-size:12px;font-weight:bold;` +
            `color:${esc(block.color)};text-decoration:none">${esc(l.label)}</a></td>`,
        )
        .join("");
      return (
        `<tr><td align="${block.align}" style="padding:${py}px ${horizontalPad}px">` +
        `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">` +
        `<tr>${cells}</tr></table></td></tr>`
      );
    }
    case "content":
      return `<tr><td style="padding:12px ${horizontalPad}px;font-size:15px;line-height:1.55;color:${esc(
        page.textColor,
      )}">${CONTENT_TOKEN}</td></tr>`;
    case "signature": {
      const rows: string[] = [];
      if (block.showAgent && !block.showMailbox && !block.showOrg) {
        rows.push(
          `<div style="font-size:14px;color:${esc(page.textColor)}">{{firma}}</div>`,
        );
      } else {
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
        if (block.showOrg) {
          rows.push(
            `<div style="margin-top:10px;font-size:13px;color:#5b6470">{{firma_organizacion}}</div>`,
          );
        }
      }
      if (rows.length === 0) return "";
      return `<tr><td style="${padStyle(block.paddingY ?? 8, horizontalPad)}">${rows.join("")}</td></tr>`;
    }
  }
}

/** The email HTML for a document.
 *
 *  For templates, always emits ``{{contenido}}`` even if the author deleted
 *  the block. For signatures (``kind: "signature"``), renders a compact table
 *  without an outer page wrapper or content token.
 */
export function renderBlocks(
  doc: BlockDocument,
  options: { kind?: CanvasKind } = {},
): string {
  const kind = options.kind ?? "template";
  const { page } = doc;

  if (kind === "signature") {
    const rows = doc.blocks
      .filter((b) => b.type !== "content")
      .map((b) => renderBlock(b, page, 12))
      .join("");
    return (
      `<table role="presentation" cellpadding="0" cellspacing="0" border="0" ` +
      `width="${page.width}" style="width:${page.width}px;max-width:100%;` +
      `background:${esc(page.bodyColor)};font-family:${page.fontFamily};border-collapse:collapse">` +
      rows +
      `</table>`
    );
  }

  const rows = doc.blocks.map((b) => renderBlock(b, page, 28)).join("");
  const hasContent = doc.blocks.some((b) => b.type === "content");
  const fallback = hasContent
    ? ""
    : `<tr><td style="padding:12px 28px;font-size:15px;line-height:1.55;color:${esc(
        page.textColor,
      )}">${CONTENT_TOKEN}</td></tr>`;

  const startsWithHeader = doc.blocks[0]?.type === "header";
  const topSpacer = startsWithHeader
    ? ""
    : `<tr><td style="height:28px;font-size:0;line-height:0">&nbsp;</td></tr>`;

  return (
    `<div style="background:${esc(page.pageColor)};padding:24px 0;font-family:${page.fontFamily}">` +
    `<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" ` +
    `width="${page.width}" style="width:${page.width}px;max-width:100%;margin:0 auto;` +
    `background:${esc(page.bodyColor)};border-radius:8px;overflow:hidden;border-collapse:collapse">` +
    topSpacer +
    rows +
    fallback +
    `<tr><td style="height:28px;font-size:0;line-height:0">&nbsp;</td></tr>` +
    `</table></div>`
  );
}
