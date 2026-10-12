"use client";

import { useRouter } from "next/navigation";
import { LAB_LOCALES as LOCALES, LOCALE_NAME, setLocaleCookie, type LabLocale as Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial/copy";

/* 화면 언어 — 앱과 같은 쿠키를 쓴다(lib/i18n.setLocaleCookie). 모양만 시안의 것. */
export function LangSwitch({ locale }: { locale: Locale }) {
  const router = useRouter();
  return (
    <span className="fe-lang" role="group" aria-label={fe(locale, "lang")}>
      {LOCALES.map((l, i) => (
        <span key={l} className="fe-lang">
          {i > 0 && <span className="fe-lang__sep" aria-hidden>|</span>}
          <button type="button" aria-pressed={l === locale} lang={l} onClick={() => { setLocaleCookie(l); router.refresh(); }}>{LOCALE_NAME[l]}</button>
        </span>
      ))}
    </span>
  );
}
