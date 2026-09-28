import { KeywordCardView } from "@/components/keyword-card";
import { PageShell } from "@/components/page-shell";
import { RegionChips } from "@/components/region-chips";
import { getKeywordBoard } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";

/* 사용 흐름 1단계 '살펴보기' (ADR 0001, Plan 04). 지역을 고르면 그 지역의 밈을 뜨는·식는·주의 셋으로 나눠 보인다. */
export default async function TrendsPage({ searchParams }: { searchParams: Promise<{ regions?: string }> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const asked = sp.regions === "all" ? [] : (sp.regions ?? "").split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
  // 주소에 지역이 없으면 로그인한 사람의 나라 설정으로. 익명은 설정이 없어 목표 지역 전체다.
  const reader = sp.regions ? {} : await getReader();
  const wanted = asked.length ? asked : reader.region && TARGET_REGIONS.includes(reader.region) ? [reader.region] : [];
  const board = await getKeywordBoard(wanted);
  const all = board.regions.length === TARGET_REGIONS.length && TARGET_REGIONS.every((r) => board.regions.includes(r));
  const sections = [
    { id: "rising", title: t(locale, "dash_rising"), note: t(locale, "dash_rising_note"), cards: board.rising },
    { id: "fading", title: t(locale, "dash_fading"), note: t(locale, "dash_fading_note"), cards: board.fading },
    { id: "caution", title: t(locale, "dash_caution"), note: t(locale, "dash_caution_note"), cards: board.caution },
  ];
  return (
    <PageShell>
      <div className="space-y-10">
        <header className="space-y-3">
          <h1 className="text-[24px] font-semibold text-ink">{t(locale, "dash_title")}</h1>
          <p className="text-[15px] text-charcoal">{t(locale, "dash_intro")}</p>
          <RegionChips selected={board.regions} counts={board.counts} all={all} locale={locale} />
          <p className="text-[13px] text-steel">{t(locale, "dash_updated")} {fmtDateTime(board.generated_at, locale)}</p>
        </header>
        {sections.map((s) => (
          <section key={s.id} aria-labelledby={`dash-${s.id}`} className="space-y-3">
            <div>
              <h2 id={`dash-${s.id}`} className="text-[18px] font-semibold text-ink">{s.title} <span className="ml-1 text-[14px] font-normal text-steel">{s.cards.length}</span></h2>
              <p className="mt-0.5 text-[13px] text-steel">{s.note}</p>
            </div>
            {s.cards.length ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{s.cards.map((c) => <KeywordCardView key={c.term_id} card={c} locale={locale} />)}</div>
            ) : <p className="text-[14px] text-steel">{t(locale, "dash_empty")}</p>}
          </section>
        ))}
      </div>
    </PageShell>
  );
}
