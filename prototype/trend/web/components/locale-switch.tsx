"use client";

import { useRouter } from "next/navigation";
import { LOCALES, LOCALE_NAME, setLocaleCookie, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function LocaleSwitch({ locale }: { locale: Locale }) {
  const router = useRouter();
  const set = (l: Locale) => {
    setLocaleCookie(l);
    router.refresh();
  };
  return (
    <div className="flex items-center gap-2 text-[13px]" role="group" aria-label="Language">
      {LOCALES.map((l, i) => (
        <span key={l} className="flex items-center gap-2">
          {i > 0 && <span className="text-hairline-strong" aria-hidden>|</span>}
          <button type="button" onClick={() => set(l)} aria-pressed={l === locale} className={cn("hover:text-ink", l === locale ? "font-medium text-ink" : "text-steel")}>
            {LOCALE_NAME[l]}
          </button>
        </span>
      ))}
    </div>
  );
}
