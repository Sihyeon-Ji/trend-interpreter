import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { KeywordPager } from "@/components/keyword-table";
import { WordTable } from "@/components/ledger-bits";
import { getKeywordBoard, isSampleMode } from "@/lib/data";
import { t, type StringKey } from "@/lib/i18n";
import { fmtDateTime, regionLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { MAKE_MARKETS, TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";
import type { KeywordBoard, KeywordCard } from "@/lib/types";

/* 둘러보기 (Plan 20, 시안 n-redesign) — 시장 하나씩. 기본 탭은 한국·일본·영어권(만들기와 같은 셋), 지도·나라 화면에서 다른 나라로 들어오면
   그 나라도 탭에 더한다. 낱말 크기는 그 시장 안에서의 4주 언급 순위 다섯 단계 — 시장끼리 견주지 않는다(수집량이 달라 큰 시장 말만 커진다).
   목록 셋은 대시보드 규칙(Plan 04) 그대로: 쓰이는 중·식는 중·조심할 말(주의는 앞 둘에도, 사용 자제는 조심할 말에만). 시장·쪽은 주소에만 둔다. */
const KNOWN = [...TARGET_REGIONS, "GLOBAL"];
const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((acc, [k, x]) => acc.replaceAll(`{${k}}`, String(x)), s);
const marketLabel = (locale: "ko" | "en", r: string) => (r === "KR" || r === "JP" || r === "GLOBAL") ? t(locale, `mk_market_${r}` as StringKey) : regionLabel(locale, r);

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "nav_browse")} — ${t(locale, "site")}` };
}

/** 그 시장 안의 순위로 1–5 단계 크기. 4주 언급이 없는 말은 가장 작게 */
function sizes(cards: KeywordCard[]): Map<string, number> {
  const ranked = [...cards].filter((c) => c.mentions_4w > 0).sort((a, b) => b.mentions_4w - a.mentions_4w);
  const n = ranked.length;
  const out = new Map(ranked.map((c, i) => [c.term_id, n <= 1 ? 4 : 5 - Math.min(3, Math.floor((i / n) * 4))]));
  for (const c of cards) if (!out.has(c.term_id)) out.set(c.term_id, 1);
  return out;
}

export default async function Explore({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const raw = [sp.regions].flat().filter(Boolean).join(",").split(",").map((s) => s.trim().toUpperCase());
  const reader = raw[0] ? {} : await getReader();      // 주소에 시장이 없으면 로그인한 사람의 나라, 익명은 한국
  const market = KNOWN.find((r) => r === raw[0]) ?? (reader.region && KNOWN.includes(reader.region) ? reader.region : "KR");
  const page = Math.max(1, Number.parseInt([sp.page].flat()[0] ?? "", 10) || 1);
  const href = (p: number) => `/trends?regions=${market}${p > 1 ? `&page=${p}` : ""}`;

  let board: KeywordBoard | null = null;
  try {
    board = await getKeywordBoard([market], page);
  } catch {
    board = null;
  }
  const longest = board ? Math.max(board.totals.rising, board.totals.fading, board.totals.caution) : 0;
  const last = Math.max(1, Math.ceil(longest / (board?.page_size ?? 30)));
  if (board && page > last) redirect(href(last));

  const name = marketLabel(locale, market);
  const tabs = [...MAKE_MARKETS, ...(MAKE_MARKETS.includes(market as (typeof MAKE_MARKETS)[number]) ? [] : [market])];
  const verified = board?.counts[market] ?? 0;
  const field = board ? [...new Map([...board.rising, ...board.fading, ...board.caution].map((c) => [c.term_id, c])).values()] : [];
  const size = sizes(field);
  const shown = [...field].sort((a, b) => a.canonical.localeCompare(b.canonical, locale === "ko" ? "ko" : "en"));
  const lists = board ? [
    { id: "rising", title: t(locale, "ex_using"), note: t(locale, "ex_using_note"), rows: board.rising, total: board.totals.rising },
    { id: "fading", title: t(locale, "ex_fading"), note: t(locale, "ex_fading_note"), rows: board.fading, total: board.totals.fading },
    { id: "caution", title: t(locale, "ex_careful"), note: t(locale, "ex_careful_note"), rows: board.caution, total: board.totals.caution },
  ] : [];

  return (
    <main id="main" className="n-main">
      <div className="n-wrap">
        <div className="n-head" style={{ paddingBottom: 20 }}>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: "12px 32px" }}>
            <div>
              <h1 className="n-h1">{t(locale, "ex_title")}</h1>
              <p className="n-lead">{t(locale, "ex_lead")}</p>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
              {board && <span className="n-meta">{isSampleMode ? t(locale, "dash_sample_badge") : <>{t(locale, "dash_updated")} <span className="n-num">{fmtDateTime(board.collected_at ?? board.generated_at, locale)}</span></>}</span>}
              <Link className="n-btn" data-kind="line" data-size="s" href={`/map?regions=${market}`}>{t(locale, "dash_pick_on_map")}</Link>
              <Link className="n-btn" data-size="s" href={`/?regions=${market}`}>{t(locale, "ex_make")}</Link>
            </div>
          </div>
        </div>

        <nav className="n-mtabs" aria-label={t(locale, "ex_markets")}>
          {tabs.map((r) => (
            <Link key={r} href={`/trends?regions=${r}`} aria-current={r === market ? "page" : undefined}>
              <b>{marketLabel(locale, r)}</b><span>{fill(t(locale, "ex_count"), { n: (board?.counts[r] ?? 0).toLocaleString() })}</span>
            </Link>
          ))}
        </nav>

        {!board ? (
          <p className="n-error" role="alert" style={{ paddingBlock: 32 }}>{t(locale, "dash_error")} <Link className="n-link" href={href(page)}>{t(locale, "dash_retry")}</Link></p>
        ) : (
          <>
            {page === 1 && (
              <section aria-labelledby="ex-field">
                <h2 className="n-sr" id="ex-field">{fill(t(locale, "ex_field"), { market: name })}</h2>
                {shown.length > 0 && (
                  <p className="n-field-words">
                    {shown.map((c) => {
                      const others = c.regions.filter((r) => r !== market && r !== "GLOBAL").length;
                      const risk = c.risk_level === "avoid" ? "avoid" : c.risk_level === "caution" ? "caution" : "none";
                      return (
                        <span key={c.term_id} className="n-fw" data-s={size.get(c.term_id)} data-r={risk} lang={c.lang}>
                          <Link href={`/dictionary/${encodeURIComponent(c.term_id)}?regions=${market}`}>{c.canonical}</Link>
                          {risk === "avoid" && <span className="n-sr">({t(locale, "risk_avoid")})</span>}
                          {risk === "caution" && <span className="n-sr">({t(locale, "risk_caution")})</span>}
                          {others > 0 && <sup aria-label={fill(t(locale, "ex_key_share_note"), { n: others })}>+{others}</sup>}
                        </span>
                      );
                    })}
                  </p>
                )}
                {verified < 50 && <p className="n-thin" style={{ margin: "0 0 28px" }}>{fill(t(locale, "ex_thin"), { market: name, n: verified })}</p>}
                <div className="n-strip">
                  <dl className="n-stats" aria-label={fill(t(locale, "ex_stats"), { market: name })}>
                    <div><dt>{t(locale, "ex_verified")}</dt><dd>{verified.toLocaleString()}</dd></div>
                    {lists.map((l) => <div key={l.id}><dt>{l.title}</dt><dd>{l.total.toLocaleString()}</dd></div>)}
                  </dl>
                  <ul className="n-keys" aria-label={t(locale, "ex_keys")}>
                    <li><span className="k-size">{t(locale, "ex_key_size")}</span><span>{fill(t(locale, "ex_key_size_note"), { market: name })}</span></li>
                    <li><span className="k-share">+2</span><span>{fill(t(locale, "ex_key_share_note"), { n: 2 })}</span></li>
                    <li><span className="k-caution">{t(locale, "ex_key_caution")}</span><span>{t(locale, "ex_key_caution_note")}</span></li>
                    <li><span className="k-avoid">{t(locale, "ex_key_avoid")}</span><span>{t(locale, "ex_key_avoid_note")}</span></li>
                  </ul>
                </div>
              </section>
            )}

            {lists.map((l) => (
              <section key={l.id} className="n-list" aria-labelledby={`l-${l.id}`}>
                <div className="n-list-head">
                  <h2 className="n-h2" id={`l-${l.id}`}>{l.title} <span className="n-num" style={{ fontWeight: 400, color: "var(--n-ink-3)" }}>{l.total}</span></h2>
                  <span className="n-meta">{l.note}</span>
                </div>
                {l.rows.length ? <WordTable cards={l.rows} caption={`${name}, ${l.title}`} locale={locale} regions={[market]} />
                  : <p className="n-empty">{fill(t(locale, "ex_empty"), { market: name })}</p>}
              </section>
            ))}
            {longest > board.page_size && (
              <div style={{ marginTop: 24 }}><KeywordPager total={longest} page={page} size={board.page_size} href={href} locale={locale} /></div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
