import { timingSafeEqual } from "node:crypto";
import { z } from "zod";
import { getDataset } from "@/lib/dataset";
import { runBriefingAgent } from "@/lib/agent";
import { filterReports } from "@/lib/selectors";

export const maxDuration = 100;
const requestSchema = z.object({
  filters: z.object({
    search: z.string().max(160),
    disease: z.string().max(80),
    source: z.enum(["all", "who", "cdc", "ecdc", "ukhsa", "kdca"]),
    country: z.string().max(3),
    days: z.union([
      z.literal(30),
      z.literal(90),
      z.literal(180),
      z.literal(365),
    ]),
  }),
  question: z
    .string()
    .max(800)
    .default(
      "Summarize the most important observations, evidence gaps, conditional risk scenarios, and official response options.",
    ),
});
let active = false;
let lastStartedAt = 0;
const MIN_REQUEST_INTERVAL_MS = 10_000;

export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  if (origin) {
    try {
      if (new URL(origin).host !== request.headers.get("host"))
        return Response.json(
          { error: "Cross-origin requests are not allowed." },
          { status: 403 },
        );
    } catch {
      return Response.json(
        { error: "Invalid request origin." },
        { status: 403 },
      );
    }
  }
  const configuredToken = process.env.ANALYSIS_ACCESS_TOKEN;
  if (configuredToken) {
    const supplied = Buffer.from(
      request.headers.get("authorization")?.replace(/^Bearer /, "") ?? "",
    );
    const expected = Buffer.from(configuredToken);
    if (
      supplied.length !== expected.length ||
      !timingSafeEqual(supplied, expected)
    )
      return Response.json(
        { error: "Enter the analysis access token to continue." },
        { status: 401 },
      );
  }
  const reader = request.body?.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  if (reader) {
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 5000) {
          await reader.cancel();
          return Response.json(
            { error: "Request is too large." },
            { status: 413 },
          );
        }
        chunks.push(value);
      }
    } catch {
      return Response.json(
        { error: "Request body could not be read." },
        { status: 400 },
      );
    } finally {
      reader.releaseLock();
    }
  }
  const body = Buffer.concat(chunks).toString("utf8");
  let parsed: z.infer<typeof requestSchema>;
  try {
    parsed = requestSchema.parse(JSON.parse(body));
  } catch {
    return Response.json(
      { error: "Invalid analysis filters or question." },
      { status: 400 },
    );
  }
  if (active || Date.now() - lastStartedAt < MIN_REQUEST_INTERVAL_MS)
    return Response.json(
      {
        error:
          "An analysis is running or just completed. Please retry in a few seconds.",
      },
      { status: 429, headers: { "Retry-After": "10" } },
    );
  active = true;
  lastStartedAt = Date.now();
  try {
    const dataset = await getDataset();
    const reports = filterReports(dataset.reports, parsed.filters);
    if (!reports.length)
      return Response.json(
        {
          error:
            "No matching reports. Broaden your filters before creating a brief.",
        },
        { status: 422 },
      );
    const briefing = await runBriefingAgent(reports, dataset, parsed.question);
    return Response.json(briefing, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      {
        error:
          "Gemini analysis could not be completed. Check the server API key, model access, and quota, then retry. No AI findings were generated.",
      },
      { status: 502 },
    );
  } finally {
    active = false;
  }
}
