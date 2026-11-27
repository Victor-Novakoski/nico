import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(__dirname, "index.css"), "utf8");

// Blocos de tema: `:root` ou `[data-theme="..."]` (pode vir em lista, separados por virgula).
function parseThemes(source: string): Map<string, Record<string, string>> {
  const themes = new Map<string, Record<string, string>>();
  const re =
    /((?::root|\[data-theme="[\w-]+"\])(?:\s*,\s*(?::root|\[data-theme="[\w-]+"\]))*)\s*\{([^}]*)\}/g;
  for (const m of source.matchAll(re)) {
    const vars: Record<string, string> = {};
    for (const v of m[2].matchAll(/(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;/g)) {
      vars[v[1]] = v[2];
    }
    const selectors = m[1].split(",").map((s) => s.trim());
    const name =
      selectors
        .map((s) => /data-theme="([\w-]+)"/.exec(s)?.[1])
        .find(Boolean) ?? "root";
    themes.set(name, { ...themes.get(name), ...vars });
  }
  return themes;
}

function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT_VARS = [
  "--text",
  "--muted",
  "--valor",
  "--oque",
  "--meio",
  "--parcelas",
  "--entrada",
  "--aviso",
];
const BACKGROUNDS = ["--bg", "--surface"];

describe("temas", () => {
  const themes = parseThemes(css);

  it("tem o tema noturno", () => {
    expect(themes.has("noturno")).toBe(true);
  });

  for (const [name, vars] of themes) {
    describe(`tema ${name}`, () => {
      for (const fg of TEXT_VARS) {
        for (const bg of BACKGROUNDS) {
          it(`${fg} sobre ${bg} tem contraste de pelo menos 4,5:1`, () => {
            expect(vars[fg], `${fg} definido`).toBeDefined();
            expect(vars[bg], `${bg} definido`).toBeDefined();
            expect(contrast(vars[fg], vars[bg])).toBeGreaterThanOrEqual(4.5);
          });
        }
      }
    });
  }
});
