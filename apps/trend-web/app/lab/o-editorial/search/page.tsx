import type { Metadata } from "next";
import Link from "next/link";
import { Tape } from "@/components/lab/o-editorial/type";
import { currentMeaning, textFor } from "@/lib/explain";
import { langTag } from "@/lib/lang";
import { copy, entryHref, fmtDay, regionName, riskKind, riskTone, riskWord, stageTape } from "@/lib/lab/o-editorial";
import { searchDictionary } from "@/lib/lab/o-editorial-data";
import { getLocale } from "@/lib/locale";

/* 찾기 — '이 밈, 써도 되나' 를 올리기 직전에 확인하는 길. 확인을 거친 사전에서 이름·다른 표기·뜻으로 찾는다. */

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata(): Promise<Metadata> {
  const c = copy(await getLocale());
  return { title: `${c.searchTitle} | ${c.site}` };
}

export default async function SearchPage({ searchParams }: Props) {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const c = copy(locale);
  const q = ([sp.q].flat()[0] ?? "").trim().slice(0, 60);
  const found = q ? await searchDictionary(q) : [];

  return (
    <div className="oe-wrap" style={{ paddingTop: 36, paddingBottom: 72 }}>
      <h1 style={{ fontSize: "clamp(34px, 4vw, 52px)", fontWeight: 800, lineHeight: 1.1, letterSpacing: "-0.035em" }}>{c.searchTitle}</h1>
      <form action="/lab/o-editorial/search" method="get" role="search" className="oe-search-form">
        <label htmlFor="oe-q-page" className="oe-sr">{c.searchLabel}</label>
        <input id="oe-q-page" name="q" type="search" defaultValue={q} placeholder={c.searchPlaceholder} autoComplete="off" autoFocus={!q} />
        <button type="submit">{c.searchButton}</button>
      </form>
      <p className="oe-meta" style={{ marginTop: 10, fontSize: 14 }}>{c.searchHint}</p>

      {q && found === null && <div className="oe-state" role="alert" style={{ marginTop: 32 }}><p>{c.searchFailed}</p></div>}
      {q && found && (
        <section aria-labelledby="oe-results" style={{ marginTop: 40 }}>
          <h2 id="oe-results" style={{ fontSize: 20, fontWeight: 800 }} aria-live="polite">{found.length ? c.searchResults(q, found.length) : c.searchEmpty(q)}</h2>
          {found.length > 0 && (
            <ul className="oe-ledger">
              {found.map(({ record: r, regions, lastUsed }) => {
                const t = r.term;
                const st = stageTape(locale, { lifecycle: t.lifecycle ?? "unknown", diffusion: t.diffusion ?? null });
                const k = riskKind(t);
                const tone = riskTone(k);
                const tx = textFor(r, locale);
                const m = currentMeaning(r);
                return (
                  <li key={t.term_id} className="oe-ledger-item">
                    <div style={{ display: "grid", gap: 6, minWidth: 0 }}>
                      <Link href={entryHref(t.term_id)} className="oe-ledger-name" lang={langTag(t.lang)}>{t.canonical}</Link>
                      {regions.length > 0 && <span className="oe-meta">{regions.map((x) => regionName(locale, x)).join(", ")}</span>}
                    </div>
                    <p className="oe-index-gloss" style={{ WebkitLineClamp: 3, color: "var(--oe-ink)", fontSize: 15 }} lang={locale === "en" && !r.en ? "ko" : undefined}>{tx?.definition ?? m?.definition ?? ""}</p>
                    <div className="oe-ledger-side">
                      <Tape tone={st.tone}>{st.text}</Tape>
                      {tone ? <Tape tone={tone}>{riskWord(locale, k)}</Tape> : <span className="oe-meta">{riskWord(locale, k)}</span>}
                      {lastUsed && <span className="oe-meta oe-num">{c.lastUsedLabel} {fmtDay(locale, lastUsed)}</span>}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
