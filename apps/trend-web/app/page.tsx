import type { Metadata } from "next";
import { MakeFlow } from "@/components/make-flow";
import { getKeywordBoard, isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { MAKE_MARKETS } from "@/lib/reader";
import { getReader, getViewer } from "@/lib/reader-server";

// 탭·화면 낭독기가 화면을 가를 수 있게 화면마다 제목을 둔다
export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "mk_title")} — ${t(locale, "site")}` };
}

/* 첫 화면 — 만들기 (Plan 20, 시안 n-redesign). 시장은 한국·일본·영어권. 시장 버튼의 '확인된 말' 은 대시보드 카드 수(지역마다).
   승인 표지의 이름은 로그인한 사람의 것(없으면 '검수자'). 트렌드는 여기서 펼치지 않는다(둘러보기 /trends). */
export default async function MakePage() {
  const locale = await getLocale();
  const [viewer, reader] = await Promise.all([getViewer(), getReader()]);
  let counts: Record<string, number> = {};
  try {
    counts = (await getKeywordBoard([...MAKE_MARKETS], 1)).counts;
  } catch {
    counts = {};                       // 숫자만 비고 화면은 연다
  }
  return (
    <main id="main" className="n-main">
      <MakeFlow key={locale} locale={locale} counts={counts} reviewer={viewer ? reader.nick ?? viewer.user : null} sample={isSampleMode} />
    </main>
  );
}
