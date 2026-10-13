"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { Fragment, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { TrendGlobe, type GlobeApi, type GlobeArc, type GlobeBubble, type GlobeFocus } from "@/components/globe/trend-globe";
import { CENTROID } from "@/components/globe/points";
import { ListTabs } from "@/components/list-tabs";
import { PageHeader } from "@/components/page-header";
import { StatePanel } from "@/components/state-panel";
import { StatusBadge } from "@/components/status-badge";
import { koOrEn, t, type Locale } from "@/lib/i18n";
import { fmtDate, fmtDateTime, regionLabel } from "@/lib/labels";
import { langTag, localWord, scriptLang } from "@/lib/lang";
import { TARGET_REGIONS } from "@/lib/reader";
import { displayOrder, originOf, pathOf } from "@/lib/trends/path";
import type { Topic, TopicVariant, TrendBoard } from "@/lib/trends/types";
import type { KeywordBoard, KeywordCard } from "@/lib/types";
import { cn } from "@/lib/utils";

/* 세계 지도 — 대시보드의 지역을 고르는 화면(ADR 0001, docs/트렌드/디자인-개편.md). 머리 → 탭(지역 | 나라를 건너간 밈) → 지도 패널 + 표.
   지역 층은 대시보드와 같은 키워드 보드(밈 수·주의·대표 밈)라 두 화면의 숫자가 같다. 고른 지역·탭·밈은 주소에만 둔다(뒤로 가기 기록은 쌓지 않는다). */

const KNOWN = [...TARGET_REGIONS, "GLOBAL"];
const LISTS = ["rising", "fading", "caution"];
const rad = Math.PI / 180;
const PRIMARY = "inline-flex h-11 items-center justify-center rounded-md bg-ink px-4 text-[14px] font-medium whitespace-nowrap text-white hover:bg-ink/85 sm:h-9";
const CTRL = "flex size-8 items-center justify-center border-b border-hairline-strong text-charcoal last:border-b-0 hover:bg-surface hover:text-ink";
const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((acc, [k, x]) => acc.replace(`{${k}}`, String(x)), s);

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

const noop = () => () => {};
function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (cb) => { const m = window.matchMedia(query); m.addEventListener("change", cb); return () => m.removeEventListener("change", cb); },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
const useReducedMotion = () => useSyncExternalStore(noop, () => window.matchMedia("(prefers-reduced-motion: reduce)").matches, () => false);

/** 조사가 끝난 주제 — 나라마다 '무엇이 달라졌나' 가 하나라도 있다 */
const researched = (x: Topic) => x.variants.some((v) => v.what_changed.ko || v.what_changed.en);

function Heat({ value }: { value: number }) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap tabular-nums">
      <span className="inline-block h-[3px] w-[40px] rounded-[2px] bg-hairline" aria-hidden>
        <span className="block h-full rounded-[2px] bg-ink" style={{ width: `${value}%` }} />
      </span>
      <span className="text-[13px] text-charcoal">{value}</span>
    </span>
  );
}

function Named({ items, locale, region }: { items: { label: string; note: { ko: string; en: string }; term_id?: string }[]; locale: Locale; region: string }) {
  if (!items.length) return <span className="text-steel">—</span>;
  return (
    <ul className="space-y-1.5">
      {items.map((m) => (
        <li key={m.label}>
          <span className="block text-ink" lang={scriptLang(m.label, region)}>
            {m.term_id ? <Link href={`/dictionary/${m.term_id}`} className="text-link-blue hover:underline">{m.label}</Link> : m.label}
          </span>
          {m.note[koOrEn(locale)] && <span className="block text-[13px] text-steel">{m.note[koOrEn(locale)]}</span>}
        </li>
      ))}
    </ul>
  );
}

