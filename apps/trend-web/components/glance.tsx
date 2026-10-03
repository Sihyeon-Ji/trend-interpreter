import Link from "next/link";
import { t, type Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import type { Briefing } from "@/lib/types";

/* 대시보드 맨 위 '한눈에 보기' — 고른 시장에서 지금 바로 써도 되는 밈 몇 개와, 조심·쓰지 말 것·판단 전의 건수.
   목록(근거 화면)까지 내려가지 않아도 '지금 뭘 쓸 수 있나' 가 첫 화면에 보이게 한다. 수는 브리핑과 같은 규칙(briefing.build). */
const TOP = 5;

export function Glance({ b, locale, regions }: { b: Briefing; locale: Locale; regions: string[] }) {
  const q = regions.length ? `?regions=${regions.join(",")}` : "";
  const stats = [
    { label: t(locale, "glance_use_now"), n: b.counts.use_now },
    { label: t(locale, "glance_careful"), n: b.counts.careful },
    { label: t(locale, "glance_avoid"), n: b.counts.avoid },
    { label: t(locale, "glance_undecided"), n: b.counts.undecided },
  ];
  return (
    <section aria-labelledby="glance-title" className="rounded-md border border-hairline-strong p-4 space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="glance-title" className="text-[15px] font-semibold text-ink">{t(locale, "glance_title")}</h2>
        <span className="text-[13px] text-steel">{t(locale, "glance_basis").replace("{n}", b.counts.rising.toLocaleString())}</span>
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label}>
            <dt className="text-[13px] text-steel">{s.label}</dt>
            <dd className="text-[22px] font-semibold tabular-nums text-ink">{s.n.toLocaleString()}</dd>
          </div>
        ))}
      </dl>
      <div>
        <p className="text-[13px] text-steel">{t(locale, "glance_top")}</p>
        {b.use_now.length ? (
          <ul className="mt-1.5 flex flex-wrap gap-2">
            {b.use_now.slice(0, TOP).map((c) => (
              <li key={c.term_id}>
                <Link href={`/dictionary/${c.term_id}${q}`} lang={langTag(c.lang)}
                  className="inline-flex h-8 items-center rounded-md border border-hairline-strong px-3 text-[14px] font-medium text-ink hover:border-ink">
                  {c.canonical}
                </Link>
              </li>
            ))}
          </ul>
        ) : <p className="mt-1 text-[14px] text-charcoal">{t(locale, "glance_none")}</p>}
      </div>
      <Link href={`/briefing${q}`} className="inline-block text-[14px] text-link-blue hover:underline">{t(locale, "glance_more")} →</Link>
    </section>
  );
}
