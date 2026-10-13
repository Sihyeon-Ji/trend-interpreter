/* 규칙이 남긴 이유 문장(백엔드 verification·risk·검토 스크립트가 한국어로 쓴다)을 화면 언어로. 판정은 그대로이고 글만 옮긴다.
   리허설 DB 의 검수 이유 1,419가지·리스크 이유 352가지 가운데 자주 나오는 꼴(95% 이상)만 맞춘다 — 맞는 꼴이 없으면 원문 그대로(10-13). */
import type { Locale } from "./i18n";

type Rule = [RegExp, Record<Exclude<Locale, "ko">, string>];

const RULES: Rule[] = [
  // 검수 큐(게이트·정리 스크립트)
  [/^참고 문서\(나무위키·위키백과·Know Your Meme 등\)에 유래가 없어 사람이 확인한 뒤에만 실립니다$/,
    { en: "No reference page (Namuwiki, Wikipedia, Know Your Meme…) documents it, so it is published only after a person checks it",
      ja: "参考ページ（ナムウィキ・ウィキペディア・Know Your Meme など）に由来がないため、人が確認してから掲載します" }],
  [/^용어가 실재하는 독립 출처 (\d+)개 미만$/, { en: "Fewer than $1 independent sources show the term exists", ja: "言葉の存在を示す独立した出典が$1件未満" }],
  [/^(\d+)차 근거\(쇼츠·뉴스·데이터랩\) 없음 — 웹 검색만으로는 부족$/,
    { en: "No primary evidence (shorts, news, DataLab) — web search alone is not enough", ja: "一次根拠（ショート動画・ニュース・データラボ）がない — ウェブ検索だけでは不十分" }],
  [/^밈 카드 — 개별 밈이 아니라 대상 소개·목록·일반 낱말로 보인다$/,
    { en: "Meme card: reads as an introduction, a list or an ordinary word, not a single meme", ja: "ミームカード：個別のミームではなく、紹介・一覧・一般語に見える" }],
  [/^표현이 아니라 상품·기관·인물·일반 단어로 판단됨 — 사전 대상 아님$/,
    { en: "Judged a product, organization, person or ordinary word rather than an expression — not for the dictionary", ja: "表現ではなく商品・機関・人物・一般語と判断 — 辞書の対象外" }],
  [/^문서 대조: 고칠 것$/, { en: "Reference check: needs a fix", ja: "参考ページとの照合：要修正" }],
  [/^문서 대조: 위키끼리 다름$/, { en: "Reference check: wikis disagree", ja: "参考ページとの照合：ウィキ同士で説明が異なる" }],
  [/^뜻이 '근거 부족'·'정의 없음' 같은 빈말이다$/, { en: "The meaning is empty filler such as 'not enough evidence' or 'no definition'", ja: "意味が「根拠不足」「定義なし」のような中身のない文になっている" }],
  [/^풀이 '(.+)' 가 어떤 근거 원문에도 없음 — 환각 의심$/, { en: "The expansion '$1' is in no source text — possibly made up", ja: "略語の説明「$1」がどの根拠の原文にもない — 創作の疑い" }],
  [/^밈 아님\(두 판정 일치\): 로컬 판정 — 참고 문서에 밈·유행어로 쓰인다는 말이 없다(.*)$/,
    { en: "Not a meme (two checks agree): the reference page does not say it is used as a meme or slang", ja: "ミームではない（2つの判定が一致）：参考ページにミーム・流行語として使われるという記述がない" }],
  [/^용어가 원문에 없는 근거 (\d+)건 제외됨$/, { en: "$1 sources without the term were left out", ja: "言葉が原文にない根拠$1件を除外" }],
  [/^모델이 든 웹 근거 (\d+)건에 용어가 없음 — 환각 의심$/, { en: "The term is missing from $1 web sources the model cited — possibly made up", ja: "モデルが挙げたウェブ根拠$1件に言葉がない — 創作の疑い" }],
  [/^서로 다른 출처가 (\d+)개 미만$/, { en: "Fewer than $1 different sources", ja: "異なる出典が$1件未満" }],
  [/^뜻을 정의한 공개 출처가 없음(.*)$/, { en: "No public source defines the meaning", ja: "意味を定義した公開の出典がない" }],
  [/^확신도 (\d+)% \(기준 (\d+)%\)$/, { en: "Confidence $1% (threshold $2%)", ja: "確信度$1%（基準$2%）" }],
  // 리스크(쓸 때 주의)
  [/^그 뜻으로 쓰인 근거가 (\d+)건뿐이라 판단을 보류한다\.?$/, { en: "Only $1 sources use it in this sense, so the call is on hold.", ja: "その意味で使われた根拠が$1件しかなく、判断を保留しています。" }],
  [/^그 뜻으로 쓰인 근거가 (\d+)건뿐이라 판단을 보류한다 \(글자만 같은 딴 이야기 (\d+)건 제외\)\.?$/,
    { en: "Only $1 sources use it in this sense, so the call is on hold ($2 unrelated uses of the same letters left out).",
      ja: "その意味で使われた根拠が$1件しかなく、判断を保留しています（文字だけ同じ別の話$2件を除外）。" }],
  [/^위키 분류가 (.+) 소재의 밈이라고 적었다 — 브랜드가 쓰기 조심스럽다\.?$/,
    { en: "The wiki files it as a meme about $1 — a brand should be careful.", ja: "ウィキの分類が「$1」を題材にしたミームとしている — ブランドが使うには注意が必要。" }],
  [/^분류된 근거 (\d+)건에 위험 신호가 없다\.?$/, { en: "No risk signal in $1 classified sources.", ja: "分類した根拠$1件にリスクの兆候はない。" }],
  [/^뜻풀이가 민감한 소재\('(.+)'\)를 다룬다\.?$/, { en: "The meaning touches a sensitive subject ('$1').", ja: "意味の説明が敏感な題材（「$1」）を扱っている。" }],
  [/^표제어 자체가 욕설·성적 표현이다\.?$/, { en: "The word itself is profane or sexual.", ja: "見出し語そのものが罵倒・性的な表現である。" }],
  [/^커뮤니티 글의 (\d+)%가 부정적인 맥락$/, { en: "$1% of community posts use it in a negative context", ja: "コミュニティ投稿の$1%が否定的な文脈" }],
  [/^위험 유형이 붙은 근거 (\d+)건$/, { en: "$1 sources tagged with a risk type", ja: "リスクの種類が付いた根拠$1件" }],
  [/^커뮤니티 글에서 정치 맥락으로 쓰인 경우 (\d+)건$/, { en: "$1 community posts use it in a political context", ja: "コミュニティ投稿で政治的な文脈で使われた例$1件" }],
];

