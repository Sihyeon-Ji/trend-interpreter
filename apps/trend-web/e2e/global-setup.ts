import { request } from "@playwright/test";

/* The e2e stack runs the Next.js development server, which compiles each route on its first request. On a slow CI
 * runner that first compile alone outlasted single-test and navigation timeouts (release CI 10-04: /map and a report
 * entry), so every route is requested once before the tests. The tests then measure behaviour, not compile time. */
const ROUTES = [
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
  "/admin",
  "/lab",
  "/lab/t-studio",
  "/lab/f-report",
  "/lab/f-report/api/search",
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
const COMPILE_TIMEOUT_MS = 180_000;

export default async function globalSetup() {
  const context = await request.newContext({ baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000" });
  try {
    for (const route of ROUTES) {
      await context.get(route, { timeout: COMPILE_TIMEOUT_MS, maxRedirects: 0, failOnStatusCode: false });
    }
  } finally {
    await context.dispose();
  }
}
