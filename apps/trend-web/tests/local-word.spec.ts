import { expect, test } from "@playwright/test";
import { localWord, originalName } from "../lib/lang";

/* 화면에 세울 말 — 외국에서 온 말은 그 화면 언어의 원어 이름(백엔드 pipeline/names 가 문서에 글자 그대로 있는 것만 넣는다) */
test("the screen language's original name replaces the headword and drops the reading", () => {
  const gyudon = { canonical: "규동", lang: "ko", names: { ja: "牛丼" }, readings: { ja: "キュドン", en: "gyudong" } };
  expect(localWord(gyudon, "ja")).toEqual({ text: "牛丼", lang: "ja", local: true });
  expect(localWord(gyudon, "en")).toEqual({ text: "牛丼", lang: "ja", readings: gyudon.readings, local: true });   // 영어 화면도 원어, 읽기는 gyudong
  expect(localWord({ canonical: "推し活", lang: "ja" }, "ko")).toMatchObject({ text: "推し活", lang: "ja", local: false });
});

test("a word from an English-speaking country shows its English original on screens other than Korean", () => {
  const goblin = { canonical: "고블린 모드", lang: "ko", names: { en: "goblin mode" }, readings: { ja: "ゴブリン モード" } };
  expect(localWord(goblin, "ja")).toEqual({ text: "goblin mode", lang: "en", readings: goblin.readings, local: true });   // 원어 + 가타카나 읽기
  expect(localWord(goblin, "ko")).toMatchObject({ text: "고블린 모드", local: false });
  expect(originalName(goblin.names)).toEqual({ lang: "en", name: "goblin mode" });
  expect(originalName({ ja: "牛丼", en: "gyudon" })).toEqual({ lang: "ja", name: "牛丼" });
});

test("a reference title drops the site name in front, which the source column already gives in the screen language", async () => {
  const { cleanSource } = await import("../lib/sources");
  const e = { evidence_id: "e1", kind: "wiki", url: "https://namu.wiki/w/x", source_domain: "namu.wiki", observed_at: "2026-10-01T00:00:00Z",
    title: "나무위키: 제로투 회피 (CC BY-NC-SA 2.0 KR)", excerpt: "" } as const;
  const row = cleanSource(e as never, "제로투", "ja");
  expect(row.title).toBe("제로투 회피 (CC BY-NC-SA 2.0 KR)");          // 문서 제목·라이선스는 그대로
  expect(row.source).toBe("ナムウィキの記事");
});

test("site names in front of other reference titles are dropped too", async () => {
  const { stripSourceHead } = await import("../lib/sources");
  expect(stripSourceHead("Wikipedia (ja): スパイダーマッ (CC BY-SA)")).toBe("スパイダーマッ (CC BY-SA)");
  expect(stripSourceHead("Know Your Meme: Aura Farming")).toBe("Aura Farming");
  expect(stripSourceHead("Trend A Word #61: 갓생")).toBe("갓생");
  expect(stripSourceHead("Keep Calm and Carry On")).toBe("Keep Calm and Carry On");
  expect(stripSourceHead("밤티 - 나무위키 (CC BY-NC-SA 2.0 KR)")).toBe("밤티 (CC BY-NC-SA 2.0 KR)");
});

test("rule reasons on the admin screens are shown in the screen language, unknown ones stay as written", async () => {
  const { reasonText } = await import("../lib/reasons");
  expect(reasonText("용어가 실재하는 독립 출처 2개 미만", "ja")).toBe("言葉の存在を示す独立した出典が2件未満");
  expect(reasonText("그 뜻으로 쓰인 근거가 3건뿐이라 판단을 보류한다.", "en")).toBe("Only 3 sources use it in this sense, so the call is on hold.");
  expect(reasonText("뜻풀이가 민감한 소재('대통령')를 다룬다.", "ja")).toBe("意味の説明が敏感な題材（「大統領」）を扱っている。");
  expect(reasonText("위키 분류가 정치 및 사회 소재의 밈이라고 적었다 — 브랜드가 쓰기 조심스럽다.", "en")).toContain("politics and society");
  expect(reasonText("처음 보는 이유", "en")).toBe("처음 보는 이유");
  expect(reasonText("용어가 실재하는 독립 출처 2개 미만", "ko")).toBe("용어가 실재하는 독립 출처 2개 미만");
});
