import type { Metadata } from "next";
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";
import { AppShell } from "@/components/app-shell";
import { isSampleMode } from "@/lib/data";
import { getLocale } from "@/lib/locale";
import { getReader, getViewer } from "@/lib/reader-server";

export const metadata: Metadata = {
  title: "트렌드 통역 · Trend Interpreter",
  description: "나라별로 지금 쓰이는 밈과 조심할 밈, 내 제품에 맞는 밈과 카피 · Memes in use by country, what to avoid, and copy that fits your product",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const [reader, viewer] = await Promise.all([getReader(), getViewer()]);
  return (
    <html lang={locale} className="h-full antialiased">
      <body className="min-h-full">
        <AppShell locale={locale} sample={isSampleMode} signedIn={!!viewer} nick={reader.nick ?? null} reviewer={!!viewer?.reviewer}>{children}</AppShell>
      </body>
    </html>
  );
}
