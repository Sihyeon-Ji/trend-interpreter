"use client";

import { Bookmark, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { LOCALE_NAME, setLocaleCookie, type LabLocale as Locale } from "@/lib/i18n";
import { BASE, copy, type SinceItem } from "@/lib/lab/o-editorial";
import { isScrapped, lastVisit, readScraps, subscribeNothing, subscribeScraps, toggleScrap, type Scrap } from "./store";

/** 스크랩 단추. 이름표는 바뀌지 않고 눌림 상태(aria-pressed)와 채운 아이콘으로 보인다. */
export function ScrapButton({ locale, scrap, labelled = false }: { locale: Locale; scrap: Omit<Scrap, "at">; labelled?: boolean }) {
  const c = copy(locale);
  const on = useSyncExternalStore(subscribeScraps, () => isScrapped(scrap.id), () => false);
  const [msg, setMsg] = useState("");
  return (
    <>
      <button
        type="button"
        className={labelled ? "oe-scrap oe-scrap-labelled" : "oe-scrap"}
        aria-pressed={on}
        aria-label={labelled ? undefined : `${c.scrapAdd}: ${scrap.name}`}
        onClick={() => setMsg(toggleScrap(scrap) ? c.scrapAdded(scrap.name) : c.scrapRemoved(scrap.name))}
      >
        <Bookmark aria-hidden size={20} strokeWidth={2} fill={on ? "currentColor" : "none"} />
        {labelled && <span>{c.scrapAdd}</span>}
      </button>
      <span className="oe-sr" role="status">{msg}</span>
    </>
  );
}

/** 머리의 '스크랩 n' — 첫 화면의 내 스크랩으로 */
export function ScrapCount({ locale }: { locale: Locale }) {
  const c = copy(locale);
  const n = useSyncExternalStore(subscribeScraps, () => readScraps().length, () => 0);
  return (
    <a href={`${BASE}#scraps`} className="oe-mast-tool">
      <Bookmark aria-hidden size={18} strokeWidth={2} fill={n ? "currentColor" : "none"} />
      <span className="oe-tool-label">{c.scraps}</span>
      {n > 0 && <span className="oe-num">{n}</span>}
    </a>
  );
}

/** 화면 언어 — 지금 언어가 아닌 쪽 하나만 단추로 보인다 */
export function LocaleToggle({ locale }: { locale: Locale }) {
  const router = useRouter();
  const other: Locale = locale === "ko" ? "en" : "ko";
  return (
    <button type="button" className="oe-mast-tool" lang={other} onClick={() => { setLocaleCookie(other); router.refresh(); }}>
      {LOCALE_NAME[other]}
    </button>
  );
}

export function FindLink({ locale }: { locale: Locale }) {
  return (
    <a href={`${BASE}/search`} className="oe-mast-tool oe-mast-find">
      <Search aria-hidden size={18} strokeWidth={2} />
      <span className="oe-tool-label">{copy(locale).searchButton}</span>
    </a>
  );
}

/** '새로 실림'·'뜻 바뀜' 테이프 — 지난번 방문 뒤의 일일 때만(처음 온 사람에게는 이번 주 것 모두). 서버에서는 그리지 않는다. */
export function SinceBadge({ locale, at, kind }: { locale: Locale; at: string; kind: "verified" | "meaning_changed" }) {
  const prev = useSyncExternalStore(subscribeNothing, () => lastVisit() ?? "", () => null);
  if (prev === null) return null;
  if (prev && Date.parse(at) <= Date.parse(prev)) return null;
  const c = copy(locale);
  return <span className="oe-tape" data-tone="new">{kind === "verified" ? c.newTape : c.changedTape}</span>;
}

/** 판 머리의 한 줄 — '지난번 방문 이후 새로 실린 밈 3개, 뜻이 바뀐 밈 1개'. 누르면 아래 '지난번 방문 이후' 로.
 *  서버는 빈 줄(같은 높이)만 그리고, 브라우저가 지난번 방문 시각을 읽은 뒤 채운다 — 다시 온 사람에게 틀린 글이 번쩍이지 않게. */
export function SinceLine({ locale, items }: { locale: Locale; items: SinceItem[] }) {
  const c = copy(locale);
  const prev = useSyncExternalStore(subscribeNothing, () => lastVisit() ?? "", () => null);
  if (prev === null) return <p className="oe-since-line" aria-hidden="true">&nbsp;</p>;
  const list = prev ? items.filter((i) => Date.parse(i.at) > Date.parse(prev)) : items;
  const added = list.filter((i) => i.kind === "verified").length;
  const changed = list.filter((i) => i.kind === "meaning_changed").length;
  if (!added && !changed) return <p className="oe-since-line" data-quiet="true">{prev ? c.sinceLineNone : c.sinceLineQuiet}</p>;
  return (
    <p className="oe-since-line">
      <a href="#since">{prev ? c.sinceLineAfter(added, changed) : c.sinceLineWeek(added, changed)}</a>
    </p>
  );
}

/** 판 줄 — 좁은 화면에서는 옆으로 미는 줄. 지금 판(또는 묶은 판의 첫 시장)이 보이도록 처음 한 번 가로로만 옮긴다(세로로는 움직이지 않는다). */
export function EditionScroller({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLUListElement>(null);
  useEffect(() => {
    const ul = ref.current;
    if (!ul) return;
    // 넘칠 때만 끝을 흐리게(CSS) — 폭이 바뀌면 다시 잰다
    const measure = () => { ul.dataset.overflow = String(ul.scrollWidth > ul.clientWidth + 1); };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(ul);
    if (ul.scrollWidth > ul.clientWidth) {
      const el = ul.querySelector<HTMLElement>('[aria-current="page"], [data-member="true"]');
      const li = el?.closest("li");
      if (li) ul.scrollLeft = Math.max(0, li.offsetLeft - (ul.clientWidth - li.offsetWidth) / 2);
    }
    return () => ro.disconnect();
  }, []);
  return <ul ref={ref} className="oe-edition-list">{children}</ul>;
}
