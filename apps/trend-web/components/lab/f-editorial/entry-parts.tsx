import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { fe, words } from "@/lib/lab/f-editorial-copy";
import { entryHref, isPlaceholder } from "@/lib/lab/f-editorial";
import { L, fmtDate, regionLabel, sourceName } from "@/lib/labels";
import { langTag, scriptLang } from "@/lib/lang";
import type { Topic } from "@/lib/trends/types";
import type { Evidence, Meaning, Term, TermUsage } from "@/lib/types";
import { riskReasonText, riskWord, stageWord } from "./stickers";

/* 항목(기사)의 부품 — 사실 칸, 출처, 뜻의 이력, 나라별 차이. 전부 서버에서 그린다. */

export function FactRail({ term, verified, meaning, usage, lastUsed, sources, locale }: {
  term: Term; verified: boolean; meaning: Meaning | null; usage: TermUsage[]; lastUsed: string | null; sources: number; locale: Locale;
}) {
  const labels = L(locale);
  const stage = { lifecycle: term.lifecycle ?? "unknown", diffusion: term.diffusion, risk_level: term.risk_level, risk_checked_at: term.risk_checked_at };
  const risk = riskWord(stage, locale);
  const riskWhy = () => {
    if (!risk) return null;
    if (term.risk_human) return fe(locale, "risk_by_reviewer");
    return riskReasonText(term, locale) ?? words(locale).riskWhy[risk.key];
  };
  const firstSeen = [...usage].sort((a, b) => a.first_seen.localeCompare(b.first_seen)).slice(0, 3);
  const row = (label: string, value: React.ReactNode) => (
    <div className="fe-facts__row"><dt>{label}</dt><dd>{value}</dd></div>
  );
  return (
    <aside className="fe-facts" aria-label={fe(locale, "f_stage")}>
      <dl>
        {row(fe(locale, "f_stage"), verified
          ? <><span>{words(locale).lifecycle[stage.lifecycle]}</span>{term.diffusion && <span className="fe-facts__why">{stageWord(stage, locale)}</span>}</>
          : <span className="fe-muted">{fe(locale, "e_reviewing")}</span>)}
        {verified && risk && row(fe(locale, "f_risk"), <><span className={`fe-sticker ${risk.key === "caution" ? "fe-sticker--caution" : risk.key === "avoid" ? "fe-sticker--avoid" : "fe-sticker--muted"}`}>{risk.label}</span><span className="fe-facts__why">{riskWhy()}</span></>)}
        {meaning && meaning.regions.length > 0 && row(fe(locale, "f_regions"), meaning.regions.map((r) => regionLabel(locale, r)).join(", "))}
        {meaning && meaning.generations.length > 0 && row(fe(locale, "f_gens"), meaning.generations.map((g) => labels.generation[g]).join(", "))}
        {lastUsed && row(fe(locale, "f_last"), fmtDate(lastUsed))}
        {firstSeen.length > 0 && row(fe(locale, "f_first"), firstSeen.map((u) => `${regionLabel(locale, u.segment.region)} ${labels.generation[u.segment.generation]} ${fmtDate(u.first_seen)}`).join(" / "))}
        {(term.aliases?.length ?? 0) > 0 && row(fe(locale, "f_aliases"), term.aliases!.map((a, i) => <span key={a}>{i > 0 && ", "}<span lang={scriptLang(a)}>{a}</span></span>))}
        {sources > 0 && row(fe(locale, "f_sources"), <a href="#fe-sources" className="fe-link">{fe(locale, "f_sources_n", { n: sources })}</a>)}
      </dl>
    </aside>
  );
}

const VISIBLE_KINDS = new Set(["wiki", "news", "short", "web"]);
/** 보이는 출처만 — 위키·기사·영상·웹 문서. 커뮤니티 글은 쓰임 신호로만 쓰고 제목·이름을 내지 않는다. */
export const visibleSources = (evidences: Evidence[]) =>
  [...evidences].filter((e) => VISIBLE_KINDS.has(e.kind)).sort((a, b) => b.observed_at.localeCompare(a.observed_at));

export function SourceList({ sources, locale, region }: { sources: Evidence[]; locale: Locale; region?: string | null }) {
  const kind = L(locale).evidenceKind;
  return (
    <ul className="fe-sources">
      {sources.map((e) => (
        <li key={e.evidence_id}>
          <span className="fe-sources__date">{fmtDate(e.observed_at)}</span>
          <span>
            <a href={e.url} target="_blank" rel="noreferrer noopener" className="fe-sources__title" lang={scriptLang(e.title ?? "", region)}>{e.title || e.url}<span className="sr-only"> ({fe(locale, "new_tab")})</span></a>
            <span className="fe-sources__src"> — {sourceName(locale, e.source_domain)} {kind[e.kind]}</span>
          </span>
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
          <span>{r.what}{r.prev && <span className="fe-history__prev" lang="ko"><br />{fe(locale, "ch_prev")}: {r.prev}</span>}</span>
        </li>
      ))}
    </ul>
  );
}

export function Variants({ topic, termId, edition, locale }: { topic: Topic; termId: string; edition: string; locale: Locale }) {
  const rows = topic.variants.filter((v) => v.region);
  if (rows.length < 2) return null;
  return (
    <div className="fe-variants">
      {rows.map((v) => (
        <div key={`${v.region}-${v.local_name}`} className="fe-variant">
          <span className="fe-variant__region">{regionLabel(locale, v.region)}</span>
          <div>
            <span className="fe-variant__local">
              {v.term_id && v.term_id !== termId ? <Link href={entryHref(v.term_id, edition)} lang={scriptLang(v.local_name, v.region)}>{v.local_name}</Link> : <span lang={scriptLang(v.local_name, v.region)}>{v.local_name}</span>}
            </span>
            {!isPlaceholder(v.what_changed[locale]) && <p>{v.what_changed[locale]}</p>}
            {v.local_memes.length > 0 && <p className="fe-variant__memes">{v.local_memes.map((m) => m.label).join(", ")}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

export { langTag };
