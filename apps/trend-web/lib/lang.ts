/* 원문 글자의 말 — 화면 읽기 프로그램이 한글·가나·태국 글자를 제 음성으로 읽고, 한자를 제 글꼴로 그리게 (docs/트렌드/디자인-개편.md 원칙 4). */

const TERM_LANG: Record<string, string> = { zh: "zh-Hant", tl: "fil" };

/** 표제어 언어(term.lang) → HTML lang */
export const langTag = (lang?: string | null) => (lang ? TERM_LANG[lang] ?? lang : undefined);

/** 언어 칸이 없는 글(현지 이름·검색어·기사 제목)의 말을 글자로 짐작한다. 라틴 글자는 달지 않는다(화면 언어를 따른다).
 *  한자만 있으면 나라로 가른다: 일본은 ja, 대만·홍콩은 zh-Hant. */
export function scriptLang(text: string, region?: string | null): string | undefined {
  if (/[぀-ヿ]/.test(text)) return "ja";
  if (/[가-힣]/.test(text)) return "ko";
  if (/[฀-๿]/.test(text)) return "th";
  if (/[一-鿿]/.test(text)) return region === "JP" ? "ja" : "zh-Hant";
  return undefined;
}
