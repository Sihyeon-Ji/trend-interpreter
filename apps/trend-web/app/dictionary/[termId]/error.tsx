"use client";

import { useSyncExternalStore } from "react";
import { localeOf, type Locale } from "@/lib/i18n";

const noop = () => () => {};
const TEXT: Record<Locale, { failed: string; retry: string }> = {
  ko: { failed: "이 항목을 불러오지 못했어요.", retry: "다시 불러오기" },
  en: { failed: "Couldn't load this entry.", retry: "Try again" },
  ja: { failed: "この項目を読み込めませんでした。", retry: "もう一度読み込む" },
};

/* 사전 항목을 불러오지 못했을 때 — 무엇이 안 됐는지 말하고 다시 부를 단추를 준다(언어는 문서의 lang 을 따른다) */
export default function TermError({ retry }: { error: Error; retry: () => void }) {
  const text = TEXT[useSyncExternalStore(noop, () => localeOf(document.documentElement.lang), (): Locale => "ko")];
  return (
    <main id="main" className="rs-main" tabIndex={-1}>
      <section className="rs-stage rs-stage-empty" role="alert">
        <h1 className="rs-lede">{text.failed}</h1>
        <button type="button" className="rs-btn" data-kind="primary" onClick={() => retry()}>{text.retry}</button>
      </section>
    </main>
  );
}
