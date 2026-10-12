"use client";

import { useRouter } from "next/navigation";
import { setLocaleCookie, type LabLocale as Locale } from "@/lib/i18n";
import { tr } from "@/lib/lab/o-report/copy";

/** 한국어 / EN — 쿠키만 바꾸고 서버 그림을 다시 받는다(앱의 언어 전환과 같은 쿠키) */
export function LocaleToggle({ locale }: { locale: Locale }) {
  const router = useRouter();
  const set = (l: Locale) => { if (l !== locale) { setLocaleCookie(l); router.refresh(); } };
  const opts: { l: Locale; label: string; lang: string }[] = [{ l: "ko", label: "한국어", lang: "ko" }, { l: "en", label: "EN", lang: "en" }];
  return (
    <div role="group" aria-label={tr(locale, "lang_group")} className="flex items-center rounded-[6px] border border-[var(--or-line-strong)] p-0.5">
      {opts.map((o) => (
        <button key={o.l} type="button" lang={o.lang} onClick={() => set(o.l)} aria-pressed={o.l === locale}
          className={`h-8 rounded-[4px] px-2.5 text-[13px] ${o.l === locale ? "bg-[var(--or-ink)] font-semibold text-white" : "text-[var(--or-slate)] hover:text-[var(--or-ink)]"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
