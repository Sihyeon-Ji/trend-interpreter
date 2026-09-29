import Link from "next/link";
import { t, type Locale } from "@/lib/i18n";
import { regionLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import { chipClass } from "@/lib/ui";

/** 지역 고르기. 고른 값은 주소(?regions=)에만 둔다 — 익명은 설정을 갖지 않는다(AGENTS.md).
 *  전체를 보다가 한 나라를 누르면 그 나라만, 고른 나라를 다시 누르면 뺀다. 다 빼면 전체로 돌아간다. */
export function RegionChips({ selected, counts, all, locale, list }: { selected: string[]; counts: Record<string, number>; all: boolean; locale: Locale; list?: string }) {
  // 지역을 바꿔도 보던 탭(목록)은 그대로
  const href = (next: string[]) => `/?regions=${next.length ? next.join(",") : "all"}${list ? `&list=${list}` : ""}`;
  const toggle = (r: string) => (all ? [r] : selected.includes(r) ? selected.filter((x) => x !== r) : [...selected, r]);
  const chip = chipClass;
  return (
    // 휴대폰에서는 한 줄로 옆으로 밀어 본다 — 칩 12개가 네 줄로 쌓여 목록이 화면 아래로 밀렸다
    <nav aria-label={t(locale, "dash_regions")} className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
      <Link href={href([])} className={chip(all)} aria-current={all ? "true" : undefined}>{t(locale, "dash_all")}</Link>
      {[...TARGET_REGIONS, "GLOBAL"].map((r) => {
        const on = !all && selected.includes(r);
        return (
          <Link key={r} href={href(toggle(r))} className={chip(on)} aria-current={on ? "true" : undefined}>
            {regionLabel(locale, r)} <span className="tabular-nums opacity-75">{counts[r] ?? 0}</span>
          </Link>
        );
      })}
    </nav>
  );
}
