import { tr } from "@/lib/lab/o-report/copy";
import { getLocale } from "@/lib/locale";

/* 리포트를 기다리는 동안 — 머리와 표지 자리만 조용히. 움직이는 반짝임은 쓰지 않는다 */
export default async function ReportLoading() {
  const locale = await getLocale();
  return (
    <div className="mx-auto max-w-[1320px] px-5 pt-12 sm:px-8" aria-busy="true">
      <p className="sr-only" role="status">{tr(locale, "loading")}</p>
      <div className="h-12 w-[min(560px,80%)] rounded-[4px] bg-[var(--or-mist)]" />
      <div className="mt-5 h-5 w-[min(640px,90%)] rounded-[4px] bg-[var(--or-mist)]" />
      <div className="mt-12 grid gap-5 sm:grid-cols-3 lg:grid-cols-4">
        <div className="h-[300px] rounded-[4px] bg-[var(--or-mist)] lg:col-span-2 lg:h-[340px]" />
        <div className="hidden h-[300px] rounded-[4px] bg-[var(--or-mist)] sm:block lg:h-[340px]" />
        <div className="hidden h-[300px] rounded-[4px] bg-[var(--or-mist)] sm:block lg:h-[340px]" />
      </div>
    </div>
  );
}
