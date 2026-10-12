"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial/copy";

const noop = () => () => {};
const readLocale = (): Locale => (document.documentElement.lang === "en" ? "en" : "ko");

/* 자료 서버가 답하지 않을 때 — 예시 데이터로 바꾸지 않고 그렇다고 말한다. */
export default function IssueError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const locale = useSyncExternalStore(noop, readLocale, (): Locale => "ko");
  return (
    <div className="fe-wrap fe-state">
      <h1>{fe(locale, "error_title")}</h1>
      <p>{fe(locale, "error_body")}</p>
      <button type="button" className="fe-btn fe-btn--primary" onClick={reset}>{fe(locale, "error_retry")}</button>
      <p><Link href="/lab" className="fe-link">{fe(locale, "drafts")}</Link></p>
    </div>
  );
}
