"use client";

import { useSyncExternalStore } from "react";
import { StatePanel } from "@/components/state-panel";
import { Button } from "@/components/ui/button";
import { t, type Locale } from "@/lib/i18n";

const noop = () => () => {};
/** 오류 화면은 클라이언트 컴포넌트라 서버의 언어 쿠키를 못 읽는다 — 루트 레이아웃이 단 <html lang> 을 따른다. */
const useLocale = (): Locale => useSyncExternalStore(noop, () => (document.documentElement.lang === "en" ? "en" : "ko"), () => "ko");

/* 관리 목록을 못 읽었을 때. 예시 데이터로 바꾸지 않는다 — 머리와 탭은 레이아웃이 그대로 두고, 다시 불러오기만 준다. */
export default function AdminError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const locale = useLocale();
  return (
    <StatePanel role="alert" action={<Button variant="outline" className="h-8 rounded-md border-hairline-strong px-3 shadow-none" onClick={() => retry()}>{t(locale, "adm_retry")}</Button>}>
      {t(locale, "adm_load_failed")}
    </StatePanel>
  );
}
