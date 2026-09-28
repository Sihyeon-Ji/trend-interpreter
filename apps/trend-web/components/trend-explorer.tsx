"use client";

import Link from "next/link";
import { ChevronLeft, Minus, Pause, Play, Plus, RotateCcw, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { TrendGlobe, type GlobeApi, type GlobeArc, type GlobeBubble, type GlobeFocus } from "@/components/globe/trend-globe";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, fmtDateTime, regionLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import { CENTROID } from "@/lib/trends/geo";
import { displayOrder, originOf, pathOf } from "@/lib/trends/path";
import { TREND_CATEGORIES, type Topic, type TrendBoard, type TrendCategory, type TrendItem } from "@/lib/trends/types";
import { cn } from "@/lib/utils";
import { WhyCard } from "@/components/why-card";
import type { Meta } from "@/lib/trends/types";

const catOrder = (c: TrendCategory) => TREND_CATEGORIES.indexOf(c);
const rad = Math.PI / 180;
/* 두 나라가 함께 보이는 카메라 위치: 구면 중점 + 거리에 비례한 높이 */
function between(a: string, b: string): { lat: number; lng: number; altitude: number } {
  const A = CENTROID[a], B = CENTROID[b];
  const v = [A, B].map((c) => [Math.cos(c.lat * rad) * Math.cos(c.lng * rad), Math.cos(c.lat * rad) * Math.sin(c.lng * rad), Math.sin(c.lat * rad)]);
  const m = [0, 1, 2].map((i) => v[0][i] + v[1][i]);
  const n = Math.hypot(...m) || 1;
  const lat = Math.asin(m[2] / n) / rad, lng = Math.atan2(m[1], m[0]) / rad;
  const ang = Math.acos(Math.min(1, (v[0][0] * v[1][0] + v[0][1] * v[1][1] + v[0][2] * v[1][2]))) / rad; // 각거리(도)
  return { lat, lng, altitude: Math.min(3.4, 1.6 + ang / 55) };
}
const changeKey = (c: TrendItem["change"]) => (`map_change_${c}` as const);

function MiniSpark({ values }: { values: number[] }) {
  const w = 56, h = 16, max = Math.max(1, ...values);
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * (w - 2) + 1).toFixed(1)},${(h - 1 - (v / max) * (h - 2)).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden className="shrink-0 text-charcoal">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

const CTRL = "flex size-8 items-center justify-center border-b border-hairline text-charcoal last:border-b-0 hover:bg-[#f6f7f8] hover:text-ink";

function Heat({ value }: { value: number }) {
  return (
    <span className="inline-flex items-center gap-2 tabular-nums">
      <span className="inline-block h-[3px] w-[72px] rounded-[2px] bg-[#e6e8eb]" aria-hidden>
        <span className="block h-full rounded-[2px] bg-[var(--ink)]" style={{ width: `${value}%` }} />
      </span>
      <span className="text-[12px] text-steel">{value}</span>
    </span>
  );
}

export function TrendExplorer({ board, locale, initialRegion = null, initialTopic = null, meta = null, updatesCount = 0 }: { board: TrendBoard; locale: Locale; initialRegion?: string | null; initialTopic?: string | null; meta?: Meta | null; updatesCount?: number }) {
  const labels = L(locale);
  const [region, setRegion] = useState<string | null>(initialRegion);
  const [topicId, setTopicId] = useState<string | null>(initialTopic);
  const [compareId, setCompareId] = useState<string>(initialTopic ?? board.topics[0]?.id);
  const [category, setCategory] = useState<TrendCategory | "all">("all");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(0); // 경로가 몇 나라까지 그려졌나 (순서대로 등장)
  const [focus, setFocus] = useState<GlobeFocus | null>(() => {
    const first = initialTopic ? board.topics.find((x) => x.id === initialTopic) : undefined;
    const r = initialRegion ?? (first ? (originOf(first) ?? displayOrder(first)[0]?.region ?? null) : null);
    return r && CENTROID[r] ? { ...CENTROID[r], altitude: initialTopic ? 2.4 : 1.7, nonce: 1 } : null;
  });
  const look = (pos: { lat: number; lng: number; altitude: number }) => setFocus((f) => ({ ...pos, nonce: (f?.nonce ?? 0) + 1 }));
  const lookAt = (code: string, altitude: number) => { if (CENTROID[code]) look({ ...CENTROID[code], altitude }); };
  const [rotating, setRotating] = useState(true);
  const api = useRef<GlobeApi | null>(null);

  const topic: Topic | undefined = board.topics.find((x) => x.id === topicId);
  const items = useMemo(() => (category === "all" ? board.items : board.items.filter((i) => i.category === category)), [board.items, category]);
  const byRegion = useMemo(() => {
    const m = new Map<string, TrendItem[]>();
    for (const i of items) m.set(i.region, [...(m.get(i.region) ?? []), i]);
    for (const l of m.values()) l.sort((a, b) => a.rank - b.rank || catOrder(a.category) - catOrder(b.category));
    return m;
  }, [items]);
  const regionsWithData = useMemo(() => [...new Set(board.items.map((i) => i.region))], [board.items]);
  const countryRows = useMemo(
    () => [...byRegion.entries()].sort((a, b) => b[1].length - a[1].length || regionLabel(locale, a[0]).localeCompare(regionLabel(locale, b[0]), locale)),
    [byRegion, locale],
  );

  // 검색: 나라 이름·키워드·주제 이름
  const q = query.trim().toLowerCase();
  const matchRegion = (code: string, list: TrendItem[]) => !q || regionLabel(locale, code).toLowerCase().includes(q) || list.some((i) => i.term.toLowerCase().includes(q));
  const matchTopic = (x: Topic) => !q || x.name.ko.toLowerCase().includes(q) || x.name.en.toLowerCase().includes(q) || x.variants.some((v) => v.local_name.toLowerCase().includes(q) || regionLabel(locale, v.region).toLowerCase().includes(q));

  // 주제를 열면 경로가 날짜순으로 한 나라씩 그려지고, 카메라가 출발점과 그 나라가 함께 보이는 자리로 따라간다.
  // 날짜가 확인된 나라가 둘 미만이면 경로가 없다 — 나라들을 한꺼번에 보인다. 차례로 나타나기만 해도 퍼진 순서처럼 읽히기 때문이다.
  useEffect(() => {
    if (!topic) return;
    const path = pathOf(topic);
    const order = displayOrder(topic);
    if (!path.length) {
      const id = setTimeout(() => {
        setShown(order.length);
        if (order[0]) lookAt(order[0].region, 2.4);
      }, 0);
      return () => clearTimeout(id);
    }
    const origin = path[0].region;
    const step = 1300;
    const timers: ReturnType<typeof setTimeout>[] = [];
    path.forEach((v, i) => {
      timers.push(setTimeout(() => {
        setShown(i + 1);
        if (i === 0) lookAt(origin, 2.4);
        else look(between(origin, v.region));
      }, i === 0 ? 0 : step * i));
    });
    // 날짜가 확인되지 않은 나라는 경로가 다 그려진 뒤 한꺼번에, 선 없이
    if (order.length > path.length) timers.push(setTimeout(() => setShown(order.length), step * path.length));
    return () => timers.forEach(clearTimeout);
  }, [topic]); // eslint-disable-line react-hooks/exhaustive-deps

  const openRegion = (code: string) => {
    setTopicId(null);
    setShown(0);
    setRegion(code);
    lookAt(code, 1.7);
    setRotating(false);
  };
  const openTopic = (id: string) => {
    setRegion(null);
    setShown(0);
    setTopicId(id);
    setCompareId(id);
    setRotating(false);
  };
  const back = () => { setRegion(null); setTopicId(null); setShown(0); };

  // 지구에 올릴 것
  const bubbles: GlobeBubble[] = useMemo(() => {
    if (topic) {
      const origin = originOf(topic);
      return displayOrder(topic).slice(0, shown).filter((v) => CENTROID[v.region])
        .map((v) => ({ region: v.region, ...CENTROID[v.region], title: v.local_name, sub: regionLabel(locale, v.region), strong: v.region === origin }));
    }
    return countryRows.filter(([c]) => CENTROID[c]).map(([c, list]) => ({ region: c, ...CENTROID[c], title: list.length > 1 ? `${list[0].term}  +${list.length - 1}` : list[0].term, sub: regionLabel(locale, c), strong: c === region }));
  }, [topic, shown, countryRows, region, locale]);
  const arcs: GlobeArc[] = useMemo(() => {
    if (!topic) return [];
    const path = pathOf(topic);
    const o = path[0] && CENTROID[path[0].region];
    if (!o) return [];
    return path.slice(1, shown).filter((v) => CENTROID[v.region])
      .map((v) => ({ startLat: o.lat, startLng: o.lng, endLat: CENTROID[v.region].lat, endLng: CENTROID[v.region].lng }));
  }, [topic, shown]);
  const rings = useMemo(() => {
    const o = topic ? originOf(topic) : null;
    return o && CENTROID[o] ? [CENTROID[o]] : [];
  }, [topic]);
  const highlighted = useMemo(() => (topic ? topic.variants.map((v) => v.region) : []), [topic]);

  const compare = board.topics.find((x) => x.id === compareId) ?? board.topics[0] ?? null;
  const panelItems = region ? byRegion.get(region) ?? [] : [];
  const grouped = TREND_CATEGORIES.map((c) => [c, panelItems.filter((i) => i.category === c)] as const).filter(([, l]) => l.length);

  return (
    <>
      <section className="border-b border-hairline">
        <div className="flex min-h-[560px] flex-col lg:h-[calc(100dvh-57px)] lg:flex-row">
          {/* 패널 */}
          <aside className="order-2 flex w-full flex-col border-t border-hairline lg:order-1 lg:w-[400px] lg:shrink-0 lg:border-r lg:border-t-0">
            <div className="border-b border-hairline px-5 pb-3 pt-4">
              <div className="flex items-baseline justify-between gap-3">
                <h1 className="text-[18px] font-semibold text-ink">{t(locale, "map_title")}</h1>
                <label className="flex items-center gap-1.5 text-[12px] text-steel">
                  {t(locale, "map_category")}
                  <select value={category} onChange={(e) => setCategory(e.target.value as TrendCategory | "all")} className="rounded-[4px] border border-hairline bg-white px-1.5 py-1 text-[12px] text-ink">
                    <option value="all">{t(locale, "map_all")}</option>
                    {TREND_CATEGORIES.map((c) => <option key={c} value={c}>{labels.trendCategory[c]}</option>)}
                  </select>
                </label>
              </div>
              <p className="mt-1 text-[13px] text-charcoal">{t(locale, "ex_intro")}</p>
              {(meta?.board_generated_at || updatesCount > 0) && (
                <p className="mt-1.5 flex flex-wrap gap-x-3 text-[12px] text-steel">
                  {meta?.board_generated_at && <span>{t(locale, "updates_last_run")} {fmtDateTime(meta.board_generated_at, locale)}</span>}
                  {updatesCount > 0 && <Link href="/updates" className="text-link-blue hover:underline">{t(locale, "updates_title")} {updatesCount}{t(locale, "updates_count_unit")}</Link>}
                </p>
              )}
              <label className="mt-3 flex items-center gap-2 rounded-[4px] border border-hairline bg-white px-2.5 py-1.5 focus-within:border-[var(--ink)]">
                <Search className="size-4 shrink-0 text-steel" aria-hidden />
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t(locale, "ex_search")} aria-label={t(locale, "ex_search")}
                  className="w-full bg-transparent text-[14px] text-ink outline-none placeholder:text-steel" />
              </label>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto lg:max-h-none">
              {/* 목록 */}
              {!region && !topic && (
                <>
                  {board.topics.length > 0 && (
                  <section className="px-5 pt-4">
                    <div className="flex items-baseline justify-between">
                      <h2 className="text-[13px] font-semibold text-ink">{t(locale, "ex_topics")}</h2>
                      <span className="text-[12px] text-steel">{t(locale, "ex_topics_hint")}</span>
                    </div>
                    <ul className="mt-1 divide-y divide-hairline">
                      {board.topics.filter(matchTopic).map((x) => (
                        <li key={x.id}>
                          <button type="button" onClick={() => openTopic(x.id)} className="flex w-full items-center justify-between gap-3 py-2.5 text-left hover:bg-[#f6f7f8]">
                            <span className="min-w-0">
                              <span className="block truncate text-[14px] font-medium text-ink">{x.name[locale]}</span>
                              <span className="block text-[12px] text-steel">{(() => { const o = originOf(x); return o ? `${regionLabel(locale, o)} → ` : ""; })()}{x.variants.length}{t(locale, "ex_countries_unit")}</span>
                            </span>
                            <span className="shrink-0 text-[12px] text-steel">{labels.trendCategory[x.category]}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </section>
                  )}
                  <section className="px-5 pb-6 pt-5">
                    <h2 className="text-[13px] font-semibold text-ink">{t(locale, "ex_countries")}</h2>
                    <ul className="mt-1 divide-y divide-hairline">
                      {countryRows.filter(([c, l]) => matchRegion(c, l)).map(([c, list]) => (
                        <li key={c}>
                          <button type="button" onClick={() => openRegion(c)} className="flex w-full items-center gap-3 py-2.5 text-left hover:bg-[#f6f7f8]">
                            <span className="w-[76px] shrink-0 text-[14px] font-medium text-ink">{regionLabel(locale, c)}</span>
                            <span className="min-w-0 flex-1 truncate text-[13px] text-charcoal">{list[0].term}</span>
                            <span className="shrink-0 text-[12px] text-steel tabular-nums">{list.length}{t(locale, "ex_items_unit")}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                    {countryRows.filter(([c, l]) => matchRegion(c, l)).length === 0 && board.topics.filter(matchTopic).length === 0 && (
                      <p className="py-3 text-[13px] text-steel">{t(locale, "ex_no_result")}</p>
                    )}
                  </section>
                </>
              )}

              {/* 나라 상세 */}
              {region && !topic && (
                <div className="px-5 pb-6 pt-3">
                  <button type="button" onClick={back} className="inline-flex items-center gap-1 text-[13px] text-steel hover:text-ink"><ChevronLeft className="size-4" aria-hidden />{t(locale, "ex_back")}</button>
                  <div className="mt-2 flex items-baseline justify-between gap-2">
                    <h2 className="text-[20px] font-semibold text-ink">{regionLabel(locale, region)}</h2>
                    <span className="flex gap-3 whitespace-nowrap">
                      {TARGET_REGIONS.includes(region) && <Link href={`/trends?regions=${region}`} className="text-[13px] text-link-blue hover:underline">{t(locale, "dash_open_country")}</Link>}
                      <Link href={`/country/${region}`} className="text-[13px] text-link-blue hover:underline">{t(locale, "country_page")}</Link>
                    </span>
                  </div>
                  <p className="text-[12px] text-steel">{panelItems.length}{t(locale, "ex_items_unit")}</p>
                  {board.why.filter((w) => w.region === region).length > 0 && (
                    <section className="mt-3">
                      <h3 className="text-[12px] font-semibold text-steel">{t(locale, "why_title")}</h3>
                      {board.why.filter((w) => w.region === region).slice(0, 4).map((w) => <WhyCard key={w.term + w.date} w={w} locale={locale} />)}
                    </section>
                  )}
                  {grouped.map(([c, list]) => (
                    <section key={c} className="mt-4">
                      <h3 className="text-[12px] font-semibold text-steel">{labels.trendCategory[c]}</h3>
                      <ul className="divide-y divide-hairline">
                        {list.map((i) => (
                          <li key={i.id} className="py-2.5">
                            <div className="flex items-center gap-2">
                              <span className="w-3 shrink-0 text-[12px] text-steel tabular-nums">{i.rank}</span>
                              <span className="min-w-0 flex-1 truncate text-[14px] font-medium text-ink">{i.term_id ? <Link href={`/dictionary/${i.term_id}`} className="hover:underline">{i.term}</Link> : i.term}</span>
                              <MiniSpark values={i.weekly} />
                            </div>
                            <p className="mt-0.5 pl-5 text-[12.5px] leading-snug text-charcoal">{i.note[locale]}</p>
                            <p className="mt-0.5 flex flex-wrap gap-x-3 pl-5 text-[12px] text-steel">
                              <span>{t(locale, changeKey(i.change))}{i.gain_pct ? ` +${i.gain_pct.toLocaleString("en-US")}%` : ""}</span>
                              {i.topic_id && <button type="button" onClick={() => openTopic(i.topic_id!)} className="text-link-blue hover:underline">{t(locale, "ex_compare_btn")}</button>}
                              {i.term_id && <Link href={`/dictionary/${i.term_id}`} className="text-link-blue hover:underline">{t(locale, "map_in_dict")}</Link>}
                            </p>
                          </li>
                        ))}
                      </ul>
                    </section>
                  ))}
                </div>
              )}

              {/* 주제 상세 */}
              {topic && (
                <div className="px-5 pb-6 pt-3">
                  <button type="button" onClick={back} className="inline-flex items-center gap-1 text-[13px] text-steel hover:text-ink"><ChevronLeft className="size-4" aria-hidden />{t(locale, "ex_back")}</button>
                  <h2 className="mt-2 text-[20px] font-semibold text-ink">{topic.name[locale]}</h2>
                  <p className="text-[12px] text-steel">
                    {labels.trendCategory[topic.category]} · {(() => { const o = originOf(topic); return o ? `${t(locale, "map_origin")} ${regionLabel(locale, o)} · ` : ""; })()}{topic.variants.length}{t(locale, "ex_countries_unit")}
                  </p>
                  {!originOf(topic) && <p className="mt-1 text-[12px] text-steel">{t(locale, "map_no_path")}</p>}
                  <p className="mt-2 text-[13.5px] leading-relaxed text-charcoal">{topic.summary[locale]}</p>
                  <ol className="mt-3 divide-y divide-hairline">
                    {displayOrder(topic).map((v, i) => (
                      <li key={v.region} className={cn("py-3", i >= shown && "opacity-40")}>
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="text-[14px] font-semibold text-ink">{regionLabel(locale, v.region)} <span className="font-medium">· {v.term_id ? <Link href={`/dictionary/${v.term_id}`} className="hover:underline">{v.local_name}</Link> : v.local_name}</span></span>
                          <span className="shrink-0 text-[12px] text-steel tabular-nums">{v.dated ? fmtDate(v.since) : t(locale, "map_undated")}</span>
                        </div>
                        {v.dated && v.since_source && <p className="text-[11.5px] text-steel">{t(locale, "map_since_source")} {v.since_source[locale]}</p>}
                        <div className="mt-1"><Heat value={v.heat} /></div>
                        <p className="mt-1.5 text-[13px] leading-snug text-charcoal">{v.what_changed[locale]}</p>
                        {v.local_memes.length > 0 && (
                          <p className="mt-1.5 flex flex-wrap gap-1.5">
                            {v.local_memes.map((m) => <span key={m.label} title={m.note[locale]} className="rounded-[3px] border border-hairline px-1.5 py-0.5 text-[12px] text-ink">{m.label}</span>)}
                          </p>
                        )}
                        {v.linked.length > 0 && (
                          <p className="mt-1.5 text-[12px] text-steel">{t(locale, "ex_linked")}: {v.linked.map((l, j) => <span key={l.label}>{j > 0 && ", "}{l.term_id ? <Link href={`/dictionary/${l.term_id}`} className="text-link-blue hover:underline">{l.label}</Link> : <span className="text-charcoal">{l.label}</span>}</span>)}</p>
                        )}
                        <button type="button" onClick={() => lookAt(v.region, 1.7)} className="mt-1.5 text-[12px] text-link-blue hover:underline">{t(locale, "ex_show_on_globe")}</button>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          </aside>

          {/* 지구 */}
          <div className="relative order-1 h-[54vh] min-h-[360px] w-full lg:order-2 lg:h-auto lg:min-h-0 lg:flex-1">
            <TrendGlobe regionsWithData={regionsWithData} highlighted={highlighted} selected={region} bubbles={bubbles} arcs={arcs} rings={rings} focus={focus}
              onSelect={openRegion} apiRef={api} loadingLabel={t(locale, "ex_loading")} />
            <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between p-3">
              <p className="pointer-events-auto max-w-[60%] text-[12px] text-steel">{t(locale, "ex_legend")}</p>
              <div className="pointer-events-auto flex flex-col overflow-hidden rounded-[4px] border border-hairline bg-white">
                <button type="button" onClick={() => api.current?.zoom(0.75)} title={t(locale, "ex_zoom_in")} aria-label={t(locale, "ex_zoom_in")} className={CTRL}><Plus className="size-4" /></button>
                <button type="button" onClick={() => api.current?.zoom(1.33)} title={t(locale, "ex_zoom_out")} aria-label={t(locale, "ex_zoom_out")} className={CTRL}><Minus className="size-4" /></button>
                <button type="button" onClick={() => { api.current?.reset(); setRotating(true); }} title={t(locale, "ex_reset")} aria-label={t(locale, "ex_reset")} className={CTRL}><RotateCcw className="size-4" /></button>
                <button type="button" onClick={() => { const next = !rotating; api.current?.setRotate(next); setRotating(next); }} title={t(locale, "ex_rotate")} aria-label={t(locale, "ex_rotate")} aria-pressed={rotating} className={CTRL}>{rotating ? <Pause className="size-4" /> : <Play className="size-4" />}</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 나라별 차이 */}
      {compare && (
      <section className="mx-auto w-full max-w-[1120px] px-4 py-10 sm:px-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[18px] font-semibold text-ink">{t(locale, "ex_compare_title")}</h2>
          <p className="text-[13px] text-steel">{t(locale, "ex_compare_hint")}</p>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-[13px]">
          {board.topics.map((x) => (
            <button key={x.id} type="button" onClick={() => setCompareId(x.id)} aria-pressed={compare.id === x.id}
              className={cn("rounded-[4px] border px-2.5 py-1 text-charcoal hover:text-ink", compare.id === x.id ? "border-[var(--ink)] bg-[var(--ink)] text-white hover:text-white" : "border-hairline")}>{x.name[locale]}</button>
          ))}
          <button type="button" onClick={() => openTopic(compare.id)} className="ml-auto text-link-blue hover:underline">{t(locale, "ex_show_on_globe")}</button>
        </div>
        <p className="mt-3 max-w-[760px] text-[14px] leading-relaxed text-charcoal">{compare.summary[locale]}</p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[960px] border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-hairline text-left text-steel">
                <th className="py-2 pr-3 font-medium">{t(locale, "ex_col_country")}</th>
                <th className="py-2 pr-3 font-medium">{t(locale, "ex_local_name")}</th>
                <th className="py-2 pr-3 font-medium">{t(locale, "ex_since")}</th>
                <th className="py-2 pr-3 font-medium">{t(locale, "ex_heat")}</th>
                <th className="py-2 pr-3 font-medium">{t(locale, "ex_what_changed")}</th>
                <th className="py-2 pr-3 font-medium">{t(locale, "ex_local_memes")}</th>
                <th className="py-2 font-medium">{t(locale, "ex_linked")}</th>
              </tr>
            </thead>
            <tbody className="align-top">
              {displayOrder(compare).map((v) => (
                <tr key={v.region} className="border-b border-hairline">
                  <th scope="row" className="py-3 pr-3 text-left font-medium text-ink whitespace-nowrap">{regionLabel(locale, v.region)}{v.region === originOf(compare) && <span className="ml-1.5 text-[11px] font-normal text-steel">{t(locale, "map_origin")}</span>}</th>
                  <td className="py-3 pr-3 font-medium text-ink whitespace-nowrap">{v.term_id ? <Link href={`/dictionary/${v.term_id}`} className="hover:underline">{v.local_name}</Link> : v.local_name}</td>
                  <td className="py-3 pr-3 text-steel tabular-nums whitespace-nowrap">{v.dated ? fmtDate(v.since) : t(locale, "map_undated")}</td>
                  <td className="py-3 pr-3 whitespace-nowrap"><Heat value={v.heat} /></td>
                  <td className="py-3 pr-3 min-w-[260px] leading-snug text-charcoal">{v.what_changed[locale]}</td>
                  <td className="py-3 pr-3 min-w-[180px] text-charcoal">
                    {v.local_memes.length ? <ul className="space-y-1">{v.local_memes.map((m) => <li key={m.label}><span className="text-ink">{m.label}</span><span className="text-steel"> · {m.note[locale]}</span></li>)}</ul> : <span className="text-steel">—</span>}
                  </td>
                  <td className="py-3 min-w-[160px] text-charcoal">
                    {v.linked.length ? <ul className="space-y-1">{v.linked.map((l) => <li key={l.label}>{l.term_id ? <Link href={`/dictionary/${l.term_id}`} className="text-link-blue hover:underline">{l.label}</Link> : <span className="text-ink">{l.label}</span>}<span className="text-steel"> · {l.note[locale]}</span></li>)}</ul> : <span className="text-steel">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      )}
    </>
  );
}
