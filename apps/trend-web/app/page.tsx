import Link from "next/link";
import { KeywordTable } from "@/components/keyword-table";
import { ListTabs } from "@/components/list-tabs";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { RegionChips } from "@/components/region-chips";
import { getKeywordBoard } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";

/* 첫 화면 — 사용 흐름 1단계 '살펴보기' (ADR 0001, Plan 04, docs/트렌드/디자인-개편.md). 지역을 고르면 그 지역의 밈을
   지금 쓰이는·식어 가는·주의 셋으로 나눠 표로 보인다. 탭과 지역은 주소에만 둔다(익명은 설정을 갖지 않는다). */
const KNOWN = [...TARGET_REGIONS, "GLOBAL"];
const LISTS = ["rising", "fading", "caution"] as const;
type List = (typeof LISTS)[number];

export default async function Dashboard({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  // ?regions=JP&regions=KR 처럼 같은 키가 여러 번 오면 배열이다. 모르는 값은 버리고 순서를 고정한다 — 주소마다 캐시가 따로 생기지 않게.
  const raw = [sp.regions].flat().filter(Boolean).join(",");
  const asked = raw === "all" ? [] : raw.split(",").map((s) => s.trim().toUpperCase());
  const reader = raw ? {} : await getReader();    // 주소에 지역이 없으면 로그인한 사람의 나라, 익명은 목표 지역 전체
  const wanted = asked.length ? KNOWN.filter((r) => asked.includes(r)) : reader.region && TARGET_REGIONS.includes(reader.region) ? [reader.region] : [];
  const list: List = LISTS.includes(String(sp.list) as List) ? (String(sp.list) as List) : "rising";
  const board = await getKeywordBoard(wanted);
  const all = board.regions.length === TARGET_REGIONS.length && TARGET_REGIONS.every((r) => board.regions.includes(r));
  const href = (id: List) => {
    const q = new URLSearchParams();
    if (raw) q.set("regions", raw);
    if (id !== "rising") q.set("list", id);
    return q.size ? `/?${q}` : "/";
  };
  const cards = board[list];
  const nothing = LISTS.every((l) => board[l].length === 0);   // 셋 다 비었을 때만 '모인 표현이 없다' 고 쓴다
  const tabs = LISTS.map((id) => ({ id, label: t(locale, `dash_${id}`), count: board[id].length, href: href(id) }));
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader title={t(locale, "dash_title")} description={t(locale, "dash_intro")}
          meta={<span>{t(locale, "dash_updated")} <span className="tabular-nums text-charcoal">{fmtDateTime(board.generated_at, locale)}</span></span>}
          actions={<Link href="/map" className="text-[14px] text-link-blue hover:underline">{t(locale, "dash_pick_on_map")}</Link>}>
          <RegionChips selected={board.regions} counts={board.counts} all={all} locale={locale} list={list === "rising" ? undefined : list} />
        </PageHeader>
        <section aria-labelledby="dash-list" className="space-y-3">
          <h2 id="dash-list" className="sr-only">{t(locale, `dash_${list}`)}</h2>
          <ListTabs items={tabs} current={list} label={t(locale, "dash_lists")} />
          <p className="text-[13px] text-steel">{t(locale, `dash_${list}_note`)}</p>
          {cards.length ? <KeywordTable cards={cards} locale={locale} />
            : <p className="rounded-lg border border-hairline px-4 py-8 text-center text-[14px] text-charcoal">{nothing ? t(locale, "dash_empty") : t(locale, `dash_${list}_empty`)}</p>}
        </section>
      </div>
    </PageShell>
  );
}
