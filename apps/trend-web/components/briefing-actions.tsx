"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { t, type Locale } from "@/lib/i18n";

/** 브리핑 보고서의 작업 — 브라우저 인쇄로 PDF 저장(인쇄할 때 메뉴·버튼은 숨는다), 지금 주소를 복사해 공유(지역은 주소에 있다). */
export function BriefingActions({ locale }: { locale: Locale }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <span className="flex flex-wrap items-center gap-2 print:hidden">
      <Button type="button" variant="outline" className="h-9 rounded-md px-3.5 text-[14px]" onClick={() => void copy()}>{t(locale, "brief_copy_link")}</Button>
      <Button type="button" className="h-9 rounded-md px-3.5 text-[14px]" onClick={() => window.print()}>{t(locale, "brief_print")}</Button>
      <span aria-live="polite" className="text-[13px] text-steel">{copied ? t(locale, "brief_copied") : ""}</span>
    </span>
  );
}
