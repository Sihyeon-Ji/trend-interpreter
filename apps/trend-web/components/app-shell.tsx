import { ShellChrome } from "@/components/shell-chrome";
import { Sidebar } from "@/components/sidebar";
import { t, type Locale } from "@/lib/i18n";

/* 앱 틀 (docs/트렌드/디자인-개편.md): 왼쪽 메뉴(휴대폰은 위 막대 + 서랍)와 내용. 페이지는 <main id="main"> 을 스스로 그린다.
   디자인 시안(/lab/*)에서는 겉을 빼고 내용만 둔다(ShellChrome). */
export function AppShell({ locale, sample, signedIn, nick, reviewer, children }: {
  locale: Locale; sample: boolean; signedIn: boolean; nick: string | null; reviewer: boolean; children: React.ReactNode;
}) {
  return (
    <ShellChrome
      skip={<a href="#main" className="sr-only z-50 rounded-md bg-background px-3 py-2 text-[14px] text-ink focus:not-sr-only focus:fixed focus:left-3 focus:top-3">{t(locale, "skip_to_main")}</a>}
      sidebar={<Sidebar locale={locale} signedIn={signedIn} nick={nick} reviewer={reviewer} />}
      banner={sample ? <p className="border-b border-hairline bg-surface px-4 py-2 text-[13px] text-charcoal sm:px-6 lg:px-8">{t(locale, "sample_banner")}</p> : null}
      footer={<footer className="mt-auto border-t border-hairline px-4 py-5 text-[13px] text-steel sm:px-6 lg:px-8">© 2026 {t(locale, "site")}</footer>}>
      {children}
    </ShellChrome>
  );
}
