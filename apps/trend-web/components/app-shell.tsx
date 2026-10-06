import Link from "next/link";
import { ShellChrome } from "@/components/shell-chrome";
import { TopBar } from "@/components/top-bar";
import { t, type Locale } from "@/lib/i18n";

/* 앱 틀 (Plan 20 A안, 시안 f-report): 위 막대(휴대폰은 메뉴 단추 + 서랍)와 내용. 페이지는 <main id="main"> 을 스스로 그린다.
   디자인 시안(/lab/*)에서는 겉을 빼고 내용만 둔다(ShellChrome). */
export function AppShell({ locale, sample, signedIn, nick, reviewer, children }: {
  locale: Locale; sample: boolean; signedIn: boolean; nick: string | null; reviewer: boolean; children: React.ReactNode;
}) {
  return (
    <ShellChrome
      skip={<a href="#main" className="sr-only z-50 rounded-md bg-background px-3 py-2 text-[14px] text-ink focus:not-sr-only focus:fixed focus:left-3 focus:top-3">{t(locale, "skip_to_main")}</a>}
      sidebar={<TopBar locale={locale} signedIn={signedIn} nick={nick} reviewer={reviewer} />}
      banner={sample ? <p className="border-b border-hairline bg-surface print:hidden"><span className="mx-auto block max-w-[1280px] px-4 py-2 text-[13px] text-charcoal sm:px-6 xl:px-8">{t(locale, "sample_banner")}</span></p> : null}
      footer={<footer className="mt-auto border-t border-hairline print:hidden"><div className="mx-auto flex max-w-[1280px] flex-wrap items-center gap-x-4 gap-y-1 px-4 py-5 text-[13px] text-steel sm:px-6 xl:px-8"><span>© 2026 {t(locale, "site")}</span><Link href="/about" className="hover:text-ink hover:underline">{t(locale, "about_title")}</Link></div></footer>}>
      {children}
    </ShellChrome>
  );
}
