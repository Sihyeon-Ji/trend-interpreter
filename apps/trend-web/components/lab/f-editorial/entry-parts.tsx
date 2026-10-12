import Link from "next/link";
import type { LabLocale as Locale } from "@/lib/i18n";
import { fe, words } from "@/lib/lab/f-editorial/copy";
import { entryHref, isPlaceholder, memeLabels, type SourceItem } from "@/lib/lab/f-editorial";
import { L, fmtDate, regionLabel } from "@/lib/labels";
import { scriptLang } from "@/lib/lang";
import type { Topic, TopicVariant } from "@/lib/trends/types";
import type { Meaning, Term, TermUsage } from "@/lib/types";
import { measuredUsage } from "@/lib/dictionary/regions";
import { diffusionWord, lifecycleWord, riskClass, riskReasonText, riskWord } from "./stickers";

/* 항목(기사)의 부품 — 사실 칸, 출처, 뜻의 이력, 나라별 차이. 전부 서버에서 그린다. */

export function FactRail({ term, verified, meaning, usage, lastUsed, sources, locale }: {
  term: Term; verified: boolean; meaning: Meaning | null; usage: TermUsage[]; lastUsed: string | null; sources: number; locale: Locale;
}) {
  const labels = L(locale);
  const risk = riskWord(term, locale);
  const why = risk ? (risk.key === "none" ? words(locale).riskWhy.none : riskReasonText(term, locale)?.text ?? words(locale).riskWhy[risk.key]) : null;
  const whyLang = risk && risk.key !== "none" ? riskReasonText(term, locale)?.lang : undefined;
  const measured = measuredUsage(usage);
  const generations = [...new Set(measured.map((u) => u.segment.generation))];
  const firstSeen = measured.sort((a, b) => a.first_seen.localeCompare(b.first_seen)).slice(0, 3);
  const row = (label: string, value: React.ReactNode) => (
    <div className="fe-facts__row"><dt>{label}</dt><dd>{value}</dd></div>
  );
  return (
    <aside className="fe-facts" aria-label={fe(locale, "f_stage")}>
      <dl>
        {row(fe(locale, "f_stage"), verified ? lifecycleWord(locale, term.lifecycle) : <span className="fe-muted">{fe(locale, "e_reviewing")}</span>)}
        {verified && term.diffusion && row(fe(locale, "f_spread"), diffusionWord(locale, term.diffusion))}
        {verified && risk && row(fe(locale, "f_risk"), <><span className={riskClass(risk.key)}>{risk.label}</span>{why && <span className="fe-facts__why" lang={whyLang}>{why}</span>}</>)}
        {meaning && meaning.regions.length > 0 && row(fe(locale, "f_regions"), meaning.regions.map((r) => regionLabel(locale, r)).join(", "))}
        {generations.length > 0 && row(fe(locale, "f_gens"), generations.map((g) => labels.generation[g]).join(", "))}
        {lastUsed && row(fe(locale, "f_last"), fmtDate(lastUsed))}
        {firstSeen.length > 0 && row(fe(locale, "f_first"), firstSeen.map((u) => `${regionLabel(locale, u.segment.region)} ${labels.generation[u.segment.generation]} ${fmtDate(u.first_seen)}`).join(" / "))}
        {(term.aliases?.length ?? 0) > 0 && row(fe(locale, "f_aliases"), term.aliases!.map((a, i) => <span key={a}>{i > 0 && ", "}<span lang={scriptLang(a)}>{a}</span></span>))}
        {sources > 0 && row(fe(locale, "f_sources"), <a href="#fe-sources" className="fe-link">{fe(locale, "f_sources_n", { n: sources })}</a>)}
      </dl>
    </aside>
  );
}

/** 출처 목록 — 날짜, 제목, 출처와 종류(문서·기사·영상). 같은 기사는 이미 한 번만 남아 있다(sourceItems). */
export function SourceList({ items, locale }: { items: SourceItem[]; locale: Locale }) {
  return (
    <ul className="fe-sources">
      {items.map((s) => (
        <li key={s.id}>
          <span className="fe-sources__date">{fmtDate(s.date)}</span>
          <a href={s.url} target="_blank" rel="noreferrer noopener" className="fe-sources__title" lang={s.titleLang}>{s.title}<span className="sr-only"> ({fe(locale, "new_tab")})</span></a>
          <span className="fe-sources__src">{s.source} {fe(locale, `src_${s.kind}`)}</span>
        </li>
      ))}
    </ul>
  );
}

