"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LocaleSwitch } from "@/components/locale-switch";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Item = { href: string; key: StringKey };
// 주요 흐름(살펴보기 → 추천받기·만들기)과 그것을 돕는 화면을 나눈다 (docs/트렌드/디자인-개편.md)
const MAIN: Item[] = [{ href: "/", key: "nav_dashboard" }, { href: "/recommend", key: "nav_recommend" }];
const MORE: Item[] = [
  { href: "/dictionary", key: "nav_dictionary" },
  { href: "/explain", key: "nav_explain" },
  { href: "/map", key: "nav_map" },
  { href: "/graph", key: "nav_graph" },
  { href: "/updates", key: "updates_title" },
];

// 나라 화면(/country/*)은 세계 지도의 아래 화면이다(그 화면의 경로 줄도 '세계 지도 › 나라')
const active = (path: string, href: string) => (href === "/" ? path === "/"
  : path === href || path.startsWith(`${href}/`) || (href === "/map" && path.startsWith("/country/")));

function NavLinks({ locale, reviewer, onNavigate }: { locale: Locale; reviewer: boolean; onNavigate?: () => void }) {
  const path = usePathname();
  const link = (i: Item) => {
    const on = active(path, i.href);
    return (
      <li key={i.href}>
        <Link href={i.href} onClick={onNavigate} aria-current={on ? "page" : undefined}
          className={cn("flex h-9 items-center rounded-md border px-3 text-[14px]",
            on ? "border-hairline bg-background font-medium text-ink" : "border-transparent text-charcoal hover:bg-accent hover:text-ink")}>
          {t(locale, i.key)}
        </Link>
      </li>
    );
  };
  return (
    <div className="space-y-3">
      <ul className="space-y-0.5">{MAIN.map(link)}</ul>
      <ul className="space-y-0.5 border-t border-hairline pt-3">{MORE.map(link)}</ul>
      {reviewer && <ul className="space-y-0.5 border-t border-hairline pt-3">{link({ href: "/admin", key: "nav_admin" })}</ul>}
    </div>
  );
}

function Account({ locale, signedIn, nick, onNavigate }: { locale: Locale; signedIn: boolean; nick: string | null; onNavigate?: () => void }) {
  const path = usePathname();
  // 로그인하면 보던 화면으로 돌아온다(검수자가 아닌 계정이 매번 /admin 에 떨어지던 것). next 는 로그인 화면이 safeNext 로 거른다
  const href = signedIn ? "/me" : path === "/" || path.startsWith("/login") ? "/login" : `/login?next=${encodeURIComponent(path)}`;
  return (
    <div className="space-y-3 text-[14px]">
      <Link href={href} onClick={onNavigate} aria-current={path === (signedIn ? "/me" : "/login") ? "page" : undefined}
        className={cn("block truncate hover:text-ink", path === (signedIn ? "/me" : "/login") ? "font-medium text-ink" : "text-charcoal")}>
        {signedIn ? nick ?? t(locale, "nav_me") : t(locale, "nav_sign_in")}
      </Link>
      <LocaleSwitch locale={locale} />
    </div>
  );
}

/** 왼쪽 메뉴(1024px 이상)와 휴대폰의 위 막대·서랍. 서랍은 Esc·바깥 누르기·메뉴 고르기로 닫히고, 닫히면 초점이 메뉴 단추로 돌아간다. */
export function Sidebar({ locale, signedIn, nick, reviewer }: { locale: Locale; signedIn: boolean; nick: string | null; reviewer: boolean }) {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const close = () => {
    setOpen(false);
    button.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";        // 서랍 뒤 화면이 같이 밀리지 않게
    panel.current?.querySelector<HTMLElement>("a,button")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); button.current?.focus(); } };
    document.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = prev; document.removeEventListener("keydown", onKey); };
  }, [open]);

  const brand = <Link href="/" className="text-[16px] font-semibold whitespace-nowrap text-ink">{t(locale, "site")}</Link>;
  return (
    <>
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-hairline bg-sidebar lg:flex">
        <div className="px-5 pt-5 pb-4">{brand}</div>
        <nav aria-label={t(locale, "nav_label")} className="flex-1 overflow-y-auto px-3"><NavLinks locale={locale} reviewer={reviewer} /></nav>
        <div className="border-t border-hairline px-5 py-4"><Account locale={locale} signedIn={signedIn} nick={nick} /></div>
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-hairline bg-background px-2 lg:hidden">
        <button ref={button} type="button" onClick={() => setOpen(true)} aria-expanded={open} aria-controls="mobile-nav"
          aria-label={t(locale, "nav_open")} className="flex h-10 w-10 items-center justify-center rounded-md text-ink hover:bg-accent">
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5.5h14M3 10h14M3 14.5h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
        </button>
        {brand}
        <div className="ml-auto pr-2"><LocaleSwitch locale={locale} /></div>
      </header>

      {open && (
        <div id="mobile-nav" role="dialog" aria-modal="true" aria-label={t(locale, "nav_label")} className="fixed inset-0 z-40 flex lg:hidden">
          <button type="button" tabIndex={-1} aria-label={t(locale, "nav_close")} className="absolute inset-0 bg-black/30" onClick={close} />
          <div ref={panel} className="relative flex h-full w-[280px] max-w-[85vw] flex-col bg-sidebar">
            <div className="flex h-14 items-center justify-between border-b border-hairline pl-5 pr-2">
              {brand}
              <button type="button" onClick={close} aria-label={t(locale, "nav_close")} className="flex h-10 w-10 items-center justify-center rounded-md text-ink hover:bg-accent">
                <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M4 4l10 10M14 4L4 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
              </button>
            </div>
            <nav aria-label={t(locale, "nav_label")} className="flex-1 overflow-y-auto px-3 py-4"><NavLinks locale={locale} reviewer={reviewer} onNavigate={() => setOpen(false)} /></nav>
            <div className="border-t border-hairline px-5 py-4"><Account locale={locale} signedIn={signedIn} nick={nick} onNavigate={() => setOpen(false)} /></div>
          </div>
        </div>
      )}
    </>
  );
}
