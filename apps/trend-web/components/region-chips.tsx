"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { t, type Locale } from "@/lib/i18n";
import { regionLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import { chipClass } from "@/lib/ui";
import { cn } from "@/lib/utils";

/** 지역 고르기 — 하나만 고른다(누르면 바뀐다). 고른 값은 주소(?regions=)에만 둔다 — 익명은 설정을 갖지 않는다(AGENTS.md).
 *  여러 나라 비교는 세계 지도의 비교표가 맡는다. current 가 null 이면 '전체'. counts 가 없으면(불러오기 실패) 건수를 내지 않는다.
 *  순서: 전체 → 목표 지역 → 세로 선 → 글로벌(목표 지역 밖에서도 널리 쓰이는 말). */
export function RegionChips({ current, counts, locale, list }: { current: string | null; counts?: Record<string, number>; locale: Locale; list?: string }) {
  // 지역을 바꿔도 보던 탭(목록)은 그대로, 쪽은 처음으로
  const href = (r: string | null) => `/?regions=${r ?? "all"}${list ? `&list=${list}` : ""}`;
  const nav = useRef<HTMLElement>(null);
  // 휴대폰은 한 줄 가로 밀기 — 고른 칩이 화면 밖에 있으면 보이게 민다(세로로는 움직이지 않는다)
  useEffect(() => {
    const el = nav.current, on = el?.querySelector<HTMLElement>("[aria-current='true']");
    if (el && on && el.scrollWidth > el.clientWidth) el.scrollLeft = Math.max(0, on.offsetLeft - el.offsetLeft - 16);
  }, [current]);
  const chip = (r: string | null, label: string) => {
    const on = r === current, n = counts?.[r ?? "ALL"];
    return (
      <Link key={r ?? "ALL"} href={href(r)} className={cn(chipClass(on), !on && n === 0 && "text-steel")} aria-current={on ? "true" : undefined}>
        {label}{n != null && <> <span className="tabular-nums">{n}</span></>}
      </Link>
    );
  };
  return (
    <div className="flex items-start gap-3">
      <span className="hidden h-8 shrink-0 items-center text-[13px] font-medium text-steel sm:flex">{t(locale, "dash_regions")}</span>
      <nav ref={nav} aria-label={t(locale, "dash_regions")}
        className="-mx-4 flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
        {chip(null, t(locale, "dash_all"))}
        {TARGET_REGIONS.map((r) => chip(r, regionLabel(locale, r)))}
        <span aria-hidden className="h-5 w-px shrink-0 bg-hairline-strong" />
        {chip("GLOBAL", t(locale, "dash_global"))}
      </nav>
    </div>
  );
}
