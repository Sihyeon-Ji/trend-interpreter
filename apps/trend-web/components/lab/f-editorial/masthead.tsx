import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial-copy";
import { EDITIONS, editionName, issueHref } from "@/lib/lab/f-editorial";
import { LangSwitch } from "./lang-switch";
import { WatchCount } from "./watchlist";

/* 제호 줄 — 잡지 이름, 내 목록, 언어, 초안 목록. 앱 틀(사이드바)은 /lab 에서 그려지지 않으므로 시안이 스스로 그린다. */
export function Masthead({ locale, edition }: { locale: Locale; edition: string }) {
  return (
    <header className="fe-masthead">
      <div className="fe-wrap fe-masthead__row">
        <Link href={issueHref(edition)} className="fe-wordmark">{fe(locale, "site")}</Link>
        <nav className="fe-masthead__nav" aria-label={fe(locale, "site")}>
          <WatchCount locale={locale} href={`${issueHref(edition)}#fe-watch`} />
          <LangSwitch locale={locale} />
          <Link href="/lab" className="fe-quiet fe-masthead__drafts">{fe(locale, "drafts")}</Link>
        </nav>
      </div>
    </header>
  );
}

/* 판 고르기 — 판마다 실린 밈 수를 같이 보이고, 비어 있는 판은 눌리지 않는다(빈 호로 보내지 않는다). */
export function EditionTabs({ locale, edition, counts }: { locale: Locale; edition: string; counts: Record<string, number> }) {
  return (
    <nav className="fe-editions" aria-label={fe(locale, "edition_pick")}>
      <div className="fe-wrap">
        <ul className="fe-editions__list">
          {EDITIONS.map((code) => {
            const n = counts[code] ?? 0;
            const name = editionName(locale, code);
            const current = code === edition;
            return (
              <li key={code}>
                {n > 0 ? (
                  <Link href={issueHref(code)} className="fe-edition" aria-current={current ? "page" : undefined}>
                    {name}<span className="fe-edition__n">{n}</span>
                  </Link>
                ) : (
                  <span className="fe-edition is-empty" aria-disabled="true" title={fe(locale, "edition_empty")}>
                    {name}<span className="fe-edition__n">0</span>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
