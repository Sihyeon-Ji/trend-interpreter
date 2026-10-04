import Link from "next/link";
import { RiskCell, StageCell } from "@/components/term-status";
import type { UpdateRow } from "@/lib/data";
import { t, type Locale } from "@/lib/i18n";
import { isCountryCode, whyAnchor } from "@/lib/country";
import { langTag, scriptLang } from "@/lib/lang";
import { regionLabel } from "@/lib/labels";
import { glossFor } from "@/lib/gloss";

/* 최근 변화 표. 날짜는 묶음 행으로 올리고 행에는 시각만 — 매 행 같은 날짜를 되풀이해 휴대폰에서 이름 칸이 좁았다(화면 개편 2차 검토).
   뜻·단계·리스크·지역은 대시보드 카드에서 온다(없으면 '—'). 목적지가 있는 행만 표현이 링크이고 hover 바탕이 생긴다. */

const tz = (locale: Locale) => (locale === "ko" ? "Asia/Seoul" : "UTC");   // fmtDateTime 과 같은 기준
const parts = (iso: string, locale: Locale, opts: Intl.DateTimeFormatOptions) => {
  const p = new Intl.DateTimeFormat("en-CA", { timeZone: tz(locale), hour12: false, ...opts }).formatToParts(new Date(iso));
  return (type: string) => p.find((x) => x.type === type)?.value ?? "";
};
const dayKey = (iso: string, locale: Locale) => {
  const g = parts(iso, locale, { year: "numeric", month: "2-digit", day: "2-digit" });
  return `${g("year")}-${g("month")}-${g("day")}`;
};
const hhmm = (iso: string, locale: Locale) => {
  const g = parts(iso, locale, { hour: "2-digit", minute: "2-digit" });
  return `${g("hour")}:${g("minute")}`;
};
function dayLabel(key: string, locale: Locale, today: string, yesterday: string) {
  const [y, m, d] = key.split("-").map(Number);
  const date = locale === "ko" ? `${m}월 ${d}일`
    : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(y, m - 1, d)));
  if (key === today) return t(locale, "updates_today").replace("{date}", date);
  if (key === yesterday) return t(locale, "updates_yesterday").replace("{date}", date);
  return date;
}

export const rowRegions = (r: UpdateRow) => (r.region ? [r.region] : r.card?.regions ?? []);

const href = (r: UpdateRow) =>
  r.term_id ? `/dictionary/${r.term_id}`
    : r.kind === "spike" && r.region && isCountryCode(r.region) ? `/country/${r.region}?tab=why#${encodeURIComponent(whyAnchor(r.label))}` : null;

const labelLang = (r: UpdateRow) => (r.card ? langTag(r.card.lang) : scriptLang(r.label, r.region));
const gloss = (r: UpdateRow, locale: Locale) => (r.card ? glossFor(r.card, locale) || t(locale, "dict_pending") : null);
const Dash = () => <span className="text-steel">—</span>;

/** 뜻 또는 이유. 뜻 바뀜은 '이전 뜻'·'지금 뜻' 두 줄(이전 뜻은 번역이 없어 원문), 검색 급증은 이유 한 문장. */
function Meaning({ r, locale, clamp }: { r: UpdateRow; locale: Locale; clamp: string }) {
  if (r.kind === "spike") {
    const why = r.reason?.[locale];
    return why ? <p className={clamp} title={why}>{why}</p> : <Dash />;
  }
  const now = gloss(r, locale);
  if (r.kind === "meaning_changed") {
    return (
      <dl className="space-y-0.5">
        {r.previous && (
          <div className="flex gap-2"><dt className="shrink-0 text-steel">{t(locale, "updates_before")}</dt>
            <dd lang={r.card ? langTag(r.card.lang) : undefined} className={`min-w-0 ${clamp}`} title={r.previous}>{r.previous}</dd></div>
        )}
        <div className="flex gap-2"><dt className="shrink-0 text-steel">{t(locale, "updates_now")}</dt>
          <dd className={`min-w-0 ${clamp}`} title={now ?? undefined}>{now ?? "—"}</dd></div>
      </dl>
    );
  }
  return now ? <p className={clamp} title={now}>{now}</p> : <Dash />;
}

function Name({ r, className }: { r: UpdateRow; className: string }) {
  const to = href(r);
  return to ? <Link href={to} lang={labelLang(r)} className={`${className} hover:underline`}>{r.label}</Link>
    : <span lang={labelLang(r)} className={className}>{r.label}</span>;
}

const regionsText = (r: UpdateRow, locale: Locale) => rowRegions(r).map((x) => regionLabel(locale, x)).join(", ");

