import type { Metadata } from "next";
import { Footer, Masthead } from "@/components/lab/o-editorial/frame";
import { getMeta, isSampleMode } from "@/lib/data";
import { getLabLocale as getLocale } from "@/lib/locale";
import "./editorial.css";

/* 디자인 시안 '에디토리얼형' — 마케터를 위한 주간 밈 잡지. 앱 틀(왼쪽 메뉴)은 /lab 에서 그리지 않으므로 틀(머리·발)을 여기서 그린다.
   이 시안의 문구·계산은 lib/lab/o-editorial.ts, 데이터는 lib/lab/o-editorial-data.ts. 공용 파일은 읽기만 한다. */

export const metadata: Metadata = {
  title: "이번 주 밈 | 트렌드 통역 (시안: 에디토리얼형)",
  robots: { index: false },
};

export default async function EditorialLayout({ children }: { children: React.ReactNode }) {
  const [locale, meta] = await Promise.all([getLocale(), getMeta().catch(() => null)]);
  return (
    <div className="lab-o-editorial" lang={locale}>
      <Masthead locale={locale} />
      <main id="oe-main" tabIndex={-1} style={{ outline: "none" }}>{children}</main>
      <Footer locale={locale} updatedAt={meta?.last_run ?? null} sample={isSampleMode} />
    </div>
  );
}
