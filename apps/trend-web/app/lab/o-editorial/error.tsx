"use client";

import { useSyncExternalStore } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { copy } from "@/lib/lab/o-editorial";

/* 이번 주 호를 불러오지 못했을 때 — 예시로 바꿔 넣지 않고, 무엇이 안 됐는지와 다시 불러오기를 준다.
   오류 화면은 쿠키를 못 읽으니 루트가 <html lang> 에 넣은 화면 언어를 따른다. */
const noop = () => () => {};
const readLocale = (): Locale => (document.documentElement.lang === "en" ? "en" : "ko");

export default function EditorialError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const locale = useSyncExternalStore(noop, readLocale, (): Locale => "ko");
  const c = copy(locale);
  return (
    <div className="oe-wrap" style={{ paddingBlock: 48 }}>
      <div className="oe-state" role="alert">
        <p>{c.loadFailed}</p>
        <p style={{ marginTop: 16 }}><button type="button" className="oe-btn oe-btn-line" onClick={() => retry()}>{c.retry}</button></p>
      </div>
    </div>
  );
}
