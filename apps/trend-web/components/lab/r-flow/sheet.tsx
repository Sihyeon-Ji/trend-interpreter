"use client";

/* 옆 패널 — 밈 자세히. 목록·초안 위에 오른쪽에서 열리고, 뒤 화면은 그대로 쓸 수 있다(데스크톱). 휴대폰은 아래에서 올라오는 시트.
   열고 닫는 움직임은 View Transitions(React ViewTransition): 길 이동과 함께 들어오고 나간다. 브라우저 뒤로 가기도 닫기다. */
import { usePathname, useRouter } from "next/navigation";
import { ViewTransition, useCallback, useEffect, useRef } from "react";
import { Maximize2, X } from "lucide-react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { tr } from "./copy";

export function Sheet({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const head = useRef<HTMLHeadingElement>(null);
  const back = useRef<Element | null>(null);
  const close = useCallback(() => router.back(), [router]);

  useEffect(() => {
    back.current = document.activeElement;
    head.current?.focus({ preventScroll: true });
    return () => { if (back.current instanceof HTMLElement && document.contains(back.current)) back.current.focus({ preventScroll: true }); };
  }, []);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || document.querySelector(".rf-pal-wrap")) return;
      e.preventDefault();
      close();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [close]);

  return (
    <ViewTransition enter="rf-sheet-in" exit="rf-sheet-out" default="none">
      <div className="rf-sheet-wrap">
          <div className="rf-sheet-scrim" onClick={close} aria-hidden="true" />
          <aside className="rf-sheet" role="dialog" aria-modal="false" aria-labelledby="rf-sheet-h">
            <div className="rf-sheet-head">
              <h2 id="rf-sheet-h" ref={head} tabIndex={-1}>{tr(locale, "tm_panel")}</h2>
              {/* 전체 화면은 일부러 새로 불러온다 — 같은 주소를 화면 안에서 열면 다시 패널로 열린다 */}
              <a className="rf-icon-btn" href={path}><Maximize2 size={15} strokeWidth={1.75} aria-hidden="true" />{tr(locale, "tm_full")}</a>
              <button type="button" className="rf-icon-btn" onClick={close} aria-label={tr(locale, "tm_close")} aria-keyshortcuts="Escape"><X size={18} strokeWidth={1.75} aria-hidden="true" /></button>
            </div>
            <div className="rf-sheet-body">{children}</div>
          </aside>
      </div>
    </ViewTransition>
  );
}