export function MeaningHistory({ meanings, firstSeen, riskAt, locale }: { meanings: Meaning[]; firstSeen?: string | null; riskAt?: string | null; locale: Locale }) {
  const ms = [...meanings].sort((a, b) => a.version - b.version);
  const rows: { at: string; what: string; prev?: string }[] = [];
  if (firstSeen) rows.push({ at: firstSeen, what: fe(locale, "h_first_seen") });
  ms.forEach((m, i) => {
    const prev = ms[i - 1];
    if (m.verification === "rejected") rows.push({ at: m.valid_from, what: fe(locale, "h_rejected") });
    else if (!prev) rows.push({ at: m.valid_from, what: fe(locale, m.verification?.startsWith("verified") ? "h_published" : "h_recorded") });
    else rows.push({ at: m.valid_from, what: fe(locale, "h_changed"), prev: prev.definition !== m.definition ? prev.definition : prev.nuance !== m.nuance ? prev.nuance : undefined });
  });
  if (riskAt) rows.push({ at: riskAt, what: fe(locale, "h_risk") });
  rows.sort((a, b) => b.at.localeCompare(a.at));
  if (!rows.length) return null;
  return (
    <ul className="fe-history">
      {rows.map((r, i) => (
        <li key={`${r.at}-${i}`}>
          <span className="fe-history__date">{fmtDate(r.at)}</span>
          <span>{r.what}{r.prev && !isPlaceholder(r.prev) && <span className="fe-history__prev" lang="ko"><br />{fe(locale, "ch_prev")}: {r.prev}</span>}</span>
        </li>
      ))}
    </ul>
  );
}

const nameKey = (s: string) => s.toLowerCase().normalize("NFKC").replace(/[^\p{L}\p{N}]+/gu, "");

export interface VariantRow { variant: TopicVariant; what: string | null; memes: string[] }

/** 나라별 차이 가운데 말할 것이 있는 줄만 — 다른 이름이거나, 자리 표시가 아닌 차이 문장이 있거나, 이름꼴 파생 밈이 있는 것.
 *  같은 파생 밈이 여러 나라에 되풀이되면(백엔드가 같은 목록을 나라마다 붙인다) 처음 나온 나라에만 적는다. */
export function variantRows(topic: Topic | null, names: string[], locale: Locale): VariantRow[] {
  if (!topic) return [];
  const keys = new Set(names.map(nameKey));
  const used: string[] = [];
  const out: VariantRow[] = [];
  for (const v of topic.variants) {
    if (!v.region) continue;
    const what = isPlaceholder(v.what_changed[locale]) ? null : v.what_changed[locale];
    const memes = memeLabels(v.local_memes.map((m) => m.label), [...names, v.local_name, ...used]);
    used.push(...memes);
    const differentName = !keys.has(nameKey(v.local_name));
    if (!what && !memes.length && !differentName) continue;
    out.push({ variant: v, what, memes });
  }
  return out;
}

export function Variants({ rows, termId, edition, locale }: { rows: VariantRow[]; termId: string; edition: string; locale: Locale }) {
  return (
    <div className="fe-variants">
      {rows.map(({ variant: v, what, memes }) => (
        <div key={`${v.region}-${v.local_name}`} className="fe-variant">
          <span className="fe-variant__region">{regionLabel(locale, v.region)}</span>
          <div>
            <span className="fe-variant__local">
              {v.term_id && v.term_id !== termId ? <Link href={entryHref(v.term_id, edition)} lang={scriptLang(v.local_name, v.region)}>{v.local_name}</Link> : <span lang={scriptLang(v.local_name, v.region)}>{v.local_name}</span>}
            </span>
            {what && <p>{what}</p>}
            {memes.length > 0 && <p className="fe-variant__memes"><span>{fe(locale, "e_local_memes")}</span> {memes.map((m, i) => <span key={m}>{i > 0 && ", "}<span lang={scriptLang(m, v.region)}>{m}</span></span>)}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}
