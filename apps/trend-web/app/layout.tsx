import type { Metadata } from "next";
import Link from "next/link";
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";
import { SiteNav } from "@/components/site-nav";
import { isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getReader, getViewer } from "@/lib/reader-server";

export const metadata: Metadata = {
  title: "트렌드 통역 · Trend Interpreter",
  description: "유행어 사전과 메시지 해석 · A dictionary of slang and a message explainer",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const [reader, viewer] = await Promise.all([getReader(), getViewer()]);
  return (
    <html lang={locale} className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <SiteNav locale={locale} sample={isSampleMode} readerNick={reader.nick ?? null} signedIn={!!viewer} />
        {children}
        <footer className="border-t border-hairline px-4 py-5 text-[13px] text-steel sm:px-6">
          <div className="flex w-full items-center justify-between">
            <span>© 2026 {t(locale, "site")}{isSampleMode && <span className="sm:hidden"> · {t(locale, "sample_mode")}</span>}</span>
            <span className="flex gap-4"><Link href="/updates" className="hover:text-ink">{t(locale, "updates_title")}</Link></span>
          </div>
        </footer>
      </body>
    </html>
  );
}
