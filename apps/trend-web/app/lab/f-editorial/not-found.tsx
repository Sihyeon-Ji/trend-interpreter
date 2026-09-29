import Link from "next/link";
import { fe } from "@/lib/lab/f-editorial-copy";
import { issueHref } from "@/lib/lab/f-editorial";
import { getLocale } from "@/lib/locale";

export default async function NotFound() {
  const locale = await getLocale();
  return (
    <div className="fe-wrap fe-state">
      <h1>{fe(locale, "not_found_title")}</h1>
      <p>{fe(locale, "not_found")}</p>
      <Link href={issueHref("KR")} className="fe-btn fe-btn--primary">{fe(locale, "not_found_back")}</Link>
    </div>
  );
}
