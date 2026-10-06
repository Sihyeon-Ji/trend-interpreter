"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LocaleSwitch } from "@/components/locale-switch";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Item = { href: string; key: StringKey };
// 위 막대에는 일의 순서대로 다섯만: 만들기 → 둘러보기 → 사전 → 메시지 해석 → 세계 (Plan 20). 나머지는 '더 보기'
const MAIN: Item[] = [
  { href: "/", key: "nav_make" }, { href: "/trends", key: "nav_browse" }, { href: "/dictionary", key: "nav_dictionary" },
  { href: "/explain", key: "nav_explain" }, { href: "/map", key: "nav_map" },
];
const MORE: Item[] = [
  { href: "/briefing", key: "nav_briefing" }, { href: "/check", key: "nav_check" }, { href: "/recommend", key: "nav_recommend" },
  { href: "/graph", key: "nav_graph" }, { href: "/updates", key: "updates_title" },
];

// 나라 화면(/country/*)은 세계 지도의 아래 화면이다
const active = (path: string, href: string) => (href === "/" ? path === "/"
  : path === href || path.startsWith(`${href}/`) || (href === "/map" && path.startsWith("/country/")));

/** 데스크톱의 '더 보기' — 누르면 아래로 열리는 목록. Esc·바깥 누르기·고르기로 닫힌다. 떠 있는 메뉴라 그림자를 쓴다(그림자는 여기와 서랍에만). */
function More({ locale, items }: { locale: Locale; items: Item[] }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const path = usePathname();
  const on = items.some((i) => active(path, i.href));
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", key); };
  }, [open]);
  return (
    <div ref={box} className="relative">
      <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)}
        className={cn("flex h-14 items-center gap-1 px-2.5 text-[14px] hover:text-ink", on ? "font-semibold text-ink" : "text-steel")}>
        {t(locale, "nav_more")}
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden className={cn("transition-transform", open && "rotate-180")}><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.4" /></svg>
      </button>
      {open && (
        <ul className="absolute top-[52px] left-0 z-40 min-w-[200px] border border-hairline bg-background py-1.5 shadow-[0_8px_24px_rgba(23,25,28,0.12)]">
          {items.map((i) => (
            <li key={i.href}>
              <Link href={i.href} onClick={() => setOpen(false)} aria-current={active(path, i.href) ? "page" : undefined}
                className={cn("block px-4 py-2 text-[14px] hover:bg-surface", active(path, i.href) ? "font-semibold text-ink" : "text-charcoal")}>
                {t(locale, i.key)}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** 앱 틀의 위 막대(시안 f-report). 데스크톱은 한 줄 메뉴, 휴대폰은 메뉴 단추가 서랍을 연다. 서랍은 Esc·바깥 누르기·고르기로 닫히고 초점이 단추로 돌아간다. */
export function TopBar({ locale, signedIn, nick, reviewer }: { locale: Locale; signedIn: boolean; nick: string | null; reviewer: boolean }) {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const close = () => { setOpen(false); button.current?.focus(); };

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.querySelector<HTMLElement>("a,button")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); button.current?.focus(); } };
    document.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = prev; document.removeEventListener("keydown", onKey); };
  }, [open]);

  // 로그인하면 보던 화면으로 돌아온다. next 는 로그인 화면이 safeNext 로 거른다
  const account = signedIn ? "/me" : path === "/" || path.startsWith("/login") ? "/login" : `/login?next=${encodeURIComponent(path)}`;
  const accountLabel = signedIn ? nick ?? t(locale, "nav_me") : t(locale, "nav_sign_in");
  const more = reviewer ? [...MORE, { href: "/admin", key: "nav_admin" } as Item] : MORE;
  const link = (i: Item, mobile = false) => {
    const on = active(path, i.href);
    return (
      <li key={i.href}>
        <Link href={i.href} onClick={mobile ? () => setOpen(false) : undefined} aria-current={on ? "page" : undefined}
          className={mobile
            ? cn("block py-2.5 text-[16px]", on ? "font-semibold text-ink" : "text-charcoal")
            : cn("relative flex h-14 items-center px-2.5 text-[14px] hover:text-ink", on ? "font-semibold text-ink after:absolute after:inset-x-2.5 after:bottom-0 after:h-[2px] after:bg-ink" : "text-charcoal")}>
          {t(locale, i.key)}
        </Link>
      </li>
    );
  };

  return (
    <header className="sticky top-0 z-30 border-b border-hairline bg-background print:hidden">
      <div className="mx-auto flex h-14 max-w-[1280px] items-center gap-2 px-4 sm:px-6 xl:px-8">
        <button ref={button} type="button" onClick={() => setOpen(true)} aria-expanded={open} aria-controls="mobile-nav" aria-label={t(locale, "nav_open")}
          className="-ml-2 flex h-10 w-10 items-center justify-center text-ink hover:bg-surface lg:hidden">
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5.5h14M3 10h14M3 14.5h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
        </button>
        <Link href="/" className="flex items-baseline gap-2 whitespace-nowrap">
          <b className="text-[15px] font-bold tracking-[-0.01em] text-ink">Trend Interpreter</b>
          {locale !== "en" && <span className="hidden text-[13px] text-steel sm:inline">{t(locale, "site")}</span>}
        </Link>
        <nav aria-label={t(locale, "nav_label")} className="ml-4 hidden items-center lg:flex">
          <ul className="flex items-center">{MAIN.map((i) => link(i))}</ul>
          <More locale={locale} items={more} />
        </nav>
        <div className="ml-auto flex items-center gap-4 text-[13px]">
          <Link href={account} className="hidden max-w-[10rem] truncate text-steel hover:text-ink sm:inline">{accountLabel}</Link>
          <LocaleSwitch locale={locale} />
        </div>
      </div>

      {open && (
        <div id="mobile-nav" role="dialog" aria-modal="true" aria-label={t(locale, "nav_label")} className="fixed inset-0 z-40 flex lg:hidden">
          <button type="button" tabIndex={-1} aria-label={t(locale, "nav_close")} className="absolute inset-0 bg-black/30" onClick={close} />
          <div ref={panel} className="relative flex h-full w-[300px] max-w-[85vw] flex-col bg-background">
            <div className="flex h-14 items-center justify-between border-b border-hairline pr-2 pl-5">
              <span className="text-[16px] font-bold text-ink">{t(locale, "site")}</span>
              <button type="button" onClick={close} aria-label={t(locale, "nav_close")} className="flex h-10 w-10 items-center justify-center text-ink hover:bg-surface">
                <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M4 4l10 10M14 4L4 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
              </button>
            </div>
            <nav aria-label={t(locale, "nav_label")} className="flex-1 overflow-y-auto px-5 py-3">
              <ul>{MAIN.map((i) => link(i, true))}</ul>
              <ul className="mt-3 border-t border-hairline pt-3">{more.map((i) => link(i, true))}</ul>
            </nav>
            <div className="border-t border-hairline px-5 py-4 text-[14px]">
              <Link href={account} onClick={() => setOpen(false)} className="text-charcoal hover:text-ink">{accountLabel}</Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
