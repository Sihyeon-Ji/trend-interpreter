// 해석 API 를 여러 메시지로 두드려 이상한 매칭·문장을 찾는다. 서버(pnpm start -p 3100) 가 떠 있어야 한다.
// 사용: node scripts/explain-check.mjs [base]
const BASE = process.argv[2] ?? "http://localhost:3100";

const CASES = [
  // [locale, text, expected terms (부분 일치), note]
  ["ko", "엄마 오늘 저메추 좀ㅋㅋ 소개팅은 됐고 나는 자만추 할래. 시험은 망했는데 완전 럭키비키잖아? 원영적 사고 가자", ["저메추", "자만추", "럭키비키", "원영적 사고"], "예시 메시지(재작성 있어야 함)"],
  ["ko", "자만추를 원해서 소개팅 안 나가", ["자만추"], "조사 붙음"],
  ["ko", "그건 완전 럭키비키였어", ["럭키비키"], "어미 붙음"],
  ["ko", "원영적사고로 살자", ["원영적 사고"], "띄어쓰기 없음"],
  ["ko", "점메추 좀! 그리고 저메추도", ["점메추", "저메추"], "점메추·저메추 별개"],
  ["ko", "나 이제 늙크크인가 영크크인가", ["늙크크", "영크크"], "영크크가 늙크크 안에 없음 확인"],
  ["ko", "이 코디 완전 밤티난다 ㅋㅋ 길티 밤티", ["밤티"], "활용형+파생형 → 항목 1개"],
  ["ko", "샤갈 전시회 보러 가자", ["샤갈"], "화가 샤갈 — 오탐(문맥 필요)"],
  ["ko", "2026년 6 7월에 만나자", [], "숫자 '6 7' 은 6-7 로 잡히면 안 됨"],
  ["ko", "전화 010-6-7-1234", [], "6-7 이 전화번호 안에서 잡히면 안 됨"],
  ["ko", "그 애들 6-7 외치면서 다녀", ["6-7"], "6-7 정상 매칭"],
  ["ko", "그 영상 aura farming 아니냐 推し活 하는 사람들 많네", ["aura farming", "推し活"], "영어·일본어 혼용"],
  ["ko", "아우라 파밍 하는 강아지", ["aura farming"], "한국어 음차 별칭"],
  ["ko", "야르! 시험 끝 할렐야루", ["야르"], "감탄사 + 상위형"],
  ["ko", "아 샤갈 진짜 난리자베스 슬프자베스", ["샤갈", "난리자베스"], "감정+자베스 응용"],
  ["ko", "테토남이야 에겐녀야?", ["테토남"], "별칭 두 개 → 항목 1개"],
  ["ko", "슬롭 좀 그만 올려", ["AI slop"], "한국어 음차로 영어 항목"],
  ["ko", "엄마 저녁 뭐 먹어?", [], "유행어 없음"],
  ["ko", "skibidi toilet 봤어?", ["skibidi"], "대문자·소문자"],
  ["ko", "Skibidiman 이라는 계정", [], "단어 일부(skibidi + man) 는 매칭 금지"],
  ["ko", "미드 시즌 재밌다", [], "사전에 없는 '미드'"],
  ["ko", "퉁퉁퉁퉁 사후르 퉁퉁퉁퉁 사후르", ["Tung Tung Tung Sahur"], "반복 → 항목 1개"],
  ["en", "ngl that boat kid is pure aura farming 😭 6-7!! bro is so skibidi", ["aura farming", "6-7", "skibidi"], "영어 예시(재작성 있어야 함)"],
  ["en", "my aura farm era", ["aura farming"], "영어 별칭 'aura farm'"],
  ["en", "that's so mid", [], "사전에 없음"],
  ["en", "The 6-7 kids are loud", ["6-7"], "영어 문맥 6-7"],
  ["en", "rated 6-7 out of 10", ["6-7"], "숫자 범위 6-7 — 오탐(문맥 필요)"],
  ["en", "she said 자만추 lol", ["자만추"], "영어 화면에서 한국어 용어 → 영어 설명"],
  ["en", "Sahur time", [], "'Sahur' 단독은 매칭 금지"],
  // 3차 추가분
  ["ko", "우리 회사 선배삐가 개대박삐야 ㅋㅋ 삐바삐지", ["삐에로 밈"], "OO삐 조어 → 삐에로 밈 1개"],
  ["ko", "4시간 웨이팅이지만 또 가고 싶은 식당입니다", ["또 가고 싶은 OO입니다"], "'지만 또 가고 싶은' 포맷"],
  ["ko", "또 가고 싶은 곳이 있어", [], "평범한 '또 가고 싶은' 은 매칭 금지"],
  ["ko", "모르는 개 산책 ㅋㅋㅋ 소 잃고 뇌 약간 고친다", ["속담 오타 밈"], "오타 밈 두 개 → 항목 1개"],
  ["ko", "오늘은 책없쾌로 야구 본다. 최애 사진이 오살힘", ["책없쾌", "오살힘"], "7월 줄임말"],
  ["ko", "그 배우 진짜 무공해야", ["무공해"], "사람에게 쓰는 무공해"],
  ["ko", "무공해 자동차 보조금", ["무공해"], "환경 용어 무공해 — 오탐(문맥 필요)"],
  ["ko", "자려고 누웠는데 양의지~ 라을라~", ["자려고 누웠는데 양의지", "라을라"], "5월 밈 2종"],
  ["ko", "사보필이 뭐야?", ["사보필"], "확인 중 항목 → '확인 중' 표시"],
  ["ko", "천연 위고비 좀 먹어야겠다", ["천연 위고비"], ""],
  ["en", "remember november 2026 is coming 🐻", ["Remember November 2026 Is Coming"], "소문자"],
  ["en", "that's la peace fr", ["La Peace"], ""],
  ["en", "cheddar and barbecue wavy = three layer dip stack!!", ["Three Layer Dip Stack"], ""],
  ["en", "ronaldo pasta edit goes hard", ["Ronaldo Pasta"], ""],
  ["en", "du bist gut genug 😭", ["Du Bist Gut Genug"], "독일어 용어"],
  ["en", "wow okay", ["Wow okay"], "예시 표기와 대소문자 다름"],
  ["en", "I forgot my airpods lol", ["I forgot my AirPods"], ""],
  ["en", "November 2026 calendar", [], "'November 2026' 단독은 매칭 금지"],
];


let fails = 0;
for (const [locale, text, expected, note] of CASES) {
  const res = await fetch(`${BASE}/api/explain`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, locale }) });
  const r = await res.json();
  const got = r.items.map((i) => i.record.term.canonical);
  const ok = expected.every((e) => got.includes(e)) && got.every((g) => expected.includes(g));
  if (!ok) fails++;
  console.log(`${ok ? "OK  " : "FAIL"} [${locale}] ${note}\n      "${text}"\n      → ${JSON.stringify(got)}${r.plain ? `\n      plain: ${r.plain}` : ""}`);
  for (const it of r.items) {
    const bad = [/people in their all/, /''/, /''/, /줄임말입니다\. .*줄임말/].filter((re) => re.test(it.headline + " " + it.background));
    if (bad.length) { fails++; console.log(`      TEXT? ${it.headline} | ${it.background}`); }
  }
}
console.log(`\n${CASES.length - fails}/${CASES.length} as expected`);
