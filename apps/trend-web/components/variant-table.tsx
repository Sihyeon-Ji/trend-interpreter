import { t, type Locale } from "@/lib/i18n";
import { scriptLang } from "@/lib/lang";
import { regionLabel } from "@/lib/labels";
import type { TopicVariant } from "@/lib/trends/types";

/* 나라별 차이 — 지금 관심이 큰 나라부터. 현지 이름·현지 밈은 원문이라 글자로 lang 을 붙인다.
   데스크톱은 표, 휴대폰은 나라마다 라벨 줄 묶음. */
export function VariantTable({ variants, locale }: { variants: TopicVariant[]; locale: Locale }) {
  const rows = [...variants].sort((a, b) => b.heat - a.heat);
  const memes = (v: TopicVariant) => v.local_memes.map((m, i) => (
    <span key={m.label}>{i > 0 && ", "}<span lang={scriptLang(m.label, v.region)}>{m.label}</span></span>
  ));
  return (
    <>
      <table className="hidden w-full border-collapse text-left text-[14px] md:table">
        <thead>
          <tr className="border-b border-hairline text-[13px] text-steel">
            <th scope="col" className="w-[96px] py-2 pr-4 font-medium">{t(locale, "term_col_country")}</th>
            <th scope="col" className="w-[160px] py-2 pr-4 font-medium">{t(locale, "term_col_local_name")}</th>
            <th scope="col" className="py-2 pr-4 font-medium">{t(locale, "term_col_changed")}</th>
            <th scope="col" className="w-[200px] py-2 font-medium">{t(locale, "term_col_local_memes")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((v) => (
            <tr key={v.region} className="border-b border-hairline align-top">
              <th scope="row" className="py-2.5 pr-4 font-medium text-ink">{regionLabel(locale, v.region)}</th>
              <td lang={scriptLang(v.local_name, v.region)} className="py-2.5 pr-4 text-ink">{v.local_name}</td>
              <td className="py-2.5 pr-4 leading-[1.55] text-charcoal">{v.what_changed[locale]}</td>
              <td className="py-2.5 text-charcoal">{v.local_memes.length ? memes(v) : <span className="text-steel">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="divide-y divide-hairline border-y border-hairline md:hidden">
        {rows.map((v) => (
          <li key={v.region} className="py-3 text-[14px]">
            <p className="font-medium text-ink">{regionLabel(locale, v.region)}</p>
            <dl className="mt-1.5 grid grid-cols-[112px_minmax(0,1fr)] gap-x-3 gap-y-1.5">
              <dt className="text-[13px] text-steel">{t(locale, "term_col_local_name")}</dt>
              <dd lang={scriptLang(v.local_name, v.region)} className="text-ink">{v.local_name}</dd>
              {v.what_changed[locale] && <><dt className="text-[13px] text-steel">{t(locale, "term_col_changed")}</dt><dd className="leading-[1.55] text-charcoal">{v.what_changed[locale]}</dd></>}
              {v.local_memes.length > 0 && <><dt className="text-[13px] text-steel">{t(locale, "term_col_local_memes")}</dt><dd className="text-charcoal">{memes(v)}</dd></>}
            </dl>
          </li>
        ))}
      </ul>
    </>
  );
}
