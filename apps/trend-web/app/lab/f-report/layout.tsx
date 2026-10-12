import type { Metadata } from "next";
import "./f-report.css";
import { Frame } from "@/components/lab/f-report/frame";
import { getLabLocale as getLocale } from "@/lib/locale";

export const metadata: Metadata = { title: "트렌드 리포트 · 시안 f-report" };

/** 시안 f-report — 앱 틀(사이드바)은 /lab 에서 그려지지 않으므로 여기서 자기 틀을 두른다. 스타일은 .lab-f-report 아래에만. */
export default async function FReportLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return (
    <div className="lab-f-report">
      <Frame locale={locale}>{children}</Frame>
    </div>
  );
}
