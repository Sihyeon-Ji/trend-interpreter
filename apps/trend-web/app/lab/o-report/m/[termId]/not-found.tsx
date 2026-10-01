import Link from "next/link";
import { tr } from "@/lib/lab/o-report/copy";
import { getLocale } from "@/lib/locale";

/* 사전에 없거나 빠진 밈 — 무엇을 하면 되는지 한 문장과 돌아갈 곳 */
export default async function EntryNotFound() {
  const locale = await getLocale();
  return (
    <div className="mx-auto max-w-[1320px] px-5 py-16 sm:px-8 sm:py-24">
      <h1 className="text-[24px] leading-tight font-extrabold tracking-[-0.03em] sm:text-[36px]">{tr(locale, "not_found_title")}</h1>
      <p className="mt-3 max-w-[560px] text-[16px] leading-[1.6] text-[var(--or-slate)]">{tr(locale, "not_found_body")}</p>
      <Link href="/lab/o-report" className="mt-6 inline-flex h-11 items-center rounded-[6px] bg-[var(--or-ink)] px-5 text-[14px] font-semibold text-white">{tr(locale, "not_found_back")}</Link>
    </div>
  );
}