// 이유 문장 안에 끼는 소재 낱말(위키 분류·민감 소재 규칙의 낱말). 없는 낱말은 원문 그대로
const WORDS: Record<Exclude<Locale, "ko">, Record<string, string>> = {
  en: { "정치 및 사회": "politics and society", "종교": "religion", "대통령": "president", "정치인": "politician", "선거": "election", "테러": "terrorism",
        "자살": "suicide", "혐오": "hate", "전쟁": "war", "범죄": "crime", "성적": "sexual", "장애": "disability", "인종": "race", "사망": "death" },
  ja: { "정치 및 사회": "政治・社会", "종교": "宗教", "대통령": "大統領", "정치인": "政治家", "선거": "選挙", "테러": "テロ", "자살": "自殺", "혐오": "ヘイト",
        "전쟁": "戦争", "범죄": "犯罪", "성적": "性的", "장애": "障害", "인종": "人種", "사망": "死亡" },
};

/** 규칙의 이유 문장을 화면 언어로. 한국어 화면이거나 맞는 꼴이 없으면 원문 */
export function reasonText(text: string, locale: Locale): string {
  if (locale === "ko") return text;
  for (const [re, out] of RULES) {
    const m = re.exec(text.trim());
    if (m) return out[locale].replace(/\$(\d)/g, (_, i) => { const g = m[Number(i)] ?? ""; return WORDS[locale][g] ?? g; });
  }
  return text;
}
