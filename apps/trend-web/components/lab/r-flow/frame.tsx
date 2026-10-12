"use client";

/* 작업 공간의 틀 — 옆 메뉴(바탕보다 한 단계 어둡게, 내용이 앞에 서도록), 휴대폰은 위 막대 + 떠 있는 아래 막대.
   ⌘K·/ 로 찾기, N 으로 새 초안. 패널(밈 자세히)은 레이아웃의 @panel 칸이 그린다. */
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, use, useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { Compass, PanelLeftClose, PanelLeftOpen, Plus, Search } from "lucide-react";
import { MotionConfig } from "motion/react";
import { setLocaleCookie, type LabLocale as Locale } from "@/lib/i18n";
import { MARKETS, marketName, num, tr } from "./copy";
import { Logo } from "./glyph";
import { Palette } from "./palette";

export const BASE = "/lab/r-flow";
export const openPalette = () => window.dispatchEvent(new Event("rf-palette"));

const typing = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));

const isMac = () => /Mac|iPhone|iPad/.test(navigator.platform);
const noop = () => () => {};
/** 단축키 표기 — 서버 렌더와 첫 화면은 Ctrl, 그 뒤 맥이면 ⌘ (하이드레이션이 어긋나지 않게) */
const useIsMac = () => useSyncExternalStore(noop, isMac, () => false);

/** 옆 메뉴의 숫자 — 서버가 넘긴 약속(promise)을 기다려 채운다. 틀은 숫자 없이 먼저 그린다 */
function Count({ p, pick, locale, sr }: { p: Promise<unknown>; pick: (v: unknown) => number | null | undefined; locale: Locale; sr?: boolean }) {
  const v = pick(use(p));
  if (v == null) return null;
  return <span className="rf-count">{sr && <span className="rf-sr">{tr(locale, "nav_verified_sr")} </span>}{num(v)}</span>;
}

