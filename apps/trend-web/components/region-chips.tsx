"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ChipMark } from "@/components/chip-mark";
import { t, type Locale } from "@/lib/i18n";
import { regionLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import { chipClass } from "@/lib/ui";
import { cn } from "@/lib/utils";

const KNOWN = [...TARGET_REGIONS, "GLOBAL"];
// 밈이 거의 없는 지역은 '더보기' 뒤로 — 칩 13개가 세 줄을 차지했고 그중 싱가포르 1·말레이시아 3·필리핀 9개였다(실데이터 10-04).
// 전체가 이만큼일 때만 접는다(예시 데이터는 지역마다 몇 개뿐이라 접지 않는다). 고른 지역은 늘 보인다.
const FOLD_TOTAL = 200;
const FOLD_UNDER = 20;

/** 지역 고르기 — 여러 곳을 고른다. 대시보드·사전·최근 변화·추천·세계 지도가 같은 규칙이다(개편 종합 09-29): '전체' 에서 한 곳을
 *  누르면 그곳만, 다른 곳을 누르면 더하고, 고른 곳을 누르면 빼고, 다 빼면 '전체'. 고른 값은 주소(?regions=KR,JP)에만 둔다 —
 *  익명은 설정을 갖지 않는다(AGENTS.md). picked 가 비면 '전체'. counts 가 없으면(불러오기 실패) 건수를 내지 않는다.
 *  순서: 전체 → 목표 지역 → 세로 선 → 글로벌(목표 지역 밖에서도 널리 쓰이는 말). */
export function RegionChips({ picked, counts, locale, list, base = "/trends" }: {
  picked: string[]; counts?: Record<string, number>; locale: Locale; list?: string;
  base?: string;   // 칩이 여는 화면 — 대시보드(/) 말고 브리핑(/briefing)도 같은 칩을 쓴다
}) {
  // 지역을 바꿔도 보던 탭(목록)은 그대로, 쪽은 처음으로
  const href = (next: string[]) => `${base}?regions=${next.length ? next.join(",") : "all"}${list ? `&list=${list}` : ""}`;
  const toggled = (r: string) => (picked.includes(r) ? picked.filter((x) => x !== r) : KNOWN.filter((x) => x === r || picked.includes(x)));
  const nav = useRef<HTMLElement>(null);
  const [open, setOpen] = useState(false);
  const minor = (r: string) => (counts?.ALL ?? 0) >= FOLD_TOTAL && (counts?.[r] ?? 0) < FOLD_UNDER && !picked.includes(r);
  const folded = TARGET_REGIONS.filter(minor);
  const key = picked.join(",");
  // 휴대폰은 한 줄 가로 밀기 — 처음 고른 칩이 화면 밖에 있으면 보이게 민다(세로로는 움직이지 않는다)
  useEffect(() => {
    const el = nav.current, on = el?.querySelector<HTMLElement>("[data-on]");
    if (el && on && el.scrollWidth > el.clientWidth) el.scrollLeft = Math.max(0, on.offsetLeft - el.offsetLeft - 16);
  }, [key]);
  const chip = (r: string | null, label: string) => {
    const on = r === null ? !picked.length : picked.includes(r), n = counts?.[r ?? "ALL"];
    return (
      <Link key={r ?? "ALL"} href={href(r === null ? [] : toggled(r))} data-on={on || undefined} className={cn(chipClass(on), !on && n === 0 && "text-steel")}>
        <ChipMark on={on} />{label}{n != null && <> <span className="tabular-nums">{n}</span></>}
        {on && <span className="sr-only"> {t(locale, "chip_selected")}</span>}
      </Link>
    );
  };
  return (
    <div className="flex items-start gap-3">
      <span className="hidden h-8 shrink-0 items-center text-[13px] font-medium text-steel sm:flex">{t(locale, "dash_regions")}</span>
      <nav ref={nav} aria-label={t(locale, "dash_regions")}
        className="-mx-4 flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
        {chip(null, t(locale, "dash_all"))}
        {TARGET_REGIONS.filter((r) => open || !minor(r)).map((r) => chip(r, regionLabel(locale, r)))}
        {folded.length > 0 && (
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
            className="h-8 shrink-0 rounded-md px-2 text-[13px] text-link-blue hover:underline">
            {open ? t(locale, "chip_fewer") : t(locale, "chip_more").replace("{n}", String(folded.length))}
          </button>
        )}
        <span aria-hidden className="h-5 w-px shrink-0 bg-hairline-strong" />
        {chip("GLOBAL", t(locale, "dash_global"))}
      </nav>
    </div>
  );
}
