import { tr } from "@/components/lab/r-flow/copy";
import { MakeForMarket, MarketSwitch } from "@/components/lab/r-flow/market-switch";
import { getMarketCounts } from "@/components/lab/r-flow/server";
import { getLocale } from "@/lib/locale";

/* 둘러보기의 머리와 시장 고르기는 시장을 바꿔도 남는다(레이아웃) — 고른 표시가 옮겨 가는 움직임이 이어지게. 표는 page.tsx */
export default async function ExploreLayout({ children }: { children: React.ReactNode }) {
  const [locale, counts] = await Promise.all([getLocale(), getMarketCounts()]);
  return (
    <>
      <div className="rf-head">
        <div>
          <h1 className="rf-title">{tr(locale, "ex_title")}</h1>
          <p className="rf-lead">{tr(locale, "ex_lead")}</p>
        </div>
        <MakeForMarket locale={locale} />
      </div>
      <div className="rf-bar">
        <MarketSwitch locale={locale} counts={counts} />
        <span className="rf-note rf-hide-touch">{tr(locale, "ex_keys")}</span>
      </div>
      {children}
    </>
  );
}
