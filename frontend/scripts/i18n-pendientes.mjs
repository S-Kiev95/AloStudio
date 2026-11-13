#!/usr/bin/env node
/**
 * F13: lists the user-facing text still written in the code instead of
 * `t("…")`, to drive and measure the translation sweep.
 *
 *   node scripts/i18n-pendientes.mjs               # summary by area
 *   node scripts/i18n-pendientes.mjs --files       # count per file
 *   node scripts/i18n-pendientes.mjs <path>...     # every text, file:line
 *
 * Reads the TypeScript AST: JSX text, the text attributes (aria-label,
 * title, placeholder, alt, label…) and string literals that read like a
 * phrase (letters and a space, or Spanish accents). Skips class names,
 * imports, object keys, test files and the dictionaries. A heuristic: a
 * stray false positive is fine, the goal is to drive the count to zero.
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

import ts from "typescript";

const SKIP_FILES = [
  /\.test\.tsx?$/,
  /^lib\/i18n\//,
  /\.d\.ts$/,
  /^tests\//,
  /^scripts\//,
  /^(lib|components)\/legal\//, // legal texts stay in Spanish until reviewed (PLAN.i18n.md)
  /^app\/(privacidad|terminos|eliminacion-de-datos)\//,
  /^app\/api\//, // server routes: messages for logs and the backend
  /^middleware\.ts$/,
  /\.config\.ts$/,
  /^lib\/api\/generated\//,
];
const TEXT_ATTRS = new Set([
  "aria-label",
  "aria-description",
  "title",
  "placeholder",
  "alt",
  "label",
  "description",
  "emptyText",
  "confirmLabel",
  "cancelLabel",
]);
const NON_TEXT_CALLS = new Set([
  "cn",
  "clsx",
  "twMerge",
  "cva",
  "require",
  "querySelector",
  "querySelectorAll",
  "getItem",
  "setItem",
  "removeItem",
  "startsWith",
  "endsWith",
  "includes",
  "split",
  "replace",
  "join",
  "matchMedia",
  "addEventListener",
  "removeEventListener",
  "createElement",
  "getAttribute",
  "setAttribute",
  "t",
  "getT",
  "apiFetch",
  "fetch",
  "invalidateQueries",
  "log",
  "warn",
  "error",
  "useQuery",
]);
const SPANISH = /[áéíóúñ¿¡ÁÉÍÓÚÑ]/;

function looksLikeText(s) {
  const v = s.trim();
  if (v.length < 2) return false;
  if (SPANISH.test(v)) return true;
  if (/^[a-z0-9_.:/#?=&-]+$/.test(v)) return false; // keys, slugs, paths
  if (/^(https?:|\/|#|\.|@|mailto:|data:|var\(|rgb|hsl)/.test(v)) return false;
  if (/^[A-Z0-9_]+$/.test(v)) return false; // CONSTANTS
  if (/[{}<>;=]|=>/.test(v)) return false; // code
  if (!/[a-zA-Z]{2}/.test(v)) return false;
  const tokens = v.split(/\s+/);
  // Tailwind classes: all lowercase tokens, some with - or :.
  if (tokens.every((x) => /^[a-z0-9:[\]/.%#!_-]+$/.test(x)) && tokens.some((x) => /[-:]/.test(x))) return false;
  // SVG paths and other numeric soup.
  if ((v.match(/\d/g) ?? []).length > (v.match(/[a-zA-Z]/g) ?? []).length) return false;
  // CSS functions: color-mix(…), url(…), translate(…).
  if (/^[a-z-]+\(/.test(v)) return false;
  // A phrase: two words, or one capitalised word (a label like "Guardar").
  return /\s/.test(v) || /^[A-ZÁÉÍÓÚÑ¿¡][a-záéíóúñ]+[.…:!?]?$/.test(v);
}

function calleeName(node) {
  const e = node.expression;
  if (ts.isIdentifier(e)) return e.text;
  if (ts.isPropertyAccessExpression(e)) return e.name.text;
  return "";
}

function scan(file) {
  const src = readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const hits = [];
  // `// i18n-ignore` skips its line; `// i18n-ignore-start` … `-end` a
  // block. For text that stays as is on purpose (brand names, the Spanish
  // branch of a formatter).
  const ignored = new Set();
  let inIgnore = false;
  src.split("\n").forEach((l, i) => {
    if (l.includes("i18n-ignore-start")) inIgnore = true;
    if (inIgnore || l.includes("i18n-ignore")) ignored.add(i + 1);
    if (l.includes("i18n-ignore-end")) inIgnore = false;
  });
  const add = (node, text) => {
    const { line } = sf.getLineAndCharacterOfPosition(node.getStart());
    if (ignored.has(line + 1)) return;
    hits.push({ line: line + 1, text: text.trim().replace(/\s+/g, " ") });
  };

  const visit = (node, ctx) => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return;
    if (ts.isJsxAttribute(node)) {
      const name = node.name.getText(sf);
      if (name === "className" || name === "key" || name.startsWith("data-") || name === "href" || name === "src" || name === "id" || name === "htmlFor" || name === "type" || name === "role" || name === "name" || name === "value" || name === "variant" || name === "size" || name === "autoComplete" || name === "accept" || name === "lang") return;
      const init = node.initializer;
      if (init && ts.isStringLiteral(init) && TEXT_ATTRS.has(name) && looksLikeText(init.text)) {
        add(init, init.text);
        return;
      }
    }
    if (ts.isJsxText(node)) {
      const v = node.getText(sf).trim();
      if (v && /[a-zA-ZáéíóúñÁÉÍÓÚÑ]{2}/.test(v)) add(node, v);
      return;
    }
    if (ts.isCallExpression(node) && NON_TEXT_CALLS.has(calleeName(node))) return;
    if (ts.isPropertyAssignment(node) && ts.isIdentifier(node.name)) {
      const k = node.name.text;
      if (k === "className" || k === "queryKey" || k === "method" || k === "href" || k === "segment" || k === "key" || k === "path" || k === "id") return;
    }
    if (ts.isCaseClause(node)) {
      // `case "foo":` labels are values, not text; their bodies still count.
      node.statements.forEach((s) => visit(s, ctx));
      return;
    }
    if (ts.isBinaryExpression(node) && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken, ts.SyntaxKind.EqualsEqualsToken].includes(node.operatorToken.kind)) return;
    if (ts.isElementAccessExpression(node)) return;
    if (ts.isExpressionStatement(node) && ts.isStringLiteral(node.expression)) return; // "use client"
    if (ts.isBinaryExpression(node) && ts.isPropertyAccessExpression(node.left) && node.left.name.text === "displayName") return;
    if (ts.isTypeNode(node) || ts.isTypeAliasDeclaration(node) || ts.isInterfaceDeclaration(node)) return;
    if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node))) {
      const parent = node.parent;
      const isKey = parent && ts.isPropertyAssignment(parent) && parent.name === node;
      if (!isKey && looksLikeText(node.text)) add(node, node.text);
      return;
    }
    if (ts.isTemplateExpression(node)) {
      const raw = node.getText(sf).slice(1, -1);
      const plain = raw.replace(/\$\{[^}]*\}/g, " ");
      if (looksLikeText(plain) && /[a-zA-Z]{3}/.test(plain.replace(/\s+/g, ""))) add(node, raw);
    }
    ts.forEachChild(node, (c) => visit(c, ctx));
  };
  visit(sf, {});
  return hits;
}

const args = process.argv.slice(2).filter((a) => !a.startsWith("--"));
const listed = execFileSync("git", ["ls-files", "--others", "--cached", "--exclude-standard", "--", "*.ts", "*.tsx"], { encoding: "utf8" })
  .split("\n")
  .filter(Boolean)
  .filter((f) => !SKIP_FILES.some((re) => re.test(f)));
const files = args.length ? listed.filter((f) => args.some((a) => f.startsWith(a))) : listed;

const results = files.map((f) => [f, scan(f)]).filter(([, h]) => h.length);

if (args.length) {
  for (const [f, hits] of results) for (const h of hits) console.log(`${f}:${h.line}  ${h.text}`);
} else if (process.argv.includes("--files")) {
  for (const [f, h] of results.sort((a, b) => b[1].length - a[1].length)) console.log(`${String(h.length).padStart(4)}  ${f}`);
} else {
  const area = (f) => {
    const p = f.split("/");
    return p[0] === "app" ? p.slice(0, 3).join("/") : p.slice(0, 2).join("/");
  };
  const byArea = new Map();
  for (const [f, h] of results) {
    const a = area(f);
    const cur = byArea.get(a) ?? { files: 0, texts: 0 };
    byArea.set(a, { files: cur.files + 1, texts: cur.texts + h.length });
  }
  for (const [a, { files: fc, texts }] of [...byArea].sort((x, y) => y[1].texts - x[1].texts)) {
    console.log(`${String(texts).padStart(5)} textos  ${String(fc).padStart(3)} archivos  ${a}`);
  }
}
const total = results.reduce((s, [, h]) => s + h.length, 0);
console.log(`\nTotal: ${total} textos en ${results.length} archivos.`);
