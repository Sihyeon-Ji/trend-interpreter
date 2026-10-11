// Capture the screens used in the deck (slide 9) and the README from a deployed site.
// Runs inside the e2e image, which has Playwright and Chromium:
//   BASE_URL=https://<web> docker compose run --rm --no-deps -e BASE_URL \
//     -v "$PWD/docs/images:/out" e2e node scripts/capture-screens.mjs
// The address comes from BASE_URL so it never lands in the public repository.
import { chromium } from "@playwright/test";

const base = process.env.BASE_URL;
if (!base) throw new Error("Set BASE_URL to the deployed web address");
const out = process.env.OUT_DIR ?? "/out";
// 1600x1000 PNGs, the size the README uses. English screen; memes stay in their own script. Keep entries that show non-memes off the list.
const pages = [
  ["create", "/"],
  ["explore-en", "/trends?m=GLOBAL"],
  ["entry-en", "/dictionary/t_510cb64124?m=GLOBAL"],
  ["briefing", "/briefing?regions=KR"],
  ["map", "/map"],
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1600 / 1440, locale: "en-US" });
await ctx.addCookies([{ name: "locale", value: "en", url: base }]);
const page = await ctx.newPage();
for (const [name, path] of pages) {
  await page.goto(base + path, { waitUntil: "load", timeout: 90_000 });
  await page.waitForTimeout(6000);
  await page.screenshot({ path: `${out}/${name}.png` });
  console.log("captured", name);
}
await browser.close();
