import Link from "next/link";
import { Suspense } from "react";
import { LocaleSwitch } from "@/components/locale-switch";
import type { Locale } from "@/lib/i18n";
import { c } from "@/lib/lab/f-report/copy";
import { NavLink } from "./nav-link";
import { SearchBox } from "./search-box";

/** 시안의 틀 — 앱 사이드바 대신 얇은 머리와 바닥. 틀도 디자인의 일부다. */
export function Frame({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  return (
    <>
      <a href="#fr-main" className="fr-skip">{c(locale, "skip")}</a>
      <header className="fr-header">
        <div className="fr-container fr-header-inner">
          <Link href="/lab/f-report" className="fr-brand"><span>{c(locale, "brand")}</span><small>{c(locale, "brand_sub")}</small></Link>
          <nav className="fr-nav" aria-label="Main">
            <NavLink href="/lab/f-report">{c(locale, "nav_report")}</NavLink>
            <NavLink href="/recommend">{c(locale, "nav_recommend")}</NavLink>
          </nav>
          <div className="fr-header-right">
            <Suspense fallback={<div className="fr-search" aria-hidden />}>
              <SearchBox locale={locale} />
            </Suspense>
            <div className="hidden sm:block"><LocaleSwitch locale={locale} /></div>
            <Link href="/lab" className="fr-drafts hidden md:inline">{c(locale, "nav_drafts")}</Link>
          </div>
        </div>
      </header>
      <main id="fr-main" className="fr-main">
        <div className="fr-container">{children}</div>
      </main>
      <footer className="fr-footer">
        <div className="fr-container fr-footer-inner">
          <p className="m-0 max-w-[70ch]">{c(locale, "footer_sources")}</p>
          <div className="flex items-center gap-3">
            <span>{c(locale, "footer_draft")}</span>
            <span className="sm:hidden"><LocaleSwitch locale={locale} /></span>
            <Link href="/lab" className="fr-link">{c(locale, "nav_drafts")}</Link>
          </div>
        </div>
      </footer>
    </>
  );
}
