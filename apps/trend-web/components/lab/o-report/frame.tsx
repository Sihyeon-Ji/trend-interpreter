/* 초안 1의 틀 — 앱 사이드바 대신 이 초안이 스스로 그린다(components/shell-chrome.tsx 가 /lab 에서는 겉을 빼 준다).
   위 막대 하나: 이름, 메뉴 셋, 찾기(어디서든), 언어, 초안 목록(조용히). 휴대폰은 메뉴가 둘째 줄로 내려간다.
   바닥글은 두지 않는다 — '© 2026' 과 같은 링크를 되풀이하던 줄이었다. 페이지는 '숫자는 이렇게 셌어요' 로 끝난다. */
import Link from "next/link";
import { Suspense } from "react";
import type { Locale } from "@/lib/i18n";
import { tr } from "@/lib/lab/o-report-copy";
import { LocaleToggle } from "./locale-toggle";
import { SearchBox } from "./search-box";

export function Frame({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const nav = [
    { href: "/lab/o-report", label: tr(locale, "nav_report"), current: true },
    { href: "/recommend", label: tr(locale, "nav_recommend"), current: false },
    { href: "/dictionary", label: tr(locale, "nav_dictionary"), current: false },
  ];
  const links = (cls: string) => nav.map((n) => (
    <li key={n.href}>
      <Link href={n.href} aria-current={n.current ? "page" : undefined}
        className={`${cls} ${n.current ? "font-semibold text-[var(--or-ink)] shadow-[inset_0_-2px_0_var(--or-ink)]" : "text-[var(--or-slate)] hover:text-[var(--or-ink)]"}`}>
        {n.label}
      </Link>
    </li>
  ));
  return (
    <>
      <a href="#or-main" className="sr-only z-[60] rounded-[6px] bg-white px-3 py-2 text-[14px] text-[var(--or-ink)] focus:not-sr-only focus:fixed focus:top-3 focus:left-3">{tr(locale, "skip")}</a>
      <header className="sticky top-0 z-30 border-b border-[var(--or-line)] bg-white">
        <div className="mx-auto flex h-16 max-w-[1320px] items-center gap-4 px-5 sm:px-8 lg:gap-8">
          <Link href="/lab/o-report" className="shrink-0 text-[18px] font-extrabold tracking-[-0.03em] text-[var(--or-ink)]">{tr(locale, "brand")}</Link>
          <nav aria-label={tr(locale, "nav_label")} className="hidden h-full md:block">
            <ul className="flex h-full items-stretch gap-6">{links("inline-flex h-full items-center text-[14px]")}</ul>
          </nav>
          <div className="ml-auto flex items-center gap-3 lg:gap-5">
            <Suspense fallback={null}><SearchBox locale={locale} /></Suspense>
            <LocaleToggle locale={locale} />
            <Link href="/lab" className="hidden text-[13px] text-[var(--or-slate)] underline-offset-4 hover:text-[var(--or-ink)] hover:underline md:inline">{tr(locale, "drafts")}</Link>
          </div>
        </div>
        <nav aria-label={tr(locale, "nav_label")} className="border-t border-[var(--or-line)] md:hidden">
          <ul className="mx-auto flex h-11 max-w-[1320px] items-stretch gap-5 px-5">
            {links("inline-flex h-full items-center text-[14px]")}
            <li className="ml-auto"><Link href="/lab" className="inline-flex h-full items-center text-[13px] text-[var(--or-slate)]">{tr(locale, "drafts")}</Link></li>
          </ul>
        </nav>
      </header>
      <main id="or-main" tabIndex={-1} className="focus:outline-none">{children}</main>
    </>
  );
}
