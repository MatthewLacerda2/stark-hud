/**
 * Every colour token the theme declares must survive into the built stylesheet.
 *
 * This exists because the board takes colours over the wire. A session may name
 * one — `set_style(color="chart-3")` — and `backend/schemas/colour.py` turns
 * that into `var(--color-chart-3)`. If the build dropped that variable, the
 * browser resolves it to nothing and paints black, with nothing anywhere saying
 * why. That happened: three gauges came out as dark rings.
 *
 * Checking `styles.css` is not enough, and that is the whole point of this file.
 * The names were all present in the source and 8 of 31 reached the browser,
 * because Tailwind emits only what it sees used. So the gate reads the artefact.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const here = new URL("..", import.meta.url).pathname;
const css = readFileSync(join(here, "src/styles.css"), "utf8");
// From the block itself, not the first mention of it: the file explains `@theme`
// in a comment above it, and splitting on the word read the prose instead. That
// found no tokens and passed, which is this same bug wearing a different hat.
const theme = css.slice(css.search(/@theme[^{]*\{/));
const declared = [...theme.matchAll(/^\s*--color-([a-z0-9-]+):/gm)]
  .map((m) => m[1])
  .filter((name) => name !== "*");

if (declared.length === 0) {
  console.error(
    "Found no colour tokens to check. A gate that reads nothing passes.",
  );
  process.exit(1);
}

const assets = join(here, "dist/assets");
const built = readdirSync(assets)
  .filter((name) => name.endsWith(".css"))
  .map((name) => readFileSync(join(assets, name), "utf8"))
  .join("\n");

const missing = declared.filter((name) => !built.includes(`--color-${name}:`));

if (missing.length > 0) {
  console.error(
    `These colour tokens are declared but never reach the browser:\n` +
      `  ${missing.join(", ")}\n\n` +
      `A name the backend accepts and the build drops resolves to nothing, and ` +
      `the widget paints black. Keep the theme block marked \`static\`.`,
  );
  process.exit(1);
}

console.log(`theme: all ${declared.length} colour tokens reach the browser`);
