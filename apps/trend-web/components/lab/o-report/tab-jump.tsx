"use client";

/* 머리 문장·지난 방문 줄에서 목록의 탭으로 곧장 — 스크립트가 있으면 새로 불러오지 않고 탭만 바꿔 목록으로 내려가고,
   없으면 주소(?tab=…#or-board)로 서버가 같은 화면을 그린다. */
import type { ListKey } from "@/lib/lab/o-report";

export function jumpToTab(tab: ListKey) {
  window.dispatchEvent(new CustomEvent("or-tab", { detail: tab }));
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.getElementById("or-board")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
}

export function TabJump({ tab, href, className, children }: { tab: ListKey; href: string; className?: string; children: React.ReactNode }) {
  return (
    <a href={href} className={className}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        jumpToTab(tab);
      }}>
      {children}
    </a>
  );
}