export function Frame({ locale, counts, queue, signer, children }: {
  locale: Locale; counts: Promise<Record<string, number> | null>; queue: Promise<number | null>; signer: string | null; children: React.ReactNode;
}) {
  const path = usePathname();
  const sp = useSearchParams();
  const router = useRouter();
  const [pal, setPal] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const mac = useIsMac();

  const onExplore = path.startsWith(`${BASE}/explore`);
  const onMake = path === BASE;
  const market = onExplore ? (sp.get("m") ?? "KR") : null;

  const switchLocale = useCallback((next: Locale) => {
    if (next === locale) return;
    setLocaleCookie(next);
    router.refresh();
  }, [locale, router]);

  useEffect(() => {
    const open = () => setPal(true);
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPal((v) => !v);
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey || typing(e.target)) return;
      if (e.key === "/") { e.preventDefault(); setPal(true); }
      else if (e.key === "n" || e.key === "N") { if (!document.querySelector(".rf-pal-wrap")) router.push(BASE); }
    };
    window.addEventListener("rf-palette", open);
    window.addEventListener("keydown", key);
    return () => { window.removeEventListener("rf-palette", open); window.removeEventListener("keydown", key); };
  }, [router]);

  const cmdK = mac ? "⌘K" : "Ctrl K";

  return (
    <MotionConfig reducedMotion="user">
      <a href="#rf-main" className="rf-skip">{tr(locale, "skip")}</a>
      <div className="rf-app" data-collapsed={collapsed}>
        <aside className="rf-side" aria-label={tr(locale, "nav_label")}>
          <Link href={BASE} className="rf-brand">
            <Logo />
            <span className="rf-brand-text"><b>{tr(locale, "brand")}</b><small>{tr(locale, "brand_sub")}</small></span>
          </Link>
          <Link href={BASE} className="rf-new" aria-label={collapsed ? tr(locale, "nav_new") : undefined}>
            <Plus size={16} strokeWidth={2} aria-hidden="true" />
            <span className="rf-nav-label">{tr(locale, "nav_new")}</span>
            <span className="rf-kbd" aria-hidden="true">N</span>
          </Link>
          <nav className="rf-nav" aria-label={tr(locale, "nav_label")}>
            <button type="button" onClick={() => setPal(true)} aria-keyshortcuts="Control+K Meta+K /" title={collapsed ? tr(locale, "nav_search") : undefined}>
              <Search size={16} strokeWidth={1.75} aria-hidden="true" />
              <span className="rf-nav-label">{tr(locale, "nav_search")}</span>
              <span className="rf-kbd" aria-hidden="true">{cmdK}</span>
            </button>
            <Link href={`${BASE}/explore`} aria-current={onExplore && !sp.get("m") ? "page" : undefined} title={collapsed ? tr(locale, "nav_explore") : undefined}>
              <Compass size={16} strokeWidth={1.75} aria-hidden="true" />
              <span className="rf-nav-label">{tr(locale, "nav_explore")}</span>
            </Link>
            <span className="rf-nav-group">{tr(locale, "nav_markets")}</span>
            {MARKETS.map((m) => (
              <Link key={m} href={`${BASE}/explore?m=${m}`} aria-current={market === m && sp.get("m") ? "page" : undefined} title={collapsed ? marketName(locale, m) : undefined}>
                <span className="rf-mkt-badge" aria-hidden="true">{m === "GLOBAL" ? "EN" : m}</span>
                <span className="rf-nav-label">{marketName(locale, m)}</span>
                <Suspense fallback={null}><Count p={counts} pick={(v) => (v as Record<string, number> | null)?.[m]} locale={locale} sr /></Suspense>
              </Link>
            ))}
            <span className="rf-nav-group">{tr(locale, "nav_dict")}</span>
            <a href="/admin" title={collapsed ? tr(locale, "nav_review") : undefined}>
              <span className="rf-mkt-badge" data-k="queue" aria-hidden="true"><i /></span>
              <span className="rf-nav-label">{tr(locale, "nav_review")}</span>
              <Suspense fallback={null}><Count p={queue} pick={(v) => v as number | null} locale={locale} /></Suspense>
            </a>
          </nav>
          <div className="rf-side-foot">
            <div className="rf-langs" role="group" aria-label={tr(locale, "nav_lang")}>
              <button type="button" aria-pressed={locale === "ko"} onClick={() => switchLocale("ko")} lang="ko">한국어</button>
              <button type="button" aria-pressed={locale === "en"} onClick={() => switchLocale("en")} lang="en">English</button>
            </div>
            <span className="rf-side-note">{signer ?? tr(locale, "nav_signed_out")}</span>
            <span className="rf-side-note rf-muted">{tr(locale, "nav_note")}</span>
            <button type="button" className="rf-collapse" onClick={() => setCollapsed((v) => !v)} aria-label={tr(locale, collapsed ? "nav_expand" : "nav_collapse")} aria-pressed={collapsed}>
              {collapsed ? <PanelLeftOpen size={16} strokeWidth={1.75} aria-hidden="true" /> : <PanelLeftClose size={16} strokeWidth={1.75} aria-hidden="true" />}
            </button>
          </div>
        </aside>

        <div className="rf-main">
          <header className="rf-top">
            <Link href={BASE} className="rf-brand" style={{ padding: 0 }}><Logo /><b>{tr(locale, "brand")}</b></Link>
            <button type="button" className="rf-icon-btn" onClick={() => setPal(true)} aria-label={tr(locale, "nav_search")}><Search size={18} strokeWidth={1.75} aria-hidden="true" /></button>
          </header>
          <main id="rf-main" className="rf-canvas" tabIndex={-1}>{children}</main>
        </div>
      </div>

      <nav className="rf-dock" aria-label={tr(locale, "nav_label")}>
        <Link href={BASE} aria-current={onMake ? "page" : undefined}><Plus size={16} strokeWidth={2} aria-hidden="true" />{tr(locale, "nav_new")}</Link>
        <Link href={`${BASE}/explore`} aria-current={onExplore ? "page" : undefined}><Compass size={16} strokeWidth={1.75} aria-hidden="true" />{tr(locale, "nav_explore")}</Link>
        <button type="button" onClick={() => setPal(true)}><Search size={16} strokeWidth={1.75} aria-hidden="true" />{tr(locale, "nav_search")}</button>
      </nav>

      {pal && <Palette locale={locale} onClose={() => setPal(false)} onLocale={switchLocale} />}
    </MotionConfig>
  );
}
