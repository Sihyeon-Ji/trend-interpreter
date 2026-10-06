import { apiFetch } from "@/lib/api-fetch";
import { getViewer } from "@/lib/reader-server";
import { createBatchDecisionHandler } from "@/lib/publication-decision-handler";

export const POST = createBatchDecisionHandler(getViewer, () => process.env.FRONTEND_API_TOKEN, apiFetch);
