import type { Locale } from "@/lib/i18n";
import { L, fmtDate, sourceName } from "@/lib/labels";
import type { Evidence } from "@/lib/types";

/* 출처 목록. 제목은 원문 그대로(번역하지 않음). */
export function SourceList({ sources, locale, compact = false }: { sources: Evidence[]; locale: Locale; compact?: boolean }) {
  const kind = L(locale).evidenceKind;
  return (
    <ul className={compact ? "space-y-1" : "divide-y divide-hairline-soft"}>
      {sources.map((e) => (
        <li key={e.evidence_id} className={compact ? "text-[13px]" : "py-3 text-[14px]"}>
          <span className="text-steel">{kind[e.kind]} · {sourceName(locale, e.source_domain)} · {fmtDate(e.observed_at)}</span>
          <span className="mx-2 text-hairline-strong" aria-hidden>|</span>
          <a href={e.url} target="_blank" rel="noreferrer noopener" className="text-link-blue hover:underline">{e.title}</a>
          {!compact && e.excerpt && <p className="mt-1 text-[14px] text-charcoal">{e.excerpt}</p>}
        </li>
      ))}
    </ul>
  );
}
