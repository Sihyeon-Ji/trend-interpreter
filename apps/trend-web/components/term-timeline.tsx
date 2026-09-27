import { t, type Locale } from "@/lib/i18n";
import { fmtDate } from "@/lib/labels";
import type { TermRecord } from "@/lib/types";

/* 포착에서 확인까지 — 날짜가 있는 사건만 시간순으로. 다음 확인 예정일은 마지막 언급 + 재확인 주기. */
export function TermTimeline({ record, locale }: { record: TermRecord; locale: Locale }) {
  const ev: { at: string; label: string; note?: string }[] = [];
  if (record.term.first_seen) ev.push({ at: record.term.first_seen, label: t(locale, "term_tl_first") });
  const firstEv = [...record.evidences].sort((a, b) => a.observed_at.localeCompare(b.observed_at))[0];
  if (firstEv) ev.push({ at: firstEv.observed_at, label: t(locale, "term_tl_evidence"), note: firstEv.source_domain });
  for (const m of record.meanings) {
    const verified = m.verification?.startsWith("verified");
    ev.push({ at: m.valid_from, label: m.version > 1 ? t(locale, "term_tl_changed") : verified ? t(locale, "term_tl_verified") : t(locale, "term_tl_meaning"), note: `v${m.version}` });
  }
  if (record.term.last_seen) ev.push({ at: record.term.last_seen, label: t(locale, "term_tl_last") });
  ev.sort((a, b) => a.at.localeCompare(b.at));
  const last = ev.at(-1)?.at;  // 가장 최근 사건 기준
  const next = last ? new Date(new Date(last).getTime() + record.recheck_days * 86400000) : null;
  if (!ev.length) return null;
  return (
    <ol className="divide-y divide-hairline border-y border-hairline text-[14px]">
      {ev.map((e, i) => (
        <li key={i} className="grid grid-cols-[110px_1fr] gap-3 py-2">
          <span className="text-steel tabular-nums">{fmtDate(e.at)}</span>
          <span className="text-ink">{e.label}{e.note && <span className="ml-1.5 text-[12px] text-steel">{e.note}</span>}</span>
        </li>
      ))}
      {next && (
        <li className="grid grid-cols-[110px_1fr] gap-3 py-2">
          <span className="text-steel tabular-nums">{fmtDate(next.toISOString())}</span>
          <span className="text-charcoal">{t(locale, "term_tl_next")} <span className="text-[12px] text-steel">({record.recheck_days}{t(locale, "term_tl_days")})</span></span>
        </li>
      )}
    </ol>
  );
}