function VariantDetail({ topic, locale }: { topic: Topic; locale: Locale }) {
  const origin = originOf(topic);
  const done = researched(topic);
  const order = displayOrder(topic);
  const since = (v: TopicVariant) => (
    <>
      <span className="tabular-nums">{v.dated ? fmtDate(v.since) : t(locale, "map_undated")}</span>
      {v.dated && v.since_source && <span className="block text-[12px] text-steel">{v.since_source[koOrEn(locale)]}</span>}
    </>
  );
  const local = (v: TopicVariant) => (
    <span lang={scriptLang(v.local_name, v.region)} className="font-medium text-ink">
      {v.term_id ? <Link href={`/dictionary/${v.term_id}`} className="hover:underline">{v.local_name}</Link> : v.local_name}
    </span>
  );
  return (
    <section aria-labelledby="mp-compare" className="space-y-3">
      <h2 id="mp-compare" className="text-[18px] font-semibold text-ink">{fill(t(locale, "mp_compare_title"), { meme: topic.name[koOrEn(locale)] })}</h2>
      {topic.summary[koOrEn(locale)] && <p className="max-w-[720px] text-[15px] leading-[1.55] text-charcoal">{topic.summary[koOrEn(locale)]}</p>}
      {!origin && <p className="max-w-[720px] text-[13px] text-steel">{t(locale, "map_no_path")}</p>}

      {/* 768px 이상: 표 */}
      <table className="hidden w-full table-fixed text-left text-[14px] md:table">
        <colgroup>
          <col className="w-[112px]" /><col className="w-[140px]" /><col className="w-[120px]" />
          {done && <><col className="w-[112px]" /><col /><col className="w-[20%]" /><col className="w-[18%]" /></>}
        </colgroup>
        <thead className="border-b border-hairline bg-surface text-[13px] text-steel">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">{t(locale, "ex_col_country")}</th>
            <th scope="col" className="px-3 py-2 font-medium">{t(locale, "ex_local_name")}</th>
            <th scope="col" className="px-3 py-2 font-medium">{t(locale, "mp_first_confirmed")}</th>
            {done && <>
              <th scope="col" className="px-3 py-2 text-right font-medium">{t(locale, "ex_heat")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t(locale, "ex_what_changed")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t(locale, "ex_local_memes")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t(locale, "ex_linked")}</th>
            </>}
          </tr>
        </thead>
        <tbody className="align-top">
          {order.map((v) => (
            <tr key={v.region} className="border-b border-hairline">
              <th scope="row" className="px-3 py-3 font-medium text-ink">
                {regionLabel(locale, v.region)}
                {v.region === origin && <span className="block text-[12px] font-normal text-steel">{t(locale, "mp_first_confirmed")}</span>}
              </th>
              <td className="px-3 py-3 [overflow-wrap:break-word]">{local(v)}</td>
              <td className="px-3 py-3 text-charcoal">{since(v)}</td>
              {done && <>
                <td className="px-3 py-3 text-right"><Heat value={v.heat} /></td>
                <td className="px-3 py-3 leading-[1.55] text-charcoal">{v.what_changed[koOrEn(locale)] || <span className="text-steel">—</span>}</td>
                <td className="px-3 py-3 text-charcoal"><Named items={v.local_memes} locale={locale} region={v.region} /></td>
                <td className="px-3 py-3 text-charcoal"><Named items={v.linked} locale={locale} region={v.region} /></td>
              </>}
            </tr>
          ))}
        </tbody>
      </table>

      {/* 휴대폰: 나라마다 블록 — 가로 스크롤을 쓰지 않는다 */}
      <ul className="divide-y divide-hairline border-y border-hairline md:hidden">
        {order.map((v) => (
          <li key={v.region} className="space-y-2 py-3 text-[14px]">
            <p className="flex flex-wrap items-baseline gap-x-3">
              <span className="font-semibold text-ink">{regionLabel(locale, v.region)}</span>
              {local(v)}
              {v.region === origin && <span className="text-[12px] text-steel">{t(locale, "mp_first_confirmed")}</span>}
            </p>
            <dl className="flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
              <div className="flex gap-2"><dt className="text-steel">{t(locale, "mp_first_confirmed")}</dt><dd className="text-charcoal">{since(v)}</dd></div>
              {done && <div className="flex gap-2"><dt className="text-steel">{t(locale, "ex_heat")}</dt><dd className="tabular-nums text-charcoal">{v.heat}</dd></div>}
            </dl>
            {done && v.what_changed[koOrEn(locale)] && (
              <div><p className="text-[13px] text-steel">{t(locale, "ex_what_changed")}</p><p className="leading-[1.55] text-charcoal">{v.what_changed[koOrEn(locale)]}</p></div>
            )}
            {done && v.local_memes.length > 0 && <div><p className="text-[13px] text-steel">{t(locale, "ex_local_memes")}</p><Named items={v.local_memes} locale={locale} region={v.region} /></div>}
            {done && v.linked.length > 0 && <div><p className="text-[13px] text-steel">{t(locale, "ex_linked")}</p><Named items={v.linked} locale={locale} region={v.region} /></div>}
          </li>
        ))}
      </ul>
      {done && <p className="text-[13px] text-steel">{t(locale, "mp_compare_hint")}</p>}
    </section>
  );
}

