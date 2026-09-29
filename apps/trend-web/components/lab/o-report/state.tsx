"use client";

/* 불러오기 실패·기다림 화면. 오류 경계는 클라이언트라 쿠키를 읽지 못한다 — 루트 레이아웃이 <html lang> 에 넣은 화면 언어를 따른다. */
import { useSyncExternalStore } from "react";
import type { Locale } from "@/lib/i18n";
import { tr } from "@/lib/lab/o-report-copy";

const noop = () => () => {};
const readLocale = (): Locale => (document.documentElement.lang === "en" ? "en" : "ko");
export const useDocLocale = () => useSyncExternalStore(noop, readLocale, (): Locale => "ko");

export function ErrorState({ retry }: { retry: () => void }) {
  const locale = useDocLocale();
  return (
    <div className="mx-auto max-w-[1320px] px-5 py-16 sm:px-8 sm:py-24" role="alert">
      <h1 className="text-[24px] leading-tight font-extrabold tracking-[-0.03em] sm:text-[36px]">{tr(locale, "error_title")}</h1>
      <p className="mt-3 max-w-[560px] text-[16px] leading-[1.6] text-[var(--or-slate)]">{tr(locale, "error_body")}</p>
      <button type="button" onClick={() => retry()} className="mt-6 inline-flex h-11 items-center rounded-[6px] bg-[var(--or-ink)] px-5 text-[14px] font-semibold text-white">
        {tr(locale, "error_retry")}
      </button>
    </div>
  );
}
