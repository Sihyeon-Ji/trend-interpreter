import type { Metadata } from "next";
import { Frame } from "@/components/lab/r-flow/frame";
import { getMarketCounts, getQueueCount, getSignerName } from "@/components/lab/r-flow/server";
import { getLocale } from "@/lib/locale";
import "./r-flow.css";

/* 시안 r-flow — '작업 공간'. 앱의 틀 대신 이 시안이 제 틀(옆 메뉴·찾기·패널)을 그린다. 문서: docs/디자인-시안/r-flow.md
   panel 칸은 밈 자세히(@panel/(.)term) — 목록이나 초안 위에 옆 패널로 열려 보던 자리를 지킨다. */
export const metadata: Metadata = { title: { default: "Trend Interpreter", template: "%s | Trend Interpreter" } };

export default async function RFlowLayout({ children, panel }: { children: React.ReactNode; panel: React.ReactNode }) {
  const [locale, signer] = await Promise.all([getLocale(), getSignerName()]);
  // 숫자는 기다리지 않고 약속으로 넘긴다 — 틀은 먼저 그리고 숫자는 도착하면 채운다
  return (
    <div className="lab-r-flow">
      <Frame locale={locale} counts={getMarketCounts()} queue={getQueueCount()} signer={signer}>{children}</Frame>
      {panel}
    </div>
  );
}