export function TrendExplorer({ keywords, board, locale }: { keywords: KeywordBoard; board: TrendBoard; locale: Locale }) {
  const sp = useSearchParams();
  const pathname = usePathname();
  const wide = useMedia("(min-width: 768px)");
  const reduced = useReducedMotion();

  // 주소가 곧 상태다: ?regions=KR,JP(예전 ?region=KR 도), ?tab=topics, ?topic=…, 대시보드에서 온 ?list= 는 그대로 넘긴다
  const rawRegions = (sp.get("regions") ?? sp.get("region") ?? "").toUpperCase().split(",").map((s) => s.trim());
  const pickedKey = KNOWN.filter((r) => rawRegions.includes(r)).join(",");
  const picked = useMemo(() => (pickedKey ? pickedKey.split(",") : []), [pickedKey]);
  const tab: "regions" | "topics" = sp.get("tab") === "topics" ? "topics" : "regions";
  const list = LISTS.includes(sp.get("list") ?? "") ? sp.get("list") : null;
  const topics = useMemo(() => {
    const col = new Intl.Collator(locale);
    return [...board.topics].sort((a, b) => Number(researched(b)) - Number(researched(a)) || b.variants.length - a.variants.length || col.compare(a.name[koOrEn(locale)], b.name[koOrEn(locale)]));
  }, [board.topics, locale]);
  const wantedTopic = tab === "topics" ? sp.get("topic") : null;
  const topic = useMemo(() => (wantedTopic ? topics.find((x) => x.id === wantedTopic) : undefined), [topics, wantedTopic]);

  const go = (next: { regions?: string[]; tab?: "regions" | "topics"; topic?: string | null }) => {
    const q = new URLSearchParams();
    const r = next.regions ?? picked;
    const tb = next.tab ?? tab;
    const tp = next.topic === undefined ? topic?.id ?? null : next.topic;
    if (r.length) q.set("regions", r.join(","));
    if (tb === "topics") q.set("tab", "topics");
    if (tb === "topics" && tp) q.set("topic", tp);
    if (list) q.set("list", list);
    return q.size ? `${pathname}?${q}` : pathname;
  };
  const replace = (next: Parameters<typeof go>[0]) => window.history.replaceState(null, "", go(next));   // 고를 때마다 뒤로 가기 기록을 쌓지 않는다
  const toggle = (code: string) => replace({ regions: picked.includes(code) ? picked.filter((r) => r !== code) : KNOWN.filter((r) => r === code || picked.includes(r)) });

  const dashHref = (() => {
    const q = new URLSearchParams({ regions: picked.length ? picked.join(",") : "all" });
    if (list) q.set("list", list);
    return `/trends?${q}`;
  })();

  // 지역 층: 대시보드와 같은 수 — 밈 수는 counts, 주의 수와 대표 밈(지금 쓰이는 밈 1위, 없으면 식어 가는 밈 1위)은 백엔드가 지역마다
  // 전체에서 센 summary. 대시보드 첫 쪽(30개)만 보고 세면 작은 지역의 대표 밈이 빠진다(개편 통합 09-29)
  const regions = useMemo(() => KNOWN.map((code) => {
    const has = (c: KeywordCard) => c.regions.includes(code);
    const s = keywords.summary?.[code];
    return { code, count: keywords.counts[code] ?? 0, caution: s ? s.caution : keywords.caution.filter(has).length,
      top: s ? s.top : keywords.rising.find(has) ?? keywords.fading.find(has) ?? null };
  }), [keywords]);
  const empty = regions.every((r) => r.count === 0);

  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const regionRows = regions.filter((r) => !needle || regionLabel(locale, r.code).toLowerCase().includes(needle) || r.code.toLowerCase() === needle || (r.top?.canonical.toLowerCase().includes(needle) ?? false));
  const topicRows = topics.filter((x) => !needle || x.name.ko.toLowerCase().includes(needle) || x.name.en.toLowerCase().includes(needle)
    || x.variants.some((v) => v.local_name.toLowerCase().includes(needle) || regionLabel(locale, v.region).toLowerCase().includes(needle)));

  // 지도 — 휴대폰은 '지도로 보기' 를 누를 때만 globe.gl 을 불러온다
  const [mapOpen, setMapOpen] = useState(false);
  const showMap = wide || mapOpen;
  const api = useRef<GlobeApi | null>(null);
  const [focus, setFocus] = useState<GlobeFocus | null>(null);
  const look = (pos: { lat: number; lng: number; altitude: number }) => setFocus((f) => ({ ...pos, nonce: (f?.nonce ?? 0) + 1 }));
  const lookAt = (code: string, altitude: number) => { if (CENTROID[code]) look({ ...CENTROID[code], altitude }); };
  const [shown, setShown] = useState(0); // 경로가 몇 나라까지 그려졌나 (순서대로 등장)

  // 밈을 열면 경로가 날짜순으로 한 나라씩 그려지고, 카메라가 출발점과 그 나라가 함께 보이는 자리로 따라간다.
  // 날짜가 확인된 나라가 둘 미만이면 경로가 없다 — 나라들을 한꺼번에 보인다. 동작 줄이기면 경로를 한 번에 그린다.
  const topicId = topic?.id;
  useEffect(() => {
    if (!topic) return;
    const path = pathOf(topic);
    const order = displayOrder(topic);
    const timers: ReturnType<typeof setTimeout>[] = [];
    if (!path.length || reduced) {
      timers.push(setTimeout(() => {
        setShown(order.length);
        const o = path[0]?.region ?? order[0]?.region;
        if (o) lookAt(o, 2.0);
      }, 0));
      return () => timers.forEach(clearTimeout);
    }
    const origin = path[0].region;
    const step = 1300;
    path.forEach((v, i) => {
      timers.push(setTimeout(() => {
        setShown(i + 1);
        if (i === 0) lookAt(origin, 2.0);
        else look(between(origin, v.region));
      }, i === 0 ? 0 : step * i));
    });
    // 날짜가 확인되지 않은 나라는 경로가 다 그려진 뒤 한꺼번에, 선 없이
    if (order.length > path.length) timers.push(setTimeout(() => setShown(order.length), step * path.length));
    return () => timers.forEach(clearTimeout);
  }, [topicId, reduced]); // eslint-disable-line react-hooks/exhaustive-deps

  const bubbles: GlobeBubble[] = useMemo(() => {
    if (!wide) return [];   // 휴대폰 지도는 말풍선 없이 나라 색과 점만 — 이름과 수는 목록에서 본다
    if (tab === "topics") {
      if (!topic) return [];
      return displayOrder(topic).slice(0, shown).filter((v) => CENTROID[v.region])
        .map((v) => ({ region: v.region, ...CENTROID[v.region], title: v.local_name, titleLang: scriptLang(v.local_name, v.region), sub: regionLabel(locale, v.region) }));
    }
    return regions.filter((r) => r.code !== "GLOBAL" && CENTROID[r.code]).map((r) => ({
      region: r.code, ...CENTROID[r.code], sub: regionLabel(locale, r.code), picked: picked.includes(r.code),
      title: r.count ? fill(t(locale, "mp_bubble_count"), { n: r.count }) : t(locale, "mp_none_yet"), muted: !r.count,
    }));
  }, [wide, tab, topic, shown, regions, picked, locale]);
  const arcs: GlobeArc[] = useMemo(() => {
    if (tab !== "topics" || !topic) return [];
    const path = pathOf(topic);
    const o = path[0] && CENTROID[path[0].region];
    if (!o) return [];
    return path.slice(1, shown).filter((v) => CENTROID[v.region])
      .map((v) => ({ startLat: o.lat, startLng: o.lng, endLat: CENTROID[v.region].lat, endLng: CENTROID[v.region].lng }));
  }, [tab, topic, shown]);
  const rings = useMemo(() => {
    const o = tab === "topics" && topic ? originOf(topic) : null;
    return o && CENTROID[o] ? [CENTROID[o]] : [];
  }, [tab, topic]);
  const shaded = useMemo(() => (tab === "topics" ? (topic ? topic.variants.map((v) => v.region) : []) : TARGET_REGIONS), [tab, topic]);
  const pickedOnMap = useMemo(() => (tab === "regions" ? picked : []), [tab, picked]);
  const selectable = useMemo(() => (tab === "regions" ? TARGET_REGIONS : []), [tab]);

  const tabs = [
    { id: "regions", label: t(locale, "mp_tab_regions"), href: go({ tab: "regions" }) },
    { id: "topics", label: t(locale, "mp_tab_topics"), count: board.topics.length, href: go({ tab: "topics" }) },
  ];
  const pickedText = picked.length ? fill(t(locale, "mp_picked"), { n: picked.length }) : t(locale, "mp_picked_all");

  const mapPanel = (
    <div className="min-w-0 space-y-2">
      {!wide && (
        <button type="button" onClick={() => setMapOpen((o) => !o)} aria-expanded={mapOpen}
          className="inline-flex h-10 items-center rounded-md border border-hairline-strong bg-background px-3 text-[14px] text-ink">
          {t(locale, mapOpen ? "mp_hide_map" : "mp_show_map")}
        </button>
      )}
      {showMap && (
        <>
          <div className="relative h-[320px] min-w-0 overflow-hidden rounded-lg border border-hairline bg-surface md:h-[400px] xl:h-[560px]">
            <TrendGlobe shaded={shaded} picked={pickedOnMap} selectable={selectable} bubbles={bubbles} arcs={arcs} rings={rings} focus={focus}
              onSelect={toggle} apiRef={api} loadingLabel={t(locale, "mp_loading")} failedLabel={t(locale, "mp_map_failed")} />
            <div className="absolute bottom-4 right-4 flex flex-col overflow-hidden rounded-md border border-hairline-strong bg-background">
              <button type="button" onClick={() => api.current?.zoom(0.75)} aria-label={t(locale, "ex_zoom_in")} title={t(locale, "ex_zoom_in")} className={CTRL}><Plus className="size-4" aria-hidden /></button>
              <button type="button" onClick={() => api.current?.zoom(1.33)} aria-label={t(locale, "ex_zoom_out")} title={t(locale, "ex_zoom_out")} className={CTRL}><Minus className="size-4" aria-hidden /></button>
              <button type="button" onClick={() => api.current?.reset()} aria-label={t(locale, "ex_reset")} title={t(locale, "ex_reset")} className={CTRL}><RotateCcw className="size-4" aria-hidden /></button>
            </div>
          </div>
          <p className="text-[13px] text-steel">{t(locale, tab === "topics" ? "mp_legend_topic" : "mp_legend")}</p>
        </>
      )}
    </div>
  );

  const noMatch = (
    <StatePanel action={<button type="button" onClick={() => setQuery("")} className="text-[14px] text-link-blue hover:underline">{t(locale, "mp_clear_search")}</button>}>
      {fill(t(locale, "mp_no_match"), { q: query.trim() })}
    </StatePanel>
  );

  const regionTable = (
    <div className="min-w-0 space-y-3">
      {regionRows.length === 0 ? noMatch : (
        <>
          {/* 768px 이상: 표 */}
          <table className="hidden w-full table-fixed text-left text-[14px] md:table">
            <colgroup><col className="w-[44px]" /><col className="w-[30%]" /><col className="w-[64px]" /><col className="w-[92px]" /><col /></colgroup>
            <thead className="border-b border-hairline bg-surface text-[13px] text-steel">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium"><span className="sr-only">{t(locale, "mp_col_pick")}</span></th>
                <th scope="col" className="py-2 pr-3 font-medium">{t(locale, "mp_col_region")}</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">{t(locale, "mp_col_memes")}</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">{t(locale, "mp_col_caution")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t(locale, "mp_col_top")}</th>
              </tr>
            </thead>
            <tbody>
              {regionRows.map((r) => {
                const on = picked.includes(r.code);
                const label = regionLabel(locale, r.code);
                return (
                  <tr key={r.code} className={cn("h-11 border-b border-hairline align-middle", on && "bg-surface")}>
                    <td className="px-3"><input type="checkbox" checked={on} onChange={() => toggle(r.code)} aria-label={fill(t(locale, "mp_pick_label"), { region: label })} className="size-4 accent-link-blue" /></td>
                    <th scope="row" className="py-2 pr-3 font-medium">
                      {r.code === "GLOBAL" ? <span className="text-ink">{label}</span> : <Link href={`/country/${r.code}`} className="text-ink hover:underline">{label}</Link>}
                    </th>
                    <td className="py-2 pr-3 text-right tabular-nums text-ink">{r.count}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-charcoal">{r.caution}</td>
                    <td className="py-2 pr-3 [overflow-wrap:break-word]">
                      {r.top ? <Link href={`/dictionary/${r.top.term_id}`} lang={langTag(localWord(r.top, locale).lang)} className="text-ink hover:underline">{localWord(r.top, locale).text}</Link>
                        : <span className="text-steel">{r.count ? "—" : t(locale, "mp_none_yet")}</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {/* 휴대폰: 두 줄 목록, 체크 칸은 44×44 */}
          <ul className="divide-y divide-hairline border-y border-hairline md:hidden">
            {regionRows.map((r) => {
              const on = picked.includes(r.code);
              const label = regionLabel(locale, r.code);
              return (
                <li key={r.code} className={cn("flex items-start gap-1 py-1.5", on && "bg-surface")}>
                  <label className="flex size-11 shrink-0 items-center justify-center">
                    <input type="checkbox" checked={on} onChange={() => toggle(r.code)} aria-label={fill(t(locale, "mp_pick_label"), { region: label })} className="size-5 accent-link-blue" />
                  </label>
                  <div className="min-w-0 flex-1 py-2.5 pr-1">
                    <div className="flex items-baseline justify-between gap-3">
                      {r.code === "GLOBAL" ? <span className="text-[15px] font-medium text-ink">{label}</span> : <Link href={`/country/${r.code}`} className="text-[15px] font-medium text-ink">{label}</Link>}
                      {r.count ? (
                        <span className="flex shrink-0 gap-3 text-[13px] text-steel">
                          <span>{t(locale, "mp_col_memes")} <span className="tabular-nums text-ink">{r.count}</span></span>
                          <span>{t(locale, "mp_col_caution")} <span className="tabular-nums text-ink">{r.caution}</span></span>
                        </span>
                      ) : <span className="shrink-0 text-[13px] text-steel">{t(locale, "mp_none_yet")}</span>}
                    </div>
                    {r.top && <Link href={`/dictionary/${r.top.term_id}`} lang={langTag(localWord(r.top, locale).lang)} className="mt-0.5 block text-[14px] text-charcoal [overflow-wrap:break-word]">{localWord(r.top, locale).text}</Link>}
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
        <p aria-live="polite" className="text-charcoal">{picked.length ? pickedText : t(locale, "mp_picked_none")}</p>
        {picked.length > 0 && <button type="button" onClick={() => replace({ regions: [] })} className="text-link-blue hover:underline">{t(locale, "mp_clear")}</button>}
      </div>
      <p className="text-[13px] text-steel">{t(locale, "mp_global_note")}</p>
    </div>
  );

  const topicTable = topicRows.length === 0 ? (board.topics.length ? noMatch : <StatePanel>{t(locale, "mp_no_topics")}</StatePanel>) : (
    <table className="w-full table-fixed text-left text-[14px]">
      <colgroup><col /><col className="w-[34%]" /><col className="w-[64px]" /><col className="hidden w-[84px] md:table-column" /></colgroup>
      <thead className="border-b border-hairline bg-surface text-[13px] text-steel">
        <tr>
          <th scope="col" className="px-3 py-2 font-medium">{t(locale, "mp_col_meme")}</th>
          <th scope="col" className="py-2 pr-3 font-medium">{t(locale, "mp_col_origin")}</th>
          <th scope="col" className="py-2 pr-3 text-right font-medium">{t(locale, "mp_col_countries")}</th>
          <th scope="col" className="hidden py-2 pr-3 font-medium md:table-cell"><span className="sr-only">{t(locale, "mp_col_status")}</span></th>
        </tr>
      </thead>
      <tbody>
        {topicRows.map((x) => {
          const on = topic?.id === x.id;
          const o = originOf(x);
          return (
            <tr key={x.id} onClick={() => replace({ topic: x.id })} className={cn("cursor-pointer border-b border-hairline align-top hover:bg-surface-soft", on && "bg-surface shadow-[inset_2px_0_0_var(--link-blue)]")}>
              <th scope="row" className="px-3 py-2.5 font-medium">
                <button type="button" aria-current={on ? "true" : undefined} onClick={(e) => { e.stopPropagation(); replace({ topic: x.id }); }}
                  lang={scriptLang(x.name[koOrEn(locale)])} className="text-left text-ink [overflow-wrap:break-word] hover:underline">{x.name[koOrEn(locale)]}</button>
                {!researched(x) && <span className="mt-1 block md:hidden"><StatusBadge tone="muted">{t(locale, "mp_researching")}</StatusBadge></span>}
              </th>
              <td className="py-2.5 pr-3 text-charcoal">{o ? regionLabel(locale, o) : <span className="text-steel">{t(locale, "map_undated")}</span>}</td>
              <td className="py-2.5 pr-3 text-right tabular-nums text-ink">{x.variants.length}</td>
              <td className="hidden py-2.5 pr-3 md:table-cell">{!researched(x) && <StatusBadge tone="muted">{t(locale, "mp_researching")}</StatusBadge>}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );

  return (
    <div className={cn("space-y-6", tab === "regions" && !empty && "pb-[72px] md:pb-0")}>
      <PageHeader title={t(locale, "mp_title")} description={t(locale, "mp_intro")} divider={false}
        meta={<span>{t(locale, "mp_updated")} <span className="tabular-nums text-charcoal">{fmtDateTime(keywords.collected_at ?? keywords.generated_at, locale)}</span></span>}
        actions={!empty && <Link href={dashHref} className={cn(PRIMARY, "hidden md:inline-flex")}>{t(locale, "mp_open_dashboard")}</Link>}>
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="min-w-0 md:flex-1"><ListTabs items={tabs} current={tab} label={t(locale, "mp_tabs_label")} /></div>
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t(locale, "mp_search")} aria-label={t(locale, "mp_search")}
            className="h-10 w-full rounded-md border border-hairline-strong bg-background px-3 text-[14px] text-ink placeholder:text-steel md:mb-1.5 md:h-9 md:w-[280px]" />
        </div>
      </PageHeader>

      {tab === "regions" ? (
        empty ? <StatePanel>{t(locale, "mp_empty")}</StatePanel> : (
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_480px]">
            {mapPanel}
            {regionTable}
          </div>
        )
      ) : (
        <Fragment>
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_480px]">
            {mapPanel}
            <div className="min-w-0">{topicTable}</div>
          </div>
          {topic ? <VariantDetail topic={topic} locale={locale} /> : topicRows.length > 0 && <p className="text-[14px] text-charcoal">{t(locale, "mp_pick_topic")}</p>}
          <p className="text-[13px] text-steel">{t(locale, "map_source")}</p>
        </Fragment>
      )}

      {/* 휴대폰: 아래 막대에 고른 수와 검정 버튼(위쪽 선만, 그림자 없음) */}
      {tab === "regions" && !empty && (
        <div className="fixed inset-x-0 bottom-0 z-20 flex items-center justify-between gap-3 border-t border-hairline bg-background px-4 py-3 md:hidden">
          <span className="text-[14px] text-charcoal">{pickedText}</span>
          <Link href={dashHref} className={PRIMARY}>{t(locale, "mp_open_dashboard")}</Link>
        </div>
      )}
    </div>
  );
}
