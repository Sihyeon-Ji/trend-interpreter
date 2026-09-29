import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import {
  BASE, EDITIONS, copy, editionHref, editionName, fmtStamp, recommendRegions, regionName, weekRange, type EditionKey,
} from "@/lib/lab/o-editorial";
import { FindLink, LocaleToggle, ScrapCount } from "./client";

/** 머리 — 이름, 찾기(항상 손 닿는 곳), 스크랩, 화면 언어, 초안 목록. 앱의 왼쪽 메뉴는 /lab 에서 그리지 않는다. */
export function Masthead({ locale }: { locale: Locale }) {
  const c = copy(locale);
  return (
    <header className="oe-mast">
      <a href="#oe-main" className="oe-skip">{c.skip}</a>
      <div className="oe-wrap oe-mast-row">
        <Link href={BASE} className="oe-wordmark">{c.site}</Link>
        <form action={`${BASE}/search`} method="get" role="search" className="oe-mast-search">
          <label htmlFor="oe-q" className="oe-sr">{c.searchLabel}</label>
          <input id="oe-q" name="q" type="search" placeholder={c.searchPlaceholder} autoComplete="off" />
          <button type="submit">{c.searchButton}</button>
        </form>
        <nav className="oe-mast-tools" aria-label={c.site}>
          <FindLink locale={locale} />
          <ScrapCount locale={locale} />
          <LocaleToggle locale={locale} />
          <Link href="/lab" className="oe-mast-tool oe-mast-drafts oe-quiet-link">{c.drafts}</Link>
        </nav>
      </div>
    </header>
  );
}

export function Footer({ locale, updatedAt, sample }: { locale: Locale; updatedAt: string | null; sample: boolean }) {
  const c = copy(locale);
  return (
    <footer className="oe-foot">
      <div className="oe-wrap oe-foot-row">
        <div className="oe-meta" style={{ fontSize: 14 }}>
          <p>{c.footerData}</p>
          {updatedAt && <p className="oe-num" style={{ marginTop: 6 }}>{c.updated(fmtStamp(locale, updatedAt))}</p>}
          {sample && <p style={{ marginTop: 6 }}>{c.sampleNote}</p>}
        </div>
        <nav aria-label={c.drafts}>
          <Link href="/lab" className="oe-quiet-link">{c.drafts}</Link>
          <Link href="/" className="oe-quiet-link">{c.footerApp}</Link>
        </nav>
      </div>
    </footer>
  );
}

/** 판 고르기 — 판 이름이 곧 이 호의 제목이다. 건수 0 인 판도 숨기지 않는다(얇은 시장을 있는 그대로). */
export function EditionBar({ locale, edition, counts, generatedAt }: {
  locale: Locale; edition: EditionKey; counts: Record<string, number> | null; generatedAt: string | null;
}) {
  const c = copy(locale);
  const rec = recommendRegions(edition);
  const recHref = rec.length ? `/recommend?regions=${rec.join(",")}` : "/recommend";
  const week = weekRange(locale, generatedAt);
  return (
    <div className="oe-edition">
      <div className="oe-wrap">
        <div className="oe-edition-head">
          <h1 className="oe-edition-title">
            {c.thisWeek(editionName(locale, edition))}
            {week && <span className="oe-meta oe-num" style={{ marginLeft: 12, fontSize: 14, fontWeight: 500 }}>{week}</span>}
          </h1>
          <Link href={recHref} className="oe-btn oe-btn-line oe-btn-small">{c.recommend}</Link>
        </div>
        <nav aria-label={c.editionsNav}>
          <ul className="oe-edition-list">
            {EDITIONS.map((e, i) => {
              const n = counts ? (counts[e === "ALL" ? "ALL" : e] ?? 0) : null;
              return (
                <li key={e} className={i === EDITIONS.length - 2 ? "oe-edition-sep" : undefined}>
                  <Link href={editionHref(e)} className="oe-edition-item" aria-current={e === edition ? "page" : undefined} data-empty={n === 0}>
                    {regionName(locale, e)}
                    {n !== null && <span className="oe-edition-count">{c.memesUnit(n)}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </div>
  );
}
