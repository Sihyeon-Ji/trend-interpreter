"use client";

import { useSyncExternalStore } from "react";
import type { Locale } from "@/lib/i18n";
import { c } from "@/lib/lab/f-report/copy";

const noop = () => () => {};
const readLocale = (): Locale => (document.documentElement.lang === "en" ? "en" : "ko");

/** 자료 서버가 답하지 않을 때. 언어는 <html lang> 에서 읽는다(오류 경계는 서버 쿠키를 못 본다). */
export default function FReportError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const locale = useSyncExternalStore(noop, readLocale, () => "ko" as Locale);
  return (
    <div className="fr-state" role="alert">
      <h1>{c(locale, "error_title")}</h1>
      <p>{c(locale, "error_hint")}</p>
      <button type="button" className="fr-btn is-primary" onClick={() => reset()}>{c(locale, "error_retry")}</button>
    </div>
  );
}
