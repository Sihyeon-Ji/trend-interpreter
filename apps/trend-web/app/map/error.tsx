"use client";

import { useSyncExternalStore } from "react";
import { PageShell } from "@/components/page-shell";
import { StatePanel } from "@/components/state-panel";
import { t, type Locale } from "@/lib/i18n";

const noop = () => () => {};
/** 오류 화면은 클라이언트 컴포넌트라 서버의 언어 쿠키를 못 읽는다 — 루트 레이아웃이 단 <html lang> 을 따른다. */
const useLocale = (): Locale => useSyncExternalStore(noop, () => (document.documentElement.lang === "en" ? "en" : "ko"), () => "ko");

/* 지도 자료를 못 읽었을 때 — 예시 자료로 바꾸지 않는다(2021년 예시가 실데이터처럼 보이던 문제). */
export default function MapError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const locale = useLocale();
  return (
    <PageShell>
      <div className="space-y-6">
        <h1 className="text-[24px] leading-[1.3] font-semibold text-ink">{t(locale, "mp_title")}</h1>
        <StatePanel role="alert" action={
          <button type="button" onClick={() => retry()} className="inline-flex h-10 items-center rounded-md border border-hairline-strong bg-background px-3 text-[13px] font-medium text-ink hover:border-ink sm:h-8">
            {t(locale, "mp_retry")}
          </button>}>
          {t(locale, "mp_load_failed")}
        </StatePanel>
      </div>
    </PageShell>
  );
}
