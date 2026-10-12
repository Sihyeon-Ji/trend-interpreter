import { t, type Locale } from "./i18n";

type Glossed = { gloss_ko: string; gloss_en: string; gloss_ja?: string; en_pending?: boolean; ko_pending?: boolean; ja_pending?: boolean };

/** 화면 언어의 뜻풀이. 영어판이 아직 없는 말(en_pending)은 영어 화면에 한국어 원문 대신 '번역 전' 을 보인다 —
 *  영어 화면 첫 쪽 뜻풀이의 75~85% 가 한국어였다(실데이터 10-04). 한국어 화면도 한국어판이 없고 원문이 일본어·영어뿐이면
 *  (ko_pending) 원문 대신 '준비 중' 을 보인다(대시보드 25개, 10-05). 일본어 화면도 영어와 같다(ja_pending, 예전 서버는 gloss_ja 가 없다).
 *  원문은 사전 항목에서 본다. */
export function glossFor(item: Glossed, locale: Locale): string {
  if (locale === "ko") return item.ko_pending ? t(locale, "gloss_ko_pending") : item.gloss_ko;
  if (locale === "ja") return item.ja_pending || !item.gloss_ja ? t(locale, "gloss_ja_pending") : item.gloss_ja;
  return item.en_pending ? t(locale, "gloss_en_pending") : item.gloss_en;
}
