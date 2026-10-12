import { Check } from "lucide-react";
import Link from "next/link";
import type { LabLocale as Locale } from "@/lib/i18n";
import {
  BASE, EDITION_ORDER, EDITION_TABS, SEA, copy, editionHref, editionName, fmtStamp, isCombined, recommendRegions, regionName, weekRange,
  type EditionKey, type SinceItem,
} from "@/lib/lab/o-editorial";
import { EditionScroller, FindLink, LocaleToggle, ScrapCount, SinceLine } from "./client";
import { SearchBox } from "./search-box";

/** 머리 — 이름, 찾기(항상 손 닿는 곳, 치는 동안 밈과 쓸 때 조심을 바로 보인다), 스크랩, 화면 언어, 초안 목록.
 *  앱의 왼쪽 메뉴는 /lab 에서 그리지 않는다. */
export function Masthead({ locale }: { locale: Locale }) {
  const c = copy(locale);
  return (
    <header className="oe-mast">
      <a href="#oe-main" className="oe-skip">{c.skip}</a>
      <div className="oe-wrap oe-mast-row">
        <Link href={BASE} className="oe-wordmark">{c.site}</Link>
        <SearchBox locale={locale} id="oe-q" className="oe-mast-search" />
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

/** 여러 시장 묶기 — 브라우저의 popover 로 연다(스크립트 없이 열고 닫힌다, Esc·바깥 누르기로 닫힘).
 *  폼은 GET 이라 ?regions=TH&regions=VN 으로 가고, 주소 해석(parseEdition)이 한 판으로 묶는다. */
function CombinePanel({ id, locale, edition, counts }: { id: string; locale: Locale; edition: EditionKey; counts: Record<string, number> | null }) {
  const c = copy(locale);
  const picked = new Set<string>(edition === "ALL" ? EDITION_ORDER : edition.split(","));
  return (
    <div id={id} popover="auto" className="oe-combine" role="dialog" aria-labelledby={`${id}-title`}>
      {/* 상자 바깥(어두운 면)을 누르면 닫힌다 — 키보드는 닫기 단추와 Esc 로 */}
      <button type="button" className="oe-combine-scrim" popoverTarget={id} popoverTargetAction="hide" tabIndex={-1} aria-hidden="true" />
      <form className="oe-combine-panel" action={BASE} method="get">
        <h2 id={`${id}-title`} className="oe-combine-title">{c.combineTitle}</h2>
        <p className="oe-combine-note">{c.combineNote}</p>
        <fieldset className="oe-combine-grid">
          <legend className="oe-sr">{c.editionsNav}</legend>
          {EDITION_ORDER.map((r) => (
            <label key={r} className="oe-check">
              <input type="checkbox" name="regions" value={r} defaultChecked={picked.has(r)} />
              <span>{regionName(locale, r)}</span>
              {counts && <span className="oe-check-count oe-num">{c.memesUnit(counts[r] ?? 0)}</span>}
            </label>
          ))}
        </fieldset>
        <p className="oe-combine-quick"><Link href={editionHref(SEA.join(","))} className="oe-link">{c.combineSea}</Link></p>
        <div className="oe-combine-actions">
          <button type="submit" className="oe-btn oe-btn-primary">{c.combineSubmit}</button>
          <button type="button" className="oe-btn oe-btn-line" popoverTarget={id} popoverTargetAction="hide">{c.combineClose}</button>
        </div>
      </form>
    </div>
  );
}

/** 판 고르기 — 판 이름이 곧 이 호의 제목이다. 건수 0 인 판도 숨기지 않는다(얇은 시장을 있는 그대로).
 *  제목 밑 한 줄은 '지난번 방문 이후' — 커버를 지나지 않고도 매일의 확인이 끝나게. */
export function EditionBar({ locale, edition, counts, generatedAt, since }: {
  locale: Locale; edition: EditionKey; counts: Record<string, number> | null; generatedAt: string | null; since?: SinceItem[] | null;
}) {
  const c = copy(locale);
  const rec = recommendRegions(edition);
  const recHref = rec.length ? `/recommend?regions=${rec.join(",")}` : "/recommend";
  const week = weekRange(locale, generatedAt);
  const members = new Set(isCombined(edition) ? edition.split(",") : []);
  const combineId = "oe-combine";
  return (
    <div className="oe-edition">
      <div className="oe-wrap">
        <div className="oe-edition-head">
          <div className="oe-edition-titles">
            <h1 className="oe-edition-title">
              {c.thisWeek(editionName(locale, edition))}
              {week && <span className="oe-edition-week oe-num">{week}</span>}
            </h1>
            {since && <SinceLine locale={locale} items={since} />}
          </div>
          <div className="oe-edition-actions">
            <button type="button" className="oe-edition-tool" popoverTarget={combineId}>{c.combineOpen}</button>
            <Link href={recHref} className="oe-btn oe-btn-line oe-btn-small">{c.recommend}</Link>
          </div>
        </div>
        <nav aria-label={c.editionsNav}>
          <EditionScroller>
            {EDITION_TABS.map((e, i) => {
              const n = counts ? (counts[e] ?? 0) : null;
              const member = members.has(e);
              return (
                <li key={e} className={i === EDITION_TABS.length - 2 ? "oe-edition-sep" : undefined}>
                  <Link href={editionHref(e)} className="oe-edition-item" aria-current={e === edition ? "page" : undefined} data-member={member || undefined} data-empty={n === 0}>
                    {member && <Check aria-hidden size={14} strokeWidth={3} />}
                    {regionName(locale, e)}
                    {n !== null && <span className="oe-edition-count">{c.memesUnit(n)}</span>}
                    {member && <span className="oe-sr"> ({c.combineMember})</span>}
                  </Link>
                </li>
              );
            })}
          </EditionScroller>
        </nav>
      </div>
      <CombinePanel id={combineId} locale={locale} edition={edition} counts={counts} />
    </div>
  );
}
