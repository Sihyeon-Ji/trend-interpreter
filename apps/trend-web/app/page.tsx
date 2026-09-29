import Link from "next/link";
import { redirect } from "next/navigation";
import { KeywordPager, KeywordTable } from "@/components/keyword-table";
import { ListTabs } from "@/components/list-tabs";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { RegionChips } from "@/components/region-chips";
import { StatePanel } from "@/components/state-panel";
import { StatusBadge } from "@/components/status-badge";
import { getKeywordBoard, isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime, regionLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";
import type { KeywordBoard, KeywordList } from "@/lib/types";

/* 첫 화면 — 사용 흐름 1단계 '살펴보기' (ADR 0001, Plan 04, docs/트렌드/디자인-개편.md). 지역을 고르면 그 지역의 밈을
   지금 쓰이는·식어 가는·주의 셋으로 나눠 표로 보인다(주의 밈은 쓰이는·식는 목록에도, 사용 자제는 주의에만 — Plan 04). 지역·탭·쪽은 주소에만 둔다(익명은 설정을 갖지 않는다). */
const KNOWN = [...TARGET_REGIONS, "GLOBAL"];
const LISTS = ["rising", "fading", "caution"] as const satisfies readonly KeywordList[];

const one = (v: string | string[] | undefined) => [v].flat().filter(Boolean).join(",");

export default async function Dashboard({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  // 지역은 여러 곳(?regions=KR,JP, 순서는 칩 순서로 고정, 모르는 값은 버린다). 'all' 이나 모르는 값뿐이면 전체
  const raw = one(sp.regions);
  const asked = raw && raw !== "all" ? raw.split(",").map((s) => s.trim().toUpperCase()) : [];
  const reader = raw ? {} : await getReader();    // 주소에 지역이 없으면 로그인한 사람의 나라, 익명은 전체
  const picked = raw ? KNOWN.filter((r) => asked.includes(r)) : reader.region && TARGET_REGIONS.includes(reader.region) ? [reader.region] : [];
  const list: KeywordList = LISTS.find((l) => l === one(sp.list)) ?? "rising";
  const page = Math.max(1, Number.parseInt(one(sp.page), 10) || 1);

  const href = (to: { list?: KeywordList; page?: number } = {}) => {
    const q = new URLSearchParams();
    if (raw) q.set("regions", picked.length ? picked.join(",") : "all");
    const l = to.list ?? list, p = to.page ?? (to.list ? 1 : page);
    if (l !== "rising") q.set("list", l);
    if (p > 1) q.set("page", String(p));
    return q.size ? `/?${q}` : "/";
  };

  // 실데이터 모드에서 서버가 실패하면 예시로 바꿔 넣지 않는다 — 표 자리에 알리고 같은 주소로 다시 시도하게 한다
  let board: KeywordBoard | null = null;
  try {
    board = await getKeywordBoard(picked, page);
  } catch {
    board = null;
  }
  const total = board?.totals[list] ?? 0;
  const last = Math.max(1, Math.ceil(total / (board?.page_size ?? 30)));
  if (board && page > last) redirect(href({ page: last }));        // 범위를 넘는 쪽은 마지막 쪽으로

  const targets = picked.filter((r) => r !== "GLOBAL");             // 추천에 넘길 나라(목표 지역만, 전체·글로벌이면 없이)
  const mapQ = new URLSearchParams();
  if (picked.length) mapQ.set("regions", picked.join(","));
  if (list !== "rising") mapQ.set("list", list);                      // 지도가 대시보드로 돌려보낼 때 보던 목록을 그대로
  const names = picked.map((r) => (r === "GLOBAL" ? t(locale, "dash_global") : regionLabel(locale, r))).join(", ");
  const nothing = board && LISTS.every((l) => board.totals[l] === 0);
  const tabs = board ? LISTS.map((id) => ({ id, label: t(locale, `dash_${id}`), count: board.totals[id], href: href({ list: id }) })) : [];
  const cards = board?.[list] ?? [];
  const btn = "inline-flex h-9 items-center rounded-md border px-3.5 text-[14px] font-medium whitespace-nowrap";
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader title={t(locale, "dash_title")} description={t(locale, "dash_intro")}
          meta={!board ? null : isSampleMode
            ? <StatusBadge tone="muted">{t(locale, "dash_sample_badge")}</StatusBadge>   // 예시의 고정 시각을 갱신 시각처럼 내지 않는다
            : <span>{t(locale, "dash_updated")} <span className="tabular-nums text-charcoal">{fmtDateTime(board.generated_at, locale)}</span></span>}
          actions={
            <span className="flex flex-wrap gap-2">
              <Link href={mapQ.size ? `/map?${mapQ}` : "/map"} className={`${btn} border-hairline-strong text-ink hover:border-ink`}>{t(locale, "dash_pick_on_map")}</Link>
              <Link href={targets.length ? `/recommend?regions=${targets.join(",")}` : "/recommend"} className={`${btn} border-ink bg-ink text-white hover:bg-ink/85`}>{t(locale, "dash_to_recommend")}</Link>
            </span>
          }>
          <RegionChips picked={picked} counts={board?.counts} locale={locale} list={list === "rising" ? undefined : list} />
        </PageHeader>
        <section aria-labelledby="dash-list" className="space-y-3">
          <h2 id="dash-list" className="sr-only">{t(locale, `dash_${list}`)}</h2>
          {!board ? (
            <StatePanel role="alert" action={<Link href={href()} className="text-[14px] text-link-blue hover:underline">{t(locale, "dash_retry")}</Link>}>
              {t(locale, "dash_error")}
            </StatePanel>
          ) : nothing ? (
            // 세 목록이 다 비면 탭·표 대신 패널 하나 — 같은 빈 문장을 세 번 되풀이하지 않는다
            <StatePanel role="status" action={picked.length ? <Link href="/?regions=all" className="text-[14px] text-link-blue hover:underline">{t(locale, "dash_view_all")}</Link> : undefined}>
              {picked.length ? t(locale, "dash_region_empty").replace("{region}", names) : t(locale, "dash_empty")}
            </StatePanel>
          ) : (
            <>
              <ListTabs items={tabs} current={list} label={t(locale, "dash_lists")} />
              <p className="text-[13px] text-steel">
                {picked.includes("GLOBAL") && <>{t(locale, "dash_global_note")} </>}
                {t(locale, `dash_${list}_note`)}
              </p>
              {cards.length ? (
                <>
                  <KeywordTable cards={cards} locale={locale} showRegions={picked.length !== 1 || picked[0] === "GLOBAL"} linkRegions={picked} />
                  <KeywordPager total={total} page={page} size={board.page_size} href={(p) => href({ page: p })} locale={locale} />
                </>
              ) : <StatePanel role="status">{t(locale, `dash_${list}_empty`)}</StatePanel>}
            </>
          )}
        </section>
      </div>
    </PageShell>
  );
}
