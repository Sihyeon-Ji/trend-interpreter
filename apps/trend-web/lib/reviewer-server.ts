import "server-only";
import { cache } from "react";
import { apiFetch } from "./api-fetch";
import { getViewer } from "./reader-server";
import { assertReviewer, createReviewerReader } from "./reviewer-access";

// Deduplicate only within a render; never share authorization between requests.
export const requireReviewer = cache(async () => assertReviewer(await getViewer()));
export const reviewerFetch = createReviewerReader(apiFetch, requireReviewer, () => process.env.FRONTEND_API_TOKEN);
