import "server-only";
/* 시안 r-flow 의 서버 쪽 읽기 — lib/data.ts 함수만 부른다. 한 요청 안에서 레이아웃과 화면이 같은 값을 쓰도록 react cache 로 묶는다.
   실패하면 null 을 돌려 숫자 칸만 비우고 화면은 연다(예시 데이터로 바꾸지 않는다). */
import { cache } from "react";
import { getKeywordBoard, getReviewStats } from "@/lib/data";
import { MAKE_MARKETS } from "@/lib/reader";
import { getReader, getViewer } from "@/lib/reader-server";

export const getMarketCounts = cache(async (): Promise<Record<string, number> | null> => {
  try {
    return (await getKeywordBoard([...MAKE_MARKETS], 1)).counts;
  } catch {
    return null;
  }
});

/** 사람의 승인을 기다리는 새 말 수(검수 대기) */
export const getQueueCount = cache(async (): Promise<number | null> => {
  try {
    return (await getReviewStats()).needs_review;
  } catch {
    return null;
  }
});

/** 승인 표지에 쓸 이름 — 로그인한 사람의 별명이나 아이디, 익명이면 null */
export const getSignerName = cache(async (): Promise<string | null> => {
  const viewer = await getViewer();
  if (!viewer) return null;
  const reader = await getReader();
  return reader.nick ?? viewer.user;
});
