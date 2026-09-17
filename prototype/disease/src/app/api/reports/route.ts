import { getDataset, CACHE_TTL_MS } from "@/lib/dataset";

export const dynamic = "force-dynamic";

export async function GET() {
  const dataset = await getDataset();
  return Response.json(
    {
      ...dataset,
      aiEnabled: Boolean(process.env.GEMINI_API_KEY),
      accessTokenRequired: Boolean(process.env.ANALYSIS_ACCESS_TOKEN),
      refreshIntervalMs: CACHE_TTL_MS,
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
