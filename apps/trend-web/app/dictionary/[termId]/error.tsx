"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { PageShell } from "@/components/page-shell";
import { StatePanel } from "@/components/state-panel";
import { Button } from "@/components/ui/button";
import { t, type Locale } from "@/lib/i18n";

/* 사전 항목을 불러오지 못했을 때(api 모드에서 서버가 답하지 않음). 예시 데이터로 바꾸지 않고, 다시 불러오기를 준다.
   오류 화면은 클라이언트 컴포넌트라 쿠키를 읽지 못한다 — 루트 레이아웃이 <html lang> 에 넣은 화면 언어를 따른다. */
const noop = () => () => {};
const readLocale = (): Locale => (document.documentElement.lang === "en" ? "en" : "ko");

export default function TermError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const locale = useSyncExternalStore(noop, readLocale, (): Locale => "ko");
  return (
    <PageShell>
      <div className="space-y-6">
        <p className="text-[13px] text-steel"><Link href="/dictionary" className="hover:text-ink hover:underline">{t(locale, "dict_title")}</Link></p>
        <StatePanel role="alert" action={
          <Button type="button" variant="outline" className="h-10 rounded-md border-hairline-strong px-4 text-[14px] shadow-none" onClick={() => retry()}>
            {t(locale, "term_retry")}
          </Button>
        }>{t(locale, "term_err")}</StatePanel>
      </div>
    </PageShell>
  );
}
