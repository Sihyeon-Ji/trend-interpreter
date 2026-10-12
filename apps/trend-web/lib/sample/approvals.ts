/* 예시 데이터 모드의 문구 승인 대기열(관리 화면 /admin/approvals). 묶음은 손으로 정하지 않는다 — 예시 문구를 예시 사전의 규칙 검사
   (sample/copy-check.ts)로 돌려 백엔드와 같은 규칙(lib/approval.ts groupOf)으로 나눈다. 시각은 지금 기준이라 늘 최근 요청처럼 보인다. */
import { copyIssues, fullText, groupOf, type Fit } from "../approval";
import type { ApprovalCopy, ApprovalItem, ApprovalList } from "../types";
import { sampleCopyCheck } from "./copy-check";

const HOUR = 3_600_000;
const ago = (hours: number) => new Date(Date.now() - hours * HOUR).toISOString();

type Draft = { id: string; hours: number; copies: [ApprovalCopy["platform"], string, string[]][]; fit: Fit | null; note?: string;
  by?: string; decided?: { status: "approved" | "rejected"; by: string; hours: number; memo?: string }; expired?: boolean };

const DRAFTS: Draft[] = [
  { id: "sample-read-1", hours: 0.5, fit: "off", note: "문구가 '원영적 사고'를 비꼬는 뜻으로 읽힐 수 있어요.", copies: [
    ["instagram", "비 오는 출근길도 원영적 사고로 버텨요. 여름 한정 아이스 흑당 라떼와 함께", ["여름한정", "흑당라떼"]],
    ["instagram", "더위에 지친 오후, 원영적 사고 한 잔 어때요?", ["원영적사고"]],
    ["x", "원영적 사고로 시작하는 월요일, 흑당 라떼 한 잔", []],
    ["x", "줄이 길어도 원영적 사고. 오늘만 1+1", []]] },
  { id: "sample-read-2", hours: 2, fit: "ok", note: "긍정적으로 받아들이는 뜻 그대로 썼어요.", copies: [
    ["instagram", "원영적 사고로 맞는 여름, 아이스 흑당 라떼 시작했어요", ["여름한정"]],
    ["instagram", "아 샤갈, 벌써 품절이라니. 그래도 원영적 사고!", ["흑당라떼"]],
    ["x", "더워도 원영적 사고. 시원한 한 잔이면 충분", []],
    ["x", "원영적 사고로 고른 오늘의 메뉴", []]] },
  { id: "sample-blocked-1", hours: 5, fit: "ok", note: "자기에게 유리하게 해석하는 뜻 그대로 썼어요.", copies: [
    ["instagram", "원영적 사고로 고른 여름 한정 라떼", ["여름한정"]],
    ["instagram", "오늘도 원영적 사고, 한 모금이면 기분 전환", []],
    ["x", "중티 나는 컵 말고 우리 컵에 담아요. 원영적 사고!", []],
    ["x", "원영적 사고로 버티는 오후 세 시", []]] },
  { id: "sample-clean-1", hours: 26, fit: "ok", note: "긍정적으로 받아들이는 뜻 그대로 썼어요.", by: "marketer02", copies: [
    ["instagram", "원영적 사고로 시작하는 여름, 아이스 흑당 라떼", ["여름한정", "흑당라떼"]],
    ["instagram", "땀 흘린 만큼 시원하게, 이것도 원영적 사고", ["아이스라떼"]],
    ["x", "더운 날엔 원영적 사고. 흑당 라떼가 기다려요", []],
    ["x", "원영적 사고로 고른 여름 메뉴, 이번 주까지", []]] },
  { id: "sample-done-1", hours: 50, fit: "ok", decided: { status: "approved", by: "reviewer", hours: 48 }, copies: [
    ["instagram", "원영적 사고로 맞는 첫 여름 신메뉴", ["신메뉴"]],
    ["x", "오늘도 원영적 사고. 흑당 라떼 나왔어요", []]] },
  { id: "sample-done-2", hours: 74, fit: "ok", decided: { status: "rejected", by: "reviewer", hours: 72, memo: "'중티'는 쓰지 말아 주세요. 다시 써서 요청해 주세요." }, copies: [
    ["instagram", "중티 안 나게 마시는 법, 원영적 사고 라떼", []],
    ["x", "원영적 사고로 버티는 금요일", []]] },
  { id: "sample-done-3", hours: 24 * 33, fit: "ok", expired: true, decided: { status: "approved", by: "reviewer", hours: 24 * 32 }, copies: [
    ["instagram", "", []], ["x", "", []]] },
];

function item(d: Draft): ApprovalItem {
  const checks = d.copies.map(([, text, tags]) => (text ? sampleCopyCheck(fullText({ text, hashtags: tags }), "KR") : null));
  const issues = d.expired ? d.copies.map(() => []) : checks.map((c) => copyIssues(c));
  const { group, reasons } = groupOf(issues, d.fit);
  return {
    approval_id: d.id, market: "KR", term_id: "t_wonyoung", canonical: "원영적 사고", lang: "ko",
    product: d.expired ? null : "여름 한정 아이스 흑당 라떼", fit: d.fit, fit_copy: 0, fit_note: d.expired ? null : d.note ?? null,
    copies: d.copies.map(([platform, text, hashtags], i) => ({ platform, text: d.expired ? null : text, hashtags: d.expired ? [] : hashtags, issues: issues[i] })),
    image_meme: false, group, reasons, status: d.decided?.status ?? "pending", requested_by: d.by ?? "marketer01", requested_at: ago(d.hours),
    decided_by: d.decided?.by ?? null, decided_at: d.decided ? ago(d.decided.hours) : null, memo: d.decided?.memo ?? null, expired: !!d.expired,
  };
}

export function sampleApprovals(): ApprovalList {
  const all = DRAFTS.map(item);
  return { pending: all.filter((a) => a.status === "pending"), history: all.filter((a) => a.status !== "pending") };
}
