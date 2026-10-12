"use client";

import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { setLocaleCookie, t, type Locale, type StringKey } from "@/lib/i18n";
import { ActorTag, fmtN } from "./bits";
import { tx } from "./copy";
import { useStage } from "./store";

type Item = { href: string; key: StringKey };
// 위 막대 뒤쪽은 일의 순서대로: 사전 → 메시지 해석 → 세계. 나머지는 '더 보기' (Plan 20)
const TOOLS: Item[] = [{ href: "/dictionary", key: "nav_dictionary" }, { href: "/explain", key: "nav_explain" }, { href: "/map", key: "nav_map" }];
const MORE: Item[] = [
  { href: "/briefing", key: "nav_briefing" }, { href: "/check", key: "nav_check" }, { href: "/recommend", key: "nav_recommend" },
  { href: "/graph", key: "nav_graph" }, { href: "/updates", key: "updates_title" },
];

// 밈 항목(/dictionary/<id>)은 둘러보기의 아래 화면, 나라 화면(/country/*)은 세계 지도의 아래 화면이다
const on = (path: string, href: string) => (href === "/dictionary" ? path === href
  : path === href || path.startsWith(`${href}/`) || (href === "/map" && path.startsWith("/country/")));

/** '더 보기' — 누르면 아래로 열리는 목록. Esc·바깥 누르기·고르기로 닫힌다 */
function More({ locale, items, path, account }: { locale: Locale; items: Item[]; path: string; account: { href: string; label: string } }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", key); };
  }, [open]);
  return (
    <div ref={box} className="rs-menu">
      <button type="button" aria-expanded={open} data-on={items.some((i) => on(path, i.href))} onClick={() => setOpen((v) => !v)}>
        {t(locale, "nav_more")}<ChevronDown aria-hidden="true" size={14} />
      </button>
      {open && (
        <ul>
          {items.map((i) => (
            <li key={i.href}>
              <Link href={i.href} onClick={() => setOpen(false)} aria-current={on(path, i.href) ? "page" : undefined}>{t(locale, i.key)}</Link>
            </li>
          ))}
          <li className="rs-menu-account"><Link href={account.href} onClick={() => setOpen(false)}>{account.label}</Link></li>
        </ul>
      )}
    </div>
  );
}

/* 앱 틀 — 위 막대는 무대보다 한 단계 흐리게(무대가 주인공). 바닥글은 '누가 무엇을 하나' 읽는 법.
   페이지는 <main id="main"> 을 스스로 그린다. 디자인 시안(/lab/*)은 자기 틀을 스스로 그리므로 내용만 둔다 */
export function Frame({ locale, font, signedIn, nick, reviewer, review, sample, children }: {
  locale: Locale; font: string; signedIn: boolean; nick: string | null; reviewer: boolean; review: number | null; sample: boolean; children: React.ReactNode;
}) {
  const path = usePathname();
  const router = useRouter();
  const { run } = useStage();
  const setLocale = (l: Locale) => {
    if (l === locale) return;
    setLocaleCookie(l);
    router.refresh();
  };
  const nav = [
    { href: "/", label: tx(locale, "nav_make"), on: path === "/" },
    ...(run ? [{ href: "/drafts", label: tx(locale, "nav_drafts"), on: path.startsWith("/drafts") }] : []),
    { href: "/trends", label: tx(locale, "nav_explore"), on: path.startsWith("/trends") || path.startsWith("/dictionary/") },
    ...TOOLS.map((i) => ({ href: i.href, label: t(locale, i.key), on: on(path, i.href) })),
  ];
  const signed = run?.cols.filter((c) => c.approval?.status === "approved").length ?? 0;
  // 로그인하면 보던 화면으로 돌아온다. next 는 로그인 화면이 safeNext 로 거른다
  const account = {
    href: signedIn ? "/me" : path === "/" || path.startsWith("/login") ? "/login" : `/login?next=${encodeURIComponent(path)}`,
    label: signedIn ? nick ?? t(locale, "nav_me") : t(locale, "nav_sign_in"),
  };
  if (path.startsWith("/lab")) return <>{children}</>;
  return (
    <div className={`r-stage ${font}`} data-locale={locale}>
      <a href="#main" className="rs-skip">{tx(locale, "skip")}</a>
      <header className="rs-top" style={{ viewTransitionName: "rs-top" }}>
        <Link href="/" className="rs-brand" aria-label="Trend Interpreter">
          <b>Trend Interpreter</b>
        </Link>
        <nav className="rs-nav" aria-label={tx(locale, "nav_main")}>
          {nav.map((n) => (
            <Link key={n.href} href={n.href} aria-current={n.on ? "page" : undefined}>
              {n.label}
              {n.href === "/drafts" && run ? <span className="rs-nav-count" aria-label={tx(locale, "dr_tally", { n: run.cols.length, m: signed })}>{signed}/{run.cols.length}</span> : null}
            </Link>
          ))}
        </nav>
        <div className="rs-top-end">
          <More locale={locale} path={path} account={account} items={reviewer ? [...MORE, { href: "/admin", key: "nav_admin" }] : MORE} />
          {review != null && (
            <a className="rs-top-review" href="/admin">{tx(locale, "nav_review")} <b>{fmtN(review)}</b></a>
          )}
          <div className="rs-lang" role="group" aria-label={tx(locale, "lang_group")}>
            <button type="button" lang="ko" aria-pressed={locale === "ko"} onClick={() => setLocale("ko")}>한국어</button>
            <button type="button" lang="en" aria-pressed={locale === "en"} onClick={() => setLocale("en")}>EN</button>
            <button type="button" lang="ja" aria-pressed={locale === "ja"} onClick={() => setLocale("ja")}>日本語</button>
          </div>
          <Link href={account.href} className="rs-who">{account.label}</Link>
        </div>
      </header>
      {sample && <p className="rs-sample">{t(locale, "sample_banner")}</p>}
      <div className="rs-body">{children}</div>
      <footer className="rs-foot">
        <div className="rs-legend" aria-label={tx(locale, "foot_legend")}>
          <ActorTag who="rule" locale={locale}>{tx(locale, "foot_rule")}</ActorTag>
          <ActorTag who="ai" locale={locale}>{tx(locale, "foot_ai")}</ActorTag>
          <ActorTag who="human" locale={locale}>{tx(locale, "foot_human")}</ActorTag>
        </div>
        <span className="rs-foot-note">{tx(locale, "foot_note")} · <Link href="/about" className="rs-link">{t(locale, "about_title")}</Link></span>
      </footer>
    </div>
  );
}
