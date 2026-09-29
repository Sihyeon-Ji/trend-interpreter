import type { Metadata } from "next";
import Link from "next/link";
import "./f-editorial.css";
import { fe } from "@/lib/lab/f-editorial-copy";
import { getLocale } from "@/lib/locale";

/* 시안 F — 에디토리얼. 앱 틀은 /lab 아래에서 그려지지 않으므로 여기서 틀(제호는 판을 알아야 해서 화면이, 바닥글은 여기)을 그린다.
   스타일은 f-editorial.css 한 장, 선택자는 전부 .lab-f-editorial 아래. */
export const metadata: Metadata = { title: "트렌드 통역 주간, 시안 F" };

export default async function EditorialLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return (
    <div className="lab-f-editorial">
      <a href="#fe-main" className="fe-skip">{fe(locale, "skip")}</a>
      <div className="fe-main">{children}</div>
      <footer className="fe-footer">
        <div className="fe-wrap fe-footer__row">
          <span>{fe(locale, "footer_sources")}</span>
          <span className="fe-footer__right">
            <span>{fe(locale, "footer_draft")}</span>
            <Link href="/lab">{fe(locale, "drafts")}</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