export function UpdatesTable({ rows, locale, now }: { rows: UpdateRow[]; locale: Locale; now: string }) {
  const today = dayKey(now, locale);
  const yesterday = dayKey(new Date(Date.parse(now) - 86_400_000).toISOString(), locale);
  const groups: { key: string; rows: UpdateRow[] }[] = [];
  for (const r of rows) {
    const key = dayKey(r.at, locale);
    const g = groups.at(-1);
    if (g && g.key === key) g.rows.push(r);
    else groups.push({ key, rows: [r] });
  }
  const change = (r: UpdateRow) => t(locale, `updates_change_${r.kind}` as "updates_change_verified");
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[960px] border-collapse text-left">
          <caption className="sr-only">{t(locale, "updates_table_caption")}</caption>
          <thead>
            <tr className="border-b border-hairline text-[13px] text-steel">
              <th scope="col" className="w-[64px] py-2.5 pr-4 font-medium">{t(locale, "updates_col_time")}</th>
              <th scope="col" className="w-[104px] py-2.5 pr-4 font-medium">{t(locale, "updates_col_change")}</th>
              <th scope="col" className="w-[240px] py-2.5 pr-4 font-medium">{t(locale, "dash_col_keyword")}</th>
              <th scope="col" className="py-2.5 pr-4 font-medium">{t(locale, "updates_col_meaning")}</th>
              <th scope="col" className="w-[110px] py-2.5 pr-4 font-medium">{t(locale, "updates_col_region")}</th>
              <th scope="col" className="w-[180px] py-2.5 pr-4 font-medium">{t(locale, "dash_col_stage")}</th>
              <th scope="col" className="w-[120px] py-2.5 font-medium">{t(locale, "dash_col_risk")}</th>
            </tr>
          </thead>
          {groups.map((g) => (
            <tbody key={g.key}>
              <tr className="border-b border-hairline bg-surface-soft">
                <th scope="rowgroup" colSpan={7} className="py-2 pl-3 text-[13px] font-medium text-charcoal">{dayLabel(g.key, locale, today, yesterday)}</th>
              </tr>
              {g.rows.map((r, i) => (
                <tr key={`${r.kind}-${r.label}-${i}`} className={`border-b border-hairline align-top${href(r) ? " hover:bg-surface-soft" : ""}`}>
                  <td className="py-3 pr-4 text-[13px] tabular-nums text-steel"><time dateTime={r.at}>{hhmm(r.at, locale)}</time></td>
                  <td className="py-3 pr-4 text-[13px] text-charcoal">{change(r)}</td>
                  <td className="py-3 pr-4"><Name r={r} className="text-[15px] font-semibold text-ink" /></td>
                  <td className="max-w-0 py-3 pr-4 text-[14px] text-charcoal"><Meaning r={r} locale={locale} clamp="truncate" /></td>
                  <td className="py-3 pr-4 text-[13px] text-charcoal">{regionsText(r, locale) || <Dash />}</td>
                  <td className="py-3 pr-4">{r.card ? <StageCell diffusion={r.card.diffusion} lifecycle={r.card.lifecycle} locale={locale} /> : <Dash />}</td>
                  <td className="py-3">{r.card ? <RiskCell item={r.card} locale={locale} /> : <Dash />}</td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>

      <div className="border-b border-hairline md:hidden">
        {groups.map((g) => (
          <section key={g.key} aria-label={dayLabel(g.key, locale, today, yesterday)}>
            <h3 className="border-b border-hairline bg-surface-soft px-3 py-2 text-[13px] font-medium text-charcoal">{dayLabel(g.key, locale, today, yesterday)}</h3>
            <ul className="divide-y divide-hairline">
              {g.rows.map((r, i) => (
                <li key={`${r.kind}-${r.label}-${i}`} className="py-3.5">
                  <div className="flex items-start gap-3">
                    <Name r={r} className="min-w-0 flex-1 text-[16px] font-semibold text-ink" />
                    {r.card && <RiskCell item={r.card} locale={locale} />}
                    <time dateTime={r.at} className="shrink-0 pt-0.5 text-[13px] tabular-nums text-steel">{hhmm(r.at, locale)}</time>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-steel">
                    <span className="text-charcoal">{change(r)}</span>
                    {regionsText(r, locale) && <span>{t(locale, "updates_col_region")} <span className="text-ink">{regionsText(r, locale)}</span></span>}
                  </div>
                  <div className="mt-1 text-[14px] leading-[1.5] text-charcoal"><Meaning r={r} locale={locale} clamp="line-clamp-2" /></div>
                  {r.card && <div className="mt-2"><StageCell diffusion={r.card.diffusion} lifecycle={r.card.lifecycle} locale={locale} /></div>}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
