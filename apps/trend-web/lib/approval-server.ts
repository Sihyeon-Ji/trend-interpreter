import "server-only";
import { apiFetch } from "./api-fetch";
import { createApprovalHandlers } from "./approval-handler";
import { isSampleMode } from "./data";
import { getViewer } from "./reader-server";
import { sampleCopyCheck } from "./sample/copy-check";

/* 문구 승인 라우트가 쓰는 실제 의존성 — 세션은 서명된 쿠키에서, 토큰은 서버 환경변수에서만 */
export const approvalHandlers = createApprovalHandlers({
  viewer: getViewer,
  token: () => process.env.FRONTEND_API_TOKEN,
  fetcher: apiFetch,
  sample: isSampleMode,
  sampleCheck: sampleCopyCheck,
});
