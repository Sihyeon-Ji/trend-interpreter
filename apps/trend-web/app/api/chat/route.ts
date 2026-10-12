import { apiFetch } from "@/lib/api-fetch";
import { NextResponse } from "next/server";
import { explain } from "@/lib/data";
import { koOrEn, localeOf, type Locale } from "@/lib/i18n";
import { getReader } from "@/lib/reader-server";

/** 물음표나 의문사가 있으면 질문으로 본다. "AI slop 누가 써?" 처럼 사전 용어가 들어 있어도 묻는 말이면
 *  메시지를 번역해 주는 게 아니라 답을 해야 한다(09-16 실측: 그냥 용어 매칭으로 보내니 "…저질 콘텐츠 누가 써?" 가 나왔다). */
const QUESTION = /[?？]\s*$|무슨\s*뜻|뜻이|누가|어디서|왜\b|어떻게|언제|뭐가|뭐야|알려\s*줘|설명해|\b(what|who|why|how|when|where|which)\b/i;

/** "이거 해석해줘", "쉽게 풀어 써줘" 처럼 대놓고 부탁하면 메시지를 풀어 쓰는 쪽이다. 부탁하는 말은 빼고 본문만 넘긴다. */
const TRANSLATE = /(해석|번역)\s*(좀|해)?\s*(해\s*)?(줘|주세요|줄래|해라)?|쉽게\s*(좀\s*)?(풀어|바꿔)|풀어\s*(써|주|줘)|무슨\s*말(이야|인지)/;
// 문장 뒤에 붙은 물음 꼬리. 해석할 본문에서 떼어 낸다.
const ASK_TAIL = /\s*(이거|이게|이것|이\s*문장|이\s*말)?\s*(무슨\s*(뜻|말)(이야|인지)?|뜻이\s*뭐야?|뭐야|뭔\s*뜻|설명해\s*줘|알려\s*줘)\s*[?？!.]*\s*$/;
const STRIP = /(이거|이것|이\s*문장|이\s*메시지|다음)?\s*(해석|번역)\s*(좀)?\s*(해\s*)?(줘|주세요|줄래|해라)?\s*[:：]?|쉽게\s*(좀\s*)?(풀어|바꿔)\s*(써|줘|주세요)?\s*[:：]?|풀어\s*(써|줘|주세요)\s*[:：]?|무슨\s*말(이야|인지)\??/g;

/** 한 입력을 두 갈래로 나눈다.
 *  - 묻는 말이거나 사전 용어가 없으면: 도구 호출 루프(`POST /ask`) — 사전·그래프를 도구로 읽고 근거와 함께 답한다.
 *  - 붙여 넣은 메시지면: 규칙 매칭 + 근거 카드(해석).
 *  둘 다 답이 없으면 그렇게 말한다 — 지어내지 않는다. */
export async function POST(req: Request) {
  let text = "", locale: Locale = "ko";
  let history: Array<{ role: string; content: string }> = [];
  let isEval = false;
  try {
    const body = (await req.json()) as { text?: string; locale?: string; history?: Array<{ role: string; content: string }>; eval?: boolean };
    text = (body.text ?? "").trim().slice(0, 500);
    locale = localeOf(body.locale);
    history = (body.history ?? []).slice(-6);
    isEval = body.eval === true;   // 평가 호출은 수요 집계에서 뺀다
  } catch {
    return NextResponse.json({ error: "요청 형식이 잘못됐습니다." }, { status: 400 });
  }
  if (!text) return NextResponse.json({ error: "내용을 입력해 주세요." }, { status: 400 });

  // "무슨 말이야" 는 두 가지다: "이게 무슨 말이야?"(문장 해석)와 "자만추가 무슨 말이야?"(낱말 뜻).
  // 부탁하는 말을 떼고 남는 본문이 한 낱말뿐이면 해석이 아니라 낱말 질문이다.
  const stripped = text.replace(STRIP, " ").replace(ASK_TAIL, " ").replace(/\s+/g, " ").trim();
  const wantsTranslation = TRANSLATE.test(text) && stripped.split(/\s+/).length >= 2;
  // 붙여 넣은 문장인가. 물음표가 붙어 있어도 본문이 있으면 '이 말이 무슨 뜻이냐' 를 묻는 것이다 —
  // 질문 경로로 보내면 문장 조각 한둘만 풀이하고 나머지는 지어낸다(사용자 지적 2026-09-16,
  // "침착맨 67 … 늙크크같고 웃김 이게 무슨 뜻이야?" 에 ㅇㅈㄹ 을 엉뚱하게 풀었다).
  // 표제어에 **대해** 묻는 말("밤티는 어디서 나온 말이야?")은 붙여 넣은 문장이 아니다.
  // 길이만 보고 해석 경로로 보내면 질문을 그대로 되돌려 준다(2026-09-16 평가에서 확인).
  const aboutTerm = /(어디서|왜|누가|언제|어떻게|어느|무슨)\s*[^\s]{0,12}\s*(나온|났|떴|뜬|쓰|써|시작|생긴|유래|의미|뜻)/.test(text);
  const pasted = !aboutTerm && (/\n/.test(text) || stripped.split(/\s+/).length >= 6);
  const body = wantsTranslation || pasted ? stripped : text;
  if (wantsTranslation || pasted || !QUESTION.test(text)) {
    // 사전 표제어를 하나도 못 찾으면 아래 질문 경로로 그대로 흘러간다
    const result = await explain(body || text, locale, await getReader());
    if (result.items.length > 0) return NextResponse.json({ kind: "explain", result });
  }

  try {
    // 진행 상황을 그대로 흘려보낸다 — 오래 걸려도 무엇을 하는 중인지 보이면 기다릴 만하다.
    const res = await apiFetch(`/ask/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      // 답은 모델이 쓰는 글이라 한국어·영어뿐 — 일본어 화면은 영어로(docs/트렌드/일본어-용어집.md §6)
      body: JSON.stringify({ question: text, lang: koOrEn(locale), history, log_miss: !isEval }),
      cache: "no-store",
      signal: req.signal,
    });
    if (!res.ok || !res.body) return NextResponse.json({ kind: "answer", answer: "", failed: true });
    return new Response(res.body, {
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache", "x-accel-buffering": "no" },
    });
  } catch {
    return NextResponse.json({ kind: "answer", answer: "", failed: true });
  }
}
