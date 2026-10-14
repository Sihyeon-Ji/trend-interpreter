/* 원문 글자의 말 — 화면 읽기 프로그램이 한글·가나·태국 글자를 제 음성으로 읽고, 한자를 제 글꼴로 그리게 (docs/트렌드/디자인-개편.md 원칙 4). */

const TERM_LANG: Record<string, string> = { zh: "zh-Hant", tl: "fil" };

/** 표제어 언어(term.lang) → HTML lang */
export const langTag = (lang?: string | null) => (lang ? TERM_LANG[lang] ?? lang : undefined);

/** 언어 칸이 없는 글(현지 이름·검색어·기사 제목)의 말을 글자로 짐작한다. 라틴 글자는 달지 않는다(화면 언어를 따른다).
 *  한자만 있으면 나라로 가른다: 일본은 ja, 대만·홍콩은 zh-Hant. */
export function scriptLang(text: string, region?: string | null): string | undefined {
  // 가나와 한글이 함께 있으면 많은 쪽 — 한국어 뜻이 '推し活(오시카츠)' 를 인용하면 일본어로 잡혀 일본어 화면에 한국어 이전 뜻이 나왔다(10-14)
  const kana = text.match(/[぀-ヿ]/g)?.length ?? 0;
  const hangul = text.match(/[가-힣]/g)?.length ?? 0;
  if (kana && kana >= hangul) return "ja";
  if (hangul) return "ko";
  if (/[฀-๿]/.test(text)) return "th";
  if (/[一-鿿]/.test(text)) return region === "JP" ? "ja" : "zh-Hant";
  return undefined;
}

/** 그 시장 글자로 쓸 수 있는 말인가 — 라틴 글자만이거나 그 시장의 글자(한글·가나·한자)가 있다. 백엔드 generate.writable 의 글자 조건과 같다.
 *  첫 화면은 시장마다 '제 글자로 된' 말을 세우는데, 일본 칸에 한글 표기 말(건어물녀)이 섰다(10-12 리허설). */
const NON_LATIN = /[^\x00-\x7fÀ-ɏḀ-ỿ]/u;
const MARKET_SCRIPT: Record<string, RegExp> = { KR: /[가-힣]/u, JP: /[぀-ヿ一-鿿]/u };
export const writableIn = (word: string, market: string) => !NON_LATIN.test(word) || !!MARKET_SCRIPT[market]?.test(word);

/** 화면에 세울 말 — 기준은 화면 언어다(10-13 사용자: "설정한 언어가 기준이 되어야지"). 외국에서 온 말이 원어 이름을 가지면
 *  화면 언어의 이름(규동 → 일본어 화면 牛丼), 없으면 한국어가 아닌 화면에서는 그 말이 온 나라의 원어(고블린 모드 → 일본어 화면 goblin mode,
 *  규동 → 영어 화면 牛丼)를 세우고 화면 언어 글자의 읽기(ゴブリン モード, gyudon)를 곁에 둔다. 한국 말·원어 이름이 없는 말은 표제어와 읽기.
 *  원어 이름은 번역이 아니라 원문이다(백엔드 pipeline/names 가 문서에 글자 그대로 있는 것만 넣는다) */
export function localWord(x: { canonical: string; lang?: string | null; names?: Record<string, string> | null; readings?: Record<string, string> | null },
  locale: string): { text: string; lang: string; readings?: Record<string, string>; local: boolean } {
  const own = x.names?.[locale];
  if (own) return { text: own, lang: locale, local: true };
  const otherLang = locale === "ja" ? "en" : locale === "en" ? "ja" : null;
  const other = otherLang ? x.names?.[otherLang] : undefined;
  if (other && otherLang) return { text: other, lang: otherLang, readings: x.readings ?? undefined, local: true };
  return { text: x.canonical, lang: x.lang ?? "ko", readings: x.readings ?? undefined, local: false };
}

/** 표제어를 그대로 세울 때 곁에 둘 원어 — 그 말이 온 나라의 이름(규동 → 일본어 牛丼, 고블린 모드 → 영어 goblin mode). 일본어를 먼저 */
export function originalName(names: Record<string, string> | null | undefined): { lang: string; name: string } | null {
  if (names?.ja) return { lang: "ja", name: names.ja };
  if (names?.en) return { lang: "en", name: names.en };
  return null;
}

/** 글의 주된 글자 — 한글과 가나·한자 가운데 많은 쪽(일본어 인용이 낀 한국어 뜻을 일본어로 보지 않게). 둘 다 없으면 scriptLang */
export function mainScript(text: string): string | undefined {
  const ko = (text.match(/[가-힣]/g) ?? []).length, ja = (text.match(/[぀-ヿ]/g) ?? []).length;
  if (ko || ja) return ko >= ja ? "ko" : "ja";
  return scriptLang(text);
}
