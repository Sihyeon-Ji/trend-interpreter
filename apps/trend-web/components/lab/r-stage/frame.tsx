"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { setLocaleCookie, type Locale } from "@/lib/i18n";
import { ActorTag, fmtN } from "./bits";
import { tx } from "./copy";
import { useStage } from "./store";

export const BASE = "/lab/r-stage";

/* 틀 — 위 막대는 무대보다 한 단계 흐리게(무대가 주인공). 바닥글은 '누가 무엇을 하나' 읽는 법 */
export function Frame({ locale, who, review, children }: { locale: Locale; who: string | null; review: number | null; children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { run } = useStage();
  const setLocale = (l: Locale) => {
    if (l === locale) return;
    setLocaleCookie(l);
    router.refresh();
  };
  const nav = [
    { href: BASE, label: tx(locale, "nav_make"), on: path === BASE },
    ...(run ? [{ href: `${BASE}/drafts`, label: tx(locale, "nav_drafts"), on: path.startsWith(`${BASE}/drafts`) }] : []),
    { href: `${BASE}/explore`, label: tx(locale, "nav_explore"), on: path.startsWith(`${BASE}/explore`) || path.startsWith(`${BASE}/term`) },
  ];
  const signed = run?.cols.filter((c) => c.sign).length ?? 0;
  return (
    <>
      <a href="#rs-main" className="rs-skip">{tx(locale, "skip")}</a>
      <header className="rs-top" style={{ viewTransitionName: "rs-top" }}>
        <Link href={BASE} className="rs-brand" aria-label="Trend Interpreter">
          <b>Trend Interpreter</b>
        </Link>
        <nav className="rs-nav" aria-label={tx(locale, "nav_main")}>
          {nav.map((n) => (
            <Link key={n.href} href={n.href} aria-current={n.on ? "page" : undefined}>
              {n.label}
              {n.href.endsWith("/drafts") && run ? <span className="rs-nav-count" aria-label={tx(locale, "dr_tally", { n: run.cols.length, m: signed })}>{signed}/{run.cols.length}</span> : null}
            </Link>
          ))}
        </nav>
        <div className="rs-top-end">
          {review != null && (
            <a className="rs-top-review" href="/admin">{tx(locale, "nav_review")} <b>{fmtN(review)}</b></a>
          )}
          <div className="rs-lang" role="group" aria-label={tx(locale, "lang_group")}>
            <button type="button" lang="ko" aria-pressed={locale === "ko"} onClick={() => setLocale("ko")}>한국어</button>
            <button type="button" lang="en" aria-pressed={locale === "en"} onClick={() => setLocale("en")}>EN</button>
          </div>
          {who && <span className="rs-who">{who}</span>}
        </div>
      </header>
      <main id="rs-main" className="rs-main" tabIndex={-1}>{children}</main>
      <footer className="rs-foot">
        <div className="rs-legend" aria-label={tx(locale, "foot_legend")}>
          <ActorTag who="rule" locale={locale}>{tx(locale, "foot_rule")}</ActorTag>
          <ActorTag who="ai" locale={locale}>{tx(locale, "foot_ai")}</ActorTag>
          <ActorTag who="human" locale={locale}>{tx(locale, "foot_human")}</ActorTag>
        </div>
        <span className="rs-foot-note">{tx(locale, "foot_note")}</span>
      </footer>
    </>
  );
}
