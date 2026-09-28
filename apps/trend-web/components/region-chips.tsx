import Link from "next/link";
import { t, type Locale } from "@/lib/i18n";
import { regionLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import { cn } from "@/lib/utils";

/** 지역 고르기. 고른 값은 주소(?regions=)에만 둔다 — 익명은 설정을 갖지 않는다(AGENTS.md).
 *  전체를 보다가 한 나라를 누르면 그 나라만, 고른 나라를 다시 누르면 뺀다. 다 빼면 전체로 돌아간다. */
export function RegionChips({ selected, counts, all, locale }: { selected: string[]; counts: Record<string, number>; all: boolean; locale: Locale }) {
  const href = (next: string[]) => `/trends?regions=${next.length ? next.join(",") : "all"}`;
  const toggle = (r: string) => (all ? [r] : selected.includes(r) ? selected.filter((x) => x !== r) : [...selected, r]);
  const chip = (on: boolean) => cn("rounded-full border px-3 py-1 text-[13px] whitespace-nowrap",
    on ? "border-primary bg-primary text-primary-foreground" : "border-hairline-strong text-charcoal hover:border-ink hover:text-ink");
  return (
    <nav aria-label={t(locale, "dash_regions")} className="flex flex-wrap gap-2">
      <Link href={href([])} className={chip(all)} aria-current={all ? "true" : undefined}>{t(locale, "dash_all")}</Link>
      {[...TARGET_REGIONS, "GLOBAL"].map((r) => {
        const on = !all && selected.includes(r);
        return (
          <Link key={r} href={href(toggle(r))} className={chip(on)} aria-current={on ? "true" : undefined}>
            {regionLabel(locale, r)} <span className="tabular-nums opacity-70">{counts[r] ?? 0}</span>
          </Link>
        );
      })}
    </nav>
  );
}
