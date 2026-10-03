import { chromium, request } from "@playwright/test";

/* The e2e stack runs the Next.js development server, which compiles each route on its first request: the server
 * component, the client bundle the browser loads, and every route handler. On a slow CI runner those first compiles
 * outlasted test and assertion timeouts (release CI 10-04: map, report entry, dashboard chips, drafting), so every page
 * is opened once in a browser and every route handler is requested once before the tests. The tests then measure
 * behaviour, not compile time. */
const PAGES = [
  "/",
  "/map",
  "/map?tab=topics",
  "/briefing",
  "/dictionary",
  "/dictionary/t_oshikatsu",
  "/explain",
  "/recommend",
  "/check",
  "/trends",
  "/updates",
  "/graph",
  "/country/KR",
  "/login",
  "/me",
  "/lab",
  "/lab/t-studio",
  "/lab/f-report",
  "/lab/f-report/m/t_oshikatsu",
  "/lab/f-editorial",
  "/lab/f-editorial/m/t_oshikatsu",
  "/lab/o-report",
  "/lab/o-report/search",
  "/lab/o-report/m/t_oshikatsu",
  "/lab/o-editorial",
  "/lab/o-editorial/search",
  "/lab/o-editorial/m/t_oshikatsu",
];
// A GET compiles a POST-only handler too; the 405 that follows is expected. The report watch stream is left out.
const HANDLERS = [
  "/api/auth/login",
  "/api/chat",
  "/api/copy-check",
  "/api/explain",
  "/api/generate",
  "/api/prefs",
  "/api/recommend",
  "/api/review/t_oshikatsu",
  "/api/review/t_oshikatsu/risk",
  "/lab/f-report/api/search",
  "/lab/f-report/api/term/t_oshikatsu",
  "/lab/o-editorial/api/cards",
  "/lab/o-editorial/api/index",
  "/lab/o-report/api/index",
  "/lab/o-report/api/preview/t_oshikatsu",
  "/lab/t-studio/proto",
];
const COMPILE_TIMEOUT_MS = 180_000;

export default async function globalSetup() {
  const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
  const api = await request.newContext({ baseURL });
  try {
    for (const path of HANDLERS) {
      await api.get(path, { timeout: COMPILE_TIMEOUT_MS, maxRedirects: 0, failOnStatusCode: false });
    }
  } finally {
    await api.dispose();
  }
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ baseURL });
    for (const path of PAGES) {
      await page.goto(path, { timeout: COMPILE_TIMEOUT_MS, waitUntil: "load" });
    }
  } finally {
    await browser.close();
  }
}
