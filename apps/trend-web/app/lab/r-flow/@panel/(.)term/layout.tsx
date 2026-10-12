import { Sheet } from "@/components/lab/r-flow/sheet";
import { getLabLocale as getLocale } from "@/lib/locale";

/* 밈 자세히를 옆 패널로 — 목록·초안 화면 안에서 밈을 누르면 이 길이 가로챈다. 주소를 새로 열면 전체 화면(term/[termId])이 뜬다.
   패널 틀은 밈을 바꿔도 남아 있어(이 레이아웃) 다시 미끄러져 들어오지 않고 내용만 바뀐다. */
export default async function PanelTermLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return <Sheet locale={locale}>{children}</Sheet>;
}
