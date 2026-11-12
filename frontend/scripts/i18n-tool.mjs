#!/usr/bin/env node
/**
 * F13 sweep helper. Three commands:
 *
 *   apply <mapping.txt>
 *     Each line: `path:line section.key[.sub] [!] [~fragment]`. With `!` the
 *     literal becomes the key itself, for module-level maps whose users then
 *     call `t(item.label)`. Otherwise replaces the text
 *     on that line (JSX text, a text attribute or a string literal; the one
 *     containing `fragment` when there are several) with `t("key")`, adds
 *     `const t = useT();` (or `await getT()` in a server component) to the
 *     enclosing component or hook, and writes the original Spanish text to
 *     `lib/i18n/messages/es/<section>.ts`. Lines starting with `#` are
 *     ignored. A line `= path:line section.key Texto con {valor}` only adds
 *     the Spanish text (for templates edited by hand).
 *
 *   dump <section>
 *     Prints the Spanish section as `key=text` lines, the input to `put`.
 *
 *   put <lang> <section> <file.txt>
 *     Reads `key=text` lines and writes `messages/<lang>/<section>.ts`,
 *     registering the section in that language's index.
 *
 * A text that needs a helper outside a component (a module-level map, a
 * plain function) is left for the type checker to point out: store the key
 * there and call `t()` in the component, as PLAN.i18n.md explains.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import ts from "typescript";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const MSG = join(ROOT, "lib/i18n/messages");
const LANGS = ["es", "en", "pt", "fr", "de", "ja", "ko"];

// ---------------------------------------------------------------- dictionaries
async function loadSection(lang, section) {
  const file = join(MSG, lang, `${section}.ts`);
  if (!existsSync(file)) return {};
  const out = ts.transpileModule(readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const url = `data:text/javascript;base64,${Buffer.from(out).toString("base64")}`;
  const mod = await import(url);
  return mod[section] ?? {};
}

function flatten(obj, prefix = "") {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "string" ? [[`${prefix}${k}`, v]] : flatten(v, `${prefix}${k}.`),
  );
}

function nest(pairs) {
  const root = {};
  for (const [key, value] of pairs) {
    const parts = key.split(".");
    let node = root;
    for (const p of parts.slice(0, -1)) node = node[p] ??= {};
    node[parts.at(-1)] = value;
  }
  return root;
}

const IDENT = /^[A-Za-z_$][\w$]*$/;
function render(obj, indent = "  ") {
  const lines = ["{"];
  for (const [k, v] of Object.entries(obj)) {
    const key = IDENT.test(k) ? k : JSON.stringify(k);
    lines.push(
      typeof v === "string"
        ? `${indent}${key}: ${JSON.stringify(v)},`
        : `${indent}${key}: ${render(v, indent + "  ")},`,
    );
  }
  lines.push(`${indent.slice(2)}}`);
  return lines.join("\n");
}

function register(lang, section) {
  const file = join(MSG, lang, "index.ts");
  let src = readFileSync(file, "utf8").replace(/\r\n/g, "\n");
  if (src.includes(`from "./${section}"`)) return;
  src = src.replace(
    /(import \{ core \} from "\.\/core";\n)/,
    `$1import { ${section} } from "./${section}";\n`,
  );
  src = src.replace(/(\n {2}\.\.\.core,\n)/, `$1  ${section},\n`);
  writeFileSync(file, src);
}

function writeSection(lang, section, obj) {
  const header =
    lang === "es"
      ? ""
      : `import type { ${section} as es } from "../es/${section}";\nimport type { Strings } from "../types";\n\n`;
  const type = lang === "es" ? "" : `: Strings<typeof es>`;
  writeFileSync(
    join(MSG, lang, `${section}.ts`),
    `${header}export const ${section}${type} = ${render(obj)};\n`,
  );
  register(lang, section);
}

// ---------------------------------------------------------------- code edits
function enclosingComponent(node) {
  for (let n = node.parent; n; n = n.parent) {
    let name = "";
    if (ts.isFunctionDeclaration(n) && n.name) name = n.name.text;
    else if ((ts.isArrowFunction(n) || ts.isFunctionExpression(n)) && n.parent) {
      const p = n.parent;
      if (ts.isVariableDeclaration(p) && ts.isIdentifier(p.name)) name = p.name.text;
      else if (ts.isCallExpression(p)) {
        // forwardRef(function X() {}) / memo(() => ...)
        const d = p.parent;
        if (d && ts.isVariableDeclaration(d) && ts.isIdentifier(d.name)) name = d.name.text;
      }
    } else continue;
    if (/^[A-Z]/.test(name) || /^use[A-Z]/.test(name)) return n;
  }
  return null;
}

function nodesOnLine(sf, line) {
  const found = [];
  const visit = (node) => {
    const start = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
    const end = sf.getLineAndCharacterOfPosition(node.getEnd()).line + 1;
    if (end < line || start > line) return;
    if (start === line) {
      if (ts.isJsxText(node) && node.getText(sf).trim()) found.push({ kind: "jsx", node });
      else if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer))
        found.push({ kind: "attr", node });
      else if (
        (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
        !(node.parent && ts.isJsxAttribute(node.parent))
      )
        found.push({ kind: "str", node });
    } else if (ts.isJsxText(node) && node.getText(sf).trim()) {
      // JSX text spanning lines: match on the line where its words are.
      const text = node.getText(sf);
      const firstWord = text.search(/\S/);
      const wordLine = sf.getLineAndCharacterOfPosition(node.getStart(sf) + firstWord).line + 1;
      if (wordLine === line) found.push({ kind: "jsx", node });
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return found;
}

/** A literal that reads as text, not a value, class list or key. */
function looksLikeText(s) {
  const v = s.trim();
  if (!v) return false;
  if (/[áéíóúñ¿¡ÁÉÍÓÚÑ…]/.test(v)) return true;
  if (/^[a-z0-9_.:/#?=&-]+$/.test(v)) return false;
  const tokens = v.split(/\s+/);
  if (tokens.every((x) => /^[a-z0-9:[\]/.%#!_-]+$/.test(x)) && tokens.some((x) => /[-:]/.test(x))) return false;
  return /[A-Za-z]{2}/.test(v);
}

function textOf(sf, hit) {
  if (hit.kind === "jsx") return hit.node.getText(sf).trim().replace(/\s+/g, " ");
  if (hit.kind === "attr") return hit.node.initializer.text;
  return hit.node.text;
}

async function apply(mappingFile) {
  const lines = readFileSync(mappingFile, "utf8").split(/\r?\n/);
  const byFile = new Map();
  const esTexts = new Map(); // section -> [[key, text]]
  const addText = (fullKey, text) => {
    const [section, ...rest] = fullKey.split(".");
    if (!esTexts.has(section)) esTexts.set(section, []);
    esTexts.get(section).push([rest.join("."), text]);
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.startsWith("= ")) {
      const m = line.match(/^= (\S+?):(\d+) (\S+) (.+)$/);
      if (!m) throw new Error(`bad text line: ${line}`);
      addText(m[3], m[4]);
      continue;
    }
    const m = line.match(/^(\S+?):(\d+) (\S+)( !)?(?: ~(.+))?$/);
    if (!m) throw new Error(`bad mapping line: ${line}`);
    const [, file, ln, key, bang, fragment] = m;
    if (!byFile.has(file)) byFile.set(file, []);
    byFile.get(file).push({ line: Number(ln), key, fragment, asKey: Boolean(bang) });
  }

  const pending = [];
  for (const [file, items] of byFile) {
    const path = join(ROOT, file);
    const original = readFileSync(path, "utf8");
    const crlf = original.includes("\r\n");
    const src = original.replace(/\r\n/g, "\n");
    const sf = ts.createSourceFile(path, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const isClient = /^\s*["']use client["']/.test(src);
    const edits = [];
    const hosts = new Map();
    const used = new Set();
    for (const item of items) {
      const hits = nodesOnLine(sf, item.line).filter(
        (h) =>
          !used.has(h.node) &&
          (item.fragment
            ? textOf(sf, h).includes(item.fragment)
            : looksLikeText(textOf(sf, h))),
      );
      if (!hits.length) throw new Error(`${file}:${item.line} nothing to replace for ${item.key}`);
      const hit = hits[0];
      used.add(hit.node);
      const text = textOf(sf, hit);
      addText(item.key, text);
      if (item.asKey) {
        if (hit.kind !== "str") throw new Error(`${file}:${item.line} ! needs a string literal`);
        edits.push({ start: hit.node.getStart(sf), end: hit.node.getEnd(), text: JSON.stringify(item.key) });
        continue;
      }
      const call = `t(${JSON.stringify(item.key)})`;
      if (hit.kind === "jsx") {
        const full = hit.node.getText(sf);
        const lead = full.match(/^\s*/)[0];
        const trail = full.match(/\s*$/)[0];
        edits.push({ start: hit.node.getStart(sf), end: hit.node.getEnd(), text: `${lead}{${call}}${trail}` });
      } else if (hit.kind === "attr") {
        const init = hit.node.initializer;
        edits.push({ start: init.getStart(sf), end: init.getEnd(), text: `{${call}}` });
      } else {
        edits.push({ start: hit.node.getStart(sf), end: hit.node.getEnd(), text: call });
      }
      const host = enclosingComponent(hit.node);
      if (host && host.body && ts.isBlock(host.body)) hosts.set(host.body.getStart(sf), host);
    }
    for (const [pos, host] of hosts) {
      const bodyText = host.body.getText(sf);
      if (/\bconst t = (await getT\(\)|useT\(\));/.test(bodyText)) continue;
      const isAsync = host.modifiers?.some((m) => m.kind === ts.SyntaxKind.AsyncKeyword);
      // A server component can't use hooks: it awaits getT(), so it must be
      // async (Next allows async server components).
      // Only route files under app/ can be server components; a shared
      // component without the directive renders on the client when a
      // client component imports it.
      const server = !isClient && file.startsWith("app/") && ts.isFunctionDeclaration(host);
      if (server && !isAsync) {
        const at = host.getStart(sf) + host.getText(sf).indexOf("function");
        edits.push({ start: at, end: at, text: "async " });
      }
      const stmt = server ? "const t = await getT();" : "const t = useT();";
      edits.push({ start: pos + 1, end: pos + 1, text: `\n  ${stmt}` });
    }
    edits.sort((a, b) => b.start - a.start);
    let out = src;
    for (const e of edits) out = out.slice(0, e.start) + e.text + out.slice(e.end);
    const needsClient = out.includes("useT()") && !/import \{[^}]*\buseT\b[^}]*\} from "@\/lib\/i18n\/provider"/.test(out);
    const needsServer = out.includes("await getT()") && !/\bgetT\b[^;]*from "@\/lib\/i18n\/server"/.test(out);
    const imports = [];
    if (needsClient) imports.push(`import { useT } from "@/lib/i18n/provider";`);
    if (needsServer) imports.push(`import { getT } from "@/lib/i18n/server";`);
    if (imports.length) {
      const last = [...out.matchAll(/^import [^;]+;$/gms)].at(-1);
      const at = last ? last.index + last[0].length : 0;
      out = out.slice(0, at) + "\n" + imports.join("\n") + out.slice(at);
    }
    pending.push([path, crlf ? out.replace(/\n/g, "\r\n") : out, `${file} (${items.length})`]);
  }
  // All or nothing: a bad line above throws before any file is touched.
  for (const [path, out, label] of pending) {
    writeFileSync(path, out);
    console.log(`edited ${label}`);
  }

  // Keys of the hand-written core (common.loading, nav.home…) are reused,
  // never written again.
  const coreSections = Object.keys(await loadSection("es", "core"));
  for (const [section, pairs] of esTexts) {
    if (coreSections.includes(section)) continue;
    const current = flatten(await loadSection("es", section));
    const merged = new Map(current);
    for (const [k, v] of pairs) {
      if (merged.has(k) && merged.get(k) !== v) {
        console.warn(`! ${section}.${k}: kept "${merged.get(k)}", ignored "${v}"`);
        continue;
      }
      merged.set(k, v);
    }
    writeSection("es", section, nest([...merged]));
    console.log(`es/${section}.ts: ${merged.size} texts`);
  }
}

async function dump(section) {
  for (const [k, v] of flatten(await loadSection("es", section))) console.log(`${k}=${v}`);
}

async function put(lang, section, file) {
  if (!LANGS.includes(lang)) throw new Error(`unknown language ${lang}`);
  const pairs = readFileSync(file, "utf8")
    .split(/\r?\n/)
    .filter((l) => l.trim() && !l.startsWith("#"))
    .map((l) => {
      const i = l.indexOf("=");
      if (i < 1) throw new Error(`bad line: ${l}`);
      return [l.slice(0, i).trim(), l.slice(i + 1)];
    });
  const source = flatten(await loadSection("es", section));
  const have = new Set(pairs.map(([k]) => k));
  const missing = source.filter(([k]) => !have.has(k)).map(([k]) => k);
  const extra = pairs.filter(([k]) => !source.some(([s]) => s === k)).map(([k]) => k);
  if (missing.length || extra.length) {
    throw new Error(`${lang}/${section}: missing [${missing.join(", ")}] extra [${extra.join(", ")}]`);
  }
  // Same key order as the Spanish source.
  const map = new Map(pairs);
  writeSection(lang, section, nest(source.map(([k]) => [k, map.get(k)])));
  console.log(`${lang}/${section}.ts: ${pairs.length} texts`);
}

/**
 * `ensure <file>...`: every component or hook that calls `t(` without
 * declaring it (a `const t`, a parameter named `t`) gets `const t = useT();`
 * (`await getT()` in a server file), plus the import.
 */
function ensure(files) {
  for (const file of files) {
    const path = join(ROOT, file);
    const original = readFileSync(path, "utf8");
    const crlf = original.includes("\r\n");
    const src = original.replace(/\r\n/g, "\n");
    const sf = ts.createSourceFile(path, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const isClient = /^\s*["']use client["']/.test(src);
    const edits = [];
    const visit = (node) => {
      let name = "";
      if (ts.isFunctionDeclaration(node) && node.name) name = node.name.text;
      else if ((ts.isArrowFunction(node) || ts.isFunctionExpression(node)) && node.parent && ts.isVariableDeclaration(node.parent) && ts.isIdentifier(node.parent.name)) name = node.parent.name.text;
      const isHost = (/^[A-Z]/.test(name) || /^use[A-Z]/.test(name)) && node.body && ts.isBlock(node.body);
      if (isHost) {
        const body = node.body.getText(sf);
        const hasParamT = node.parameters.some((p) => ts.isIdentifier(p.name) && p.name.text === "t");
        if (/(^|[^\w.])t\(/.test(body) && !/\bconst t = /.test(body) && !hasParamT) {
          const isAsync = node.modifiers?.some((m) => m.kind === ts.SyntaxKind.AsyncKeyword);
          const server = !isClient && file.startsWith("app/") && ts.isFunctionDeclaration(node);
          if (server && !isAsync) {
            const at = node.getStart(sf) + node.getText(sf).indexOf("function");
            edits.push({ at, text: "async " });
          }
          edits.push({ at: node.body.getStart(sf) + 1, text: `\n  const t = ${server ? "await getT()" : "useT()"};` });
        }
        return; // nested functions use the host's t
      }
      ts.forEachChild(node, visit);
    };
    visit(sf);
    if (!edits.length) continue;
    edits.sort((a, b) => b.at - a.at);
    let out = src;
    for (const e of edits) out = out.slice(0, e.at) + e.text + out.slice(e.at);
    if (out.includes("useT()") && !/\buseT\b[^;]*from "@\/lib\/i18n\/provider"/.test(out)) {
      const last = [...out.matchAll(/^import [^;]+;$/gms)].at(-1);
      const at = last ? last.index + last[0].length : 0;
      out = out.slice(0, at) + `\nimport { useT } from "@/lib/i18n/provider";` + out.slice(at);
    }
    if (out.includes("await getT()") && !/\bgetT\b[^;]*from "@\/lib\/i18n\/server"/.test(out)) {
      const last = [...out.matchAll(/^import [^;]+;$/gms)].at(-1);
      const at = last ? last.index + last[0].length : 0;
      out = out.slice(0, at) + `\nimport { getT } from "@/lib/i18n/server";` + out.slice(at);
    }
    writeFileSync(path, crlf ? out.replace(/\n/g, "\r\n") : out);
    console.log(`ensured ${file} (${edits.length})`);
  }
}

/** `putall <lang> <file>`: like `put`, for a file with `### section`
 *  headers, one block per section. Sections are merged with what the
 *  language already has, so a block can add just the new keys. */
async function putAll(lang, file) {
  const blocks = new Map();
  let current = null;
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const h = line.match(/^### (\w+)/);
    if (h) {
      current = h[1];
      blocks.set(current, []);
    } else if (current && line.trim()) blocks.get(current).push(line);
  }
  for (const [section, lines] of blocks) {
    const existing = flatten(await loadSection(lang, section));
    const given = new Map(existing);
    for (const l of lines) {
      const i = l.indexOf("=");
      if (i < 1) throw new Error(`bad line in ${section}: ${l}`);
      given.set(l.slice(0, i).trim(), l.slice(i + 1));
    }
    const tmp = join(ROOT, `.i18n-${lang}-${section}.tmp`);
    const source = new Set(flatten(await loadSection("es", section)).map(([k]) => k));
    writeFileSync(
      tmp,
      [...given]
        .filter(([k]) => source.has(k))
        .map(([k, v]) => `${k}=${v}`)
        .join("\n"),
    );
    try {
      await put(lang, section, tmp);
    } finally {
      (await import("node:fs")).rmSync(tmp, { force: true });
    }
  }
}

const [cmd, ...rest] = process.argv.slice(2);
if (cmd === "putall") await putAll(rest[0], rest[1]);
else if (cmd === "ensure") ensure(rest);
else if (cmd === "apply") await apply(rest[0]);
else if (cmd === "dump") await dump(rest[0]);
else if (cmd === "put") await put(rest[0], rest[1], rest[2]);
else {
  console.error("usage: apply <mapping> | dump <section> | put <lang> <section> <file>");
  process.exit(1);
}
void pathToFileURL;
