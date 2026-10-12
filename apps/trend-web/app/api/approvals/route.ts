import { approvalHandlers } from "@/lib/approval-server";

/** 초안의 '검수 요청'(로그인한 계정)과 검수자의 바로 승인 — 세션·권한 확인과 본문 거르기는 lib/approval-handler.ts */
export const POST = approvalHandlers.create;
