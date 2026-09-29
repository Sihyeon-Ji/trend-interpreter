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

/* 첫 화면 — 사용 흐름 1단계 '살펴보기' (ADR 0001, Plan 04, docs/트렌드/디자인-개편.md). 지역 하나를 고르면 그 지역의 밈을
   지금 쓰이는·식어 가는·주의 셋(겹치지 않는다)으로 나눠 표로 보인다. 지역·탭·쪽은 주소에만 둔다(익명은 설정을 갖지 않는다). */
const KNOWN = [...TARGET_REGIONS, "GLOBAL"];
const LISTS = ["rising", "fading", "caution"] as const satisfies readonly KeywordList[];

const one = (v: string | string[] | undefined) => [v].flat().filter(Boolean).join(",");

export default async function Dashboard({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  // 지역은 하나만. 예전 주소(?regions=JP,TW)는 첫 번째 아는 값을 쓰고, 모르는 값뿐이면 전체로
  const raw = one(sp.regions);
  const asked = raw && raw !== "all" ? raw.split(",").map((s) => s.trim().toUpperCase()).find((r) => KNOWN.includes(r)) ?? null : null;
  const reader = raw ? {} : await getReader();    // 주소에 지역이 없으면 로그인한 사람의 나라, 익명은 전체
  const region = raw ? asked : reader.region && TARGET_REGIONS.includes(reader.region) ? reader.region : null;
  const list: KeywordList = LISTS.find((l) => l === one(sp.list)) ?? "rising";
  const page = Math.max(1, Number.parseInt(one(sp.page), 10) || 1);

  const href = (to: { list?: KeywordList; page?: number } = {}) => {
    const q = new URLSearchParams();
    if (raw) q.set("regions", region ?? "all");
    const l = to.list ?? list, p = to.page ?? (to.list ? 1 : page);
    if (l !== "rising") q.set("list", l);
    if (p > 1) q.set("page", String(p));
    return q.size ? `/?${q}` : "/";
  };

  // 실데이터 모드에서 서버가 실패하면 예시로 바꿔 넣지 않는다 — 표 자리에 알리고 같은 주소로 다시 시도하게 한다
  let board: KeywordBoard | null = null;
  try {
    board = await getKeywordBoard(region ? [region] : [], page);
  } catch {
    board = null;
  }
  const total = board?.totals[list] ?? 0;
  const last = Math.max(1, Math.ceil(total / (board?.page_size ?? 30)));
  if (board && page > last) redirect(href({ page: last }));        // 범위를 넘는 쪽은 마지막 쪽으로

  const local = region && region !== "GLOBAL" ? region : null;       // 추천·지도에 넘길 나라(전체·글로벌이면 없이)
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
              <Link href={local ? `/map?region=${local}` : "/map"} className={`${btn} border-hairline-strong text-ink hover:border-ink`}>{t(locale, "dash_pick_on_map")}</Link>
              <Link href={local ? `/recommend?regions=${local}` : "/recommend"} className={`${btn} border-ink bg-ink text-white hover:bg-ink/85`}>{t(locale, "dash_to_recommend")}</Link>
            </span>
          }>
          <RegionChips current={region} counts={board?.counts} locale={locale} list={list === "rising" ? undefined : list} />
        </PageHeader>
        <section aria-labelledby="dash-list" className="space-y-3">
          <h2 id="dash-list" className="sr-only">{t(locale, `dash_${list}`)}</h2>
          {!board ? (
            <StatePanel role="alert" action={<Link href={href()} className="text-[14px] text-link-blue hover:underline">{t(locale, "dash_retry")}</Link>}>
              {t(locale, "dash_error")}
            </StatePanel>
          ) : nothing ? (
            // 세 목록이 다 비면 탭·표 대신 패널 하나 — 같은 빈 문장을 세 번 되풀이하지 않는다
            <StatePanel role="status" action={region ? <Link href="/?regions=all" className="text-[14px] text-link-blue hover:underline">{t(locale, "dash_view_all")}</Link> : undefined}>
              {region ? t(locale, "dash_region_empty").replace("{region}", region === "GLOBAL" ? t(locale, "dash_global") : regionLabel(locale, region)) : t(locale, "dash_empty")}
            </StatePanel>
          ) : (
            <>
              <ListTabs items={tabs} current={list} label={t(locale, "dash_lists")} />
              <p className="text-[13px] text-steel">
                {region === "GLOBAL" && <>{t(locale, "dash_global_note")} </>}
                {t(locale, `dash_${list}_note`)}
              </p>
              {cards.length ? (
                <>
                  <KeywordTable cards={cards} locale={locale} showRegions={!region || region === "GLOBAL"} />
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
