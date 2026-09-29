"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { t, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { LocaleSwitch } from "./locale-switch";

export function SiteNav({ locale, sample, readerNick, signedIn }: { locale: Locale; sample: boolean; readerNick?: string | null; signedIn: boolean }) {
  const path = usePathname();
  const admin = path.startsWith("/admin");
  const links = [
    { href: "/", label: t(locale, "nav_map") },            // 지도가 첫 화면
    { href: "/trends", label: t(locale, "nav_trends") },   // 지역별 키워드 대시보드 (Plan 04)
    { href: "/recommend", label: t(locale, "nav_recommend") },   // 사진·문구로 밈 추천 (Plan 07)
    { href: "/explain", label: t(locale, "nav_explain") },
    { href: "/dictionary", label: t(locale, "nav_dictionary") },
  ];
  const nav = (cls: string) => (
    <nav className={cn("flex items-center gap-5 text-[14px] whitespace-nowrap", cls)}>
      {links.map((l) => {
        const active = !admin && (l.href === "/" ? path === "/" : path.startsWith(l.href));
        return (
          <Link key={l.href} href={l.href} className={cn("text-steel hover:text-ink", active && "font-medium text-ink")} aria-current={active ? "page" : undefined}>
            {l.label}
          </Link>
        );
      })}
      {admin && <Link href="/admin" className="font-medium text-ink" aria-current="page">{t(locale, "nav_admin")}</Link>}
    </nav>
  );
  return (
    <header className="border-b border-hairline bg-background">
      <div className="w-full px-4 sm:px-6">
        <div className="flex h-14 items-center gap-8">
          <Link href="/" className="text-[16px] font-semibold whitespace-nowrap text-ink">{t(locale, "site")}</Link>
          {nav("hidden sm:flex")}
          <div className="ml-auto flex items-center gap-4 whitespace-nowrap">
            {sample && <span className="hidden text-[13px] text-steel sm:inline">{t(locale, "sample_mode")}</span>}
            {signedIn
              ? <Link href="/me" className={cn("text-[14px] text-steel hover:text-ink", path === "/me" && "font-medium text-ink")}>{readerNick ?? t(locale, "nav_me")}</Link>
              : <Link href="/login" className={cn("text-[14px] text-steel hover:text-ink", path === "/login" && "font-medium text-ink")}>{t(locale, "nav_sign_in")}</Link>}
            <LocaleSwitch locale={locale} />
          </div>
        </div>
        {/* 좁은 화면은 한 줄 그대로 옆으로 밀어 본다 — 영어 메뉴 다섯 개가 390px 화면을 넘어 페이지 전체가 옆으로 밀렸다(검토 3차) */}
        {nav("-mx-4 overflow-x-auto px-4 pb-3 [scrollbar-width:none] sm:hidden")}
      </div>
    </header>
  );
}
