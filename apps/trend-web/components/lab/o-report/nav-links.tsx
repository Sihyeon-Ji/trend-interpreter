"use client";

/* 위 막대의 메뉴 셋. 지금 있는 곳을 표시하고, '밈 추천' 에는 고른 지역을 이어 준다(09-29 검토: 추천이 지역 없이 열렸다).
   리포트·사전은 이 초안 안에, 밈 추천만 앱의 기존 흐름으로 간다(다시 만들지 않는다). */
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { LabLocale as Locale } from "@/lib/i18n";
import { tr } from "@/lib/lab/o-report/copy";
import { TARGET_REGIONS } from "@/lib/reader";

export function NavLinks({ locale, className }: { locale: Locale; className: string }) {
  const path = usePathname();
  const sp = useSearchParams();
  const raw = sp.get("regions");
  // 추천은 목표 지역만 받는다 — 'all' 은 목표 지역 전체, 전 세계(GLOBAL)는 뺀다
  const picked = !raw ? [] : raw === "all" ? TARGET_REGIONS : raw.split(",").filter((r) => TARGET_REGIONS.includes(r));
  const nav = [
    { href: raw ? `/lab/o-report?regions=${encodeURIComponent(raw)}` : "/lab/o-report", label: tr(locale, "nav_report"), current: path === "/lab/o-report" || path.startsWith("/lab/o-report/m/") },
    { href: `/recommend${picked.length ? `?regions=${picked.join(",")}` : ""}`, label: tr(locale, "nav_recommend"), current: false },
    { href: "/lab/o-report/search", label: tr(locale, "nav_dictionary"), current: path.startsWith("/lab/o-report/search") },
  ];
  return nav.map((n) => (
    <li key={n.label}>
      <Link href={n.href} aria-current={n.current ? "page" : undefined}
        className={`${className} ${n.current ? "font-semibold text-[var(--or-ink)] shadow-[inset_0_-2px_0_var(--or-ink)]" : "text-[var(--or-slate)] hover:text-[var(--or-ink)]"}`}>
        {n.label}
      </Link>
    </li>
  ));
}
