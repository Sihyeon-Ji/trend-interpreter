import { approvalHandlers } from "@/lib/approval-server";

/** GET: 요청한 사람이 보는 상태(본문 없음) · POST: 관리 화면의 승인·반려(검수자만) — lib/approval-handler.ts */
export const GET = approvalHandlers.state;
export const POST = approvalHandlers.decide;
