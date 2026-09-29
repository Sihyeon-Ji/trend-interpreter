import { t, type Locale } from "@/lib/i18n";
import { fmtDate, sourceName } from "@/lib/labels";
import type { Meaning, TermRecord } from "@/lib/types";

/* 사전 항목의 '기록' — 처음 쓰인 때부터 쓸 때 조심 재확인까지 한 표, 최신이 위. 판 번호와 다음 확인 예정일은 내지 않는다
   (예정일이 이미 지나 보이고, 판 번호는 내부 말이다 — 개편 검토 2차). 뜻 원문은 한국어라 영어 화면에서도 lang="ko". */
type Row = { at: string; what: string; detail?: { label: string; text: string } };

const FIELD = {
  ko: { definition: "뜻", nuance: "쓰임", origin: "유래", generations: "쓰는 세대", regions: "쓰이는 곳" },
  en: { definition: "meaning", nuance: "usage", origin: "origin", generations: "age groups", regions: "regions" },
} as const;

function changed(prev: Meaning, m: Meaning, locale: Locale): string[] {
  const f = FIELD[locale];
  const out: string[] = [];
  if (prev.definition !== m.definition) out.push(f.definition);
  if (prev.nuance !== m.nuance) out.push(f.nuance);
  if (prev.origin !== m.origin) out.push(f.origin);
  if (prev.generations.join() !== m.generations.join()) out.push(f.generations);
  if (prev.regions.join() !== m.regions.join()) out.push(f.regions);
  return out;
}

export function historyRows(record: TermRecord, locale: Locale, riskResult: string | null): Row[] {
  const rows: Row[] = [];
  const term = record.term;
  if (term.first_seen) rows.push({ at: term.first_seen, what: t(locale, "term_h_first_used") });
  const firstEv = [...record.evidences].sort((a, b) => a.observed_at.localeCompare(b.observed_at))[0];
  if (firstEv) rows.push({ at: firstEv.observed_at, what: `${t(locale, "term_h_first_source")} (${sourceName(locale, firstEv.source_domain)})` });
  const ms = [...record.meanings].sort((a, b) => a.version - b.version);
  ms.forEach((m, i) => {
    const prev = ms[i - 1];
    if (m.verification === "rejected") rows.push({ at: m.valid_from, what: t(locale, "term_h_rejected") });
    else if (!prev) rows.push({ at: m.valid_from, what: t(locale, m.verification?.startsWith("verified") ? "term_h_published" : "term_h_recorded") });
    else {
      const what = changed(prev, m, locale);
      const old = prev.definition !== m.definition ? prev.definition : prev.nuance !== m.nuance ? prev.nuance : prev.origin !== m.origin ? prev.origin : "";
      rows.push({ at: m.valid_from, what: `${t(locale, "term_h_changed")}${what.length ? `: ${what.join(", ")}` : ""}`,
        detail: old ? { label: t(locale, "term_h_prev"), text: old } : undefined });
    }
  });
  const riskAt = term.risk_human ? term.risk_decided_at : term.risk_checked_at;
  if (riskAt && riskResult) rows.push({ at: riskAt, what: `${t(locale, term.risk_human ? "term_h_risk_human" : "term_h_risk")}: ${riskResult}` });
  return rows.sort((a, b) => b.at.localeCompare(a.at));
}

export function EntryHistory({ rows, locale }: { rows: Row[]; locale: Locale }) {
  if (!rows.length) return null;
  return (
    <div className="space-y-2">
      <table className="w-full border-collapse text-left text-[14px]">
        <thead>
          <tr className="border-b border-hairline text-[13px] text-steel">
            <th scope="col" className="w-[104px] py-2 pr-4 font-medium">{t(locale, "term_col_date")}</th>
            <th scope="col" className="py-2 font-medium">{t(locale, "term_col_what")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-hairline align-top">
              <td className="py-2.5 pr-4 tabular-nums text-charcoal">{fmtDate(r.at)}</td>
              <td className="py-2.5 text-ink">
                {r.what}
                {r.detail && (
                  <details className="mt-1 text-[13px]">
                    <summary className="w-fit cursor-pointer text-link-blue hover:underline">{r.detail.label}</summary>
                    <p lang="ko" className="mt-1 leading-[1.55] text-charcoal">{r.detail.text}</p>
                  </details>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {locale === "en" && rows.some((r) => r.detail) && <p className="text-[13px] text-steel">{t(locale, "term_original_note")}</p>}
    </div>
  );
}
