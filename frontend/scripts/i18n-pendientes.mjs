#!/usr/bin/env node
/**
 * F13: lists the frontend files that still have Spanish text written in the
 * code instead of `t("…")`, grouped by area, to measure the sweep.
 *
 *   node scripts/i18n-pendientes.mjs          # summary by area
 *   node scripts/i18n-pendientes.mjs --files  # every file and its count
 *
 * Heuristic, not a parser: it counts lines with Spanish letters (á é í ó ú
 * ñ ¿ ¡) outside comments. False positives (a name, a regex) are fine; the
 * goal is the trend, down to zero.
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const SPANISH = /[áéíóúñ¿¡ÁÉÍÓÚÑ]/;
const SKIP = [/\.test\.tsx?$/, /^lib\/i18n\//, /\.d\.ts$/, /^tests\//, /^scripts\//];

const files = execFileSync("git", ["ls-files", "--", "*.ts", "*.tsx"], { encoding: "utf8" })
  .split("\n")
  .filter(Boolean)
  .filter((f) => !SKIP.some((re) => re.test(f)));

const counts = [];
for (const file of files) {
  let inBlock = false;
  let n = 0;
  for (const raw of readFileSync(file, "utf8").split("\n")) {
    const line = raw.trim();
    if (inBlock) {
      if (line.includes("*/")) inBlock = false;
      continue;
    }
    if (line.startsWith("/*")) {
      inBlock = !line.includes("*/");
      continue;
    }
    if (line.startsWith("//") || line.startsWith("*") || line.startsWith("{/*")) continue;
    if (SPANISH.test(line.replace(/\/\/.*$/, ""))) n += 1;
  }
  if (n) counts.push([file, n]);
}

const area = (f) => {
  const p = f.split("/");
  return p[0] === "app" ? p.slice(0, 3).join("/") : p.slice(0, 2).join("/");
};

if (process.argv.includes("--files")) {
  for (const [f, n] of counts.sort((a, b) => b[1] - a[1])) console.log(`${String(n).padStart(4)}  ${f}`);
} else {
  const byArea = new Map();
  for (const [f, n] of counts) {
    const a = area(f);
    const cur = byArea.get(a) ?? { files: 0, lines: 0 };
    byArea.set(a, { files: cur.files + 1, lines: cur.lines + n });
  }
  for (const [a, { files: fc, lines }] of [...byArea].sort((x, y) => y[1].lines - x[1].lines)) {
    console.log(`${String(lines).padStart(5)} líneas  ${String(fc).padStart(3)} archivos  ${a}`);
  }
}
const total = counts.reduce((s, [, n]) => s + n, 0);
console.log(`\nTotal: ${total} líneas en ${counts.length} archivos.`);
