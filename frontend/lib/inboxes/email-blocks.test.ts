import { describe, expect, it } from "vitest";

import {
  type BlockDocument,
  CONTENT_TOKEN,
  DEFAULT_DOCUMENT,
  DEFAULT_PAGE,
  type ImageBlock,
  type TextBlock,
  blankBlock,
  isBlockDocument,
  renderBlocks,
} from "./email-blocks";

function doc(blocks: BlockDocument["blocks"]): BlockDocument {
  return { kind: "blocks", page: DEFAULT_PAGE, blocks };
}

describe("renderBlocks — reglas del medio, no del navegador", () => {
  it("maqueta con tablas, no con divs apilados", () => {
    // Un stack de <div> colapsa en Outlook.
    const html = renderBlocks(DEFAULT_DOCUMENT);
    expect(html).toContain("<table");
    expect(html).toContain('role="presentation"');
  });

  it("no emite ningún bloque <style>", () => {
    // Gmail los descarta enteros: todo va inline.
    const html = renderBlocks(DEFAULT_DOCUMENT);
    expect(html).not.toContain("<style");
  });

  it("las imágenes llevan el atributo width además del CSS", () => {
    // Outlook lee el atributo e ignora la regla.
    const img = { ...(blankBlock("image") as ImageBlock), src: "https://x/y.jpg", widthPct: 50 };
    const html = renderBlocks(doc([img]));
    expect(html).toMatch(/<img[^>]+width="\d+"/);
    expect(html).toMatch(/style="[^"]*width:\d+px/);
    expect(html).toContain("max-width:100%");
  });

  it("el ancho de la imagen sale del porcentaje elegido", () => {
    const mitad = { ...(blankBlock("image") as ImageBlock), src: "https://x/y.jpg", widthPct: 50 };
    const entera = { ...mitad, widthPct: 100 };
    const a = renderBlocks(doc([mitad]));
    const b = renderBlocks(doc([entera]));
    const anchoA = Number(a.match(/<img[^>]+width="(\d+)"/)![1]);
    const anchoB = Number(b.match(/<img[^>]+width="(\d+)"/)![1]);
    expect(anchoB).toBeGreaterThan(anchoA);
    expect(anchoA).toBeCloseTo(anchoB / 2, 0);
  });

  it("el botón es una tabla, no un <a> con fondo", () => {
    // Un <a> estilado pierde el fondo en Outlook.
    const html = renderBlocks(doc([blankBlock("button")]));
    expect(html).toMatch(/<table[^>]*>[\s\S]*<a /);
  });
});

describe("renderBlocks — lo que protege al destinatario", () => {
  it("siempre incluye el marcador del mensaje", () => {
    const html = renderBlocks(doc([blankBlock("content")]));
    expect(html).toContain(CONTENT_TOKEN);
  });

  it("lo agrega aunque el autor haya borrado el bloque", () => {
    // Perder el mensaje del agente es el único fallo que nada aguas
    // abajo notaría: el envío sale bien y llega un cascarón vacío.
    const html = renderBlocks(doc([blankBlock("divider")]));
    expect(html).toContain(CONTENT_TOKEN);
  });

  it("escapa lo que el autor escribe", () => {
    const texto = {
      ...(blankBlock("text") as TextBlock),
      text: 'Ventas & Post <Venta> "ya"',
    };
    const html = renderBlocks(doc([texto]));
    expect(html).toContain("Ventas &amp; Post &lt;Venta&gt;");
    expect(html).not.toContain("<Venta>");
  });

  it("respeta los saltos de línea sin dejar pasar markup", () => {
    const texto = {
      ...(blankBlock("text") as TextBlock),
      text: "Primera\nsegunda\n\nOtro párrafo",
    };
    const html = renderBlocks(doc([texto]));
    expect(html).toContain("Primera<br>segunda");
    expect((html.match(/<p style/g) || []).length).toBe(2);
  });

  it("descarta un href que no sea http, https o mailto", () => {
    const boton = { ...blankBlock("button"), href: "javascript:alert(1)" } as never;
    const html = renderBlocks(doc([boton]));
    expect(html).not.toContain("javascript:");
  });

  it("acepta mailto, que es legítimo en un correo", () => {
    const boton = { ...blankBlock("button"), href: "mailto:hola@x.com" } as never;
    const html = renderBlocks(doc([boton]));
    expect(html).toContain("mailto:hola@x.com");
  });

  it("una imagen sin src no deja un hueco roto", () => {
    const html = renderBlocks(doc([blankBlock("image"), blankBlock("content")]));
    expect(html).not.toContain("<img");
  });
});

describe("el documento", () => {
  it("se distingue del diseño viejo guardado en la misma columna", () => {
    expect(isBlockDocument(DEFAULT_DOCUMENT)).toBe(true);
    // El diseño plano anterior no tiene `kind`.
    expect(isBlockDocument({ headerColor: "#003366" })).toBe(false);
    expect(isBlockDocument(null)).toBe(false);
  });

  it("el documento por defecto ya es enviable", () => {
    const html = renderBlocks(DEFAULT_DOCUMENT);
    expect(html).toContain(CONTENT_TOKEN);
    expect(DEFAULT_DOCUMENT.blocks.some((b) => b.type === "content")).toBe(true);
  });

  it("cada bloque nuevo nace con un id propio", () => {
    const ids = new Set(
      Array.from({ length: 20 }, () => blankBlock("text").id),
    );
    expect(ids.size).toBe(20);
  });
});
